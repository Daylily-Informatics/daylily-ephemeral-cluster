"""Repository and blessed analysis command catalog support."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from daylily_ec.resources import resource_path


CATALOG_VERSION = 1


def _clean_id(value: str, *, field_name: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


class AnalysisCommandFeature(BaseModel):
    """Optional extension to a blessed analysis command."""

    model_config = ConfigDict(extra="forbid")

    display_name: str
    description: str = ""
    targets: List[str] = Field(default_factory=list)
    sv_callers: List[str] = Field(default_factory=list)

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        return _clean_id(value, field_name="display_name")

    @field_validator("targets", "sv_callers")
    @classmethod
    def _validate_string_list(cls, values: List[str]) -> List[str]:
        cleaned = [str(value).strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("list values must not be empty")
        return cleaned


class AnalysisCommand(BaseModel):
    """Structured daylily-ec workflow launch profile."""

    model_config = ConfigDict(extra="forbid")

    command_id: str
    repository: str = ""
    display_name: str
    description: str = ""
    datasource: str
    launcher: str = "workflow_launch"
    targets: List[str]
    genome: str
    jobs: int = Field(gt=0)
    aligners: List[str]
    dedupers: List[str]
    snv_callers: List[str]
    sv_callers: List[str] = Field(default_factory=list)
    dy_command: str
    dryrun_dy_command: str
    compatible_platforms: List[str]
    compatible_data_modes: List[str]
    destination: Optional[str] = None
    git_tag: str = "main"
    no_containerized: bool = False
    optional_features: Dict[str, AnalysisCommandFeature] = Field(default_factory=dict)

    @field_validator(
        "command_id",
        "display_name",
        "datasource",
        "launcher",
        "genome",
        "dy_command",
        "dryrun_dy_command",
        "git_tag",
    )
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        return _clean_id(value, field_name="value")

    @field_validator(
        "targets",
        "aligners",
        "dedupers",
        "snv_callers",
        "sv_callers",
        "compatible_platforms",
        "compatible_data_modes",
    )
    @classmethod
    def _validate_list(cls, values: List[str]) -> List[str]:
        cleaned = [str(value).strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("list values must not be empty")
        return cleaned

    @field_validator("destination")
    @classmethod
    def _validate_optional_destination(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _clean_id(value, field_name="destination")

    @model_validator(mode="after")
    def _validate_launcher(self) -> "AnalysisCommand":
        if self.launcher != "workflow_launch":
            raise ValueError("launcher must be workflow_launch")
        if not self.compatible_platforms:
            raise ValueError("compatible_platforms must not be empty")
        if not self.compatible_data_modes:
            raise ValueError("compatible_data_modes must not be empty")
        return self

    def with_features(self, feature_ids: Iterable[str]) -> "AnalysisCommand":
        """Return a copy with optional feature targets and config values applied."""

        targets = list(self.targets)
        sv_callers = list(self.sv_callers)
        for feature_id in feature_ids:
            key = _clean_id(feature_id, field_name="feature_id")
            feature = self.optional_features.get(key)
            if feature is None:
                raise KeyError(f"Unknown optional feature for {self.command_id}: {key}")
            for target in feature.targets:
                if target not in targets:
                    targets.append(target)
            for caller in feature.sv_callers:
                if caller not in sv_callers:
                    sv_callers.append(caller)
        return self.model_copy(update={"targets": targets, "sv_callers": sv_callers})

    def launch_argv(
        self,
        *,
        destination: Optional[str] = None,
        git_tag: Optional[str] = None,
        profile: Optional[str] = None,
        region: Optional[str] = None,
        cluster: Optional[str] = None,
        stage_dir: Optional[str] = None,
        session_name: Optional[str] = None,
        project: Optional[str] = None,
        dry_run: bool = False,
        skip_project_check: bool = True,
    ) -> List[str]:
        """Render a daylily-ec workflow launch argv for this profile."""

        resolved_destination = destination or self.destination
        if not resolved_destination:
            raise ValueError("destination is required to render a workflow launch command")
        resolved_git_tag = git_tag or self.git_tag
        dy_command = self.dryrun_dy_command if dry_run else self.dy_command
        argv = [
            "workflow",
            "launch",
            "--repository",
            self.repository,
            "--destination",
            resolved_destination,
            "--git-tag",
            resolved_git_tag,
            "--genome",
            self.genome,
            "--dy-command",
            dy_command,
        ]
        for flag, value in (
            ("--profile", profile),
            ("--region", region),
            ("--cluster", cluster),
            ("--stage-dir", stage_dir),
            ("--session-name", session_name),
            ("--project", project),
        ):
            if value:
                argv.extend([flag, value])
        argv.append("--skip-project-check" if skip_project_check else "--strict-project-check")
        if self.no_containerized:
            argv.append("--no-containerized")
        if dry_run:
            argv.append("--dry-run")
        return argv

    def incompatible_modes(self, modes: Sequence[str]) -> List[str]:
        """Return manifest data modes this command does not support."""

        supported = set(self.compatible_data_modes)
        return [mode for mode in modes if mode not in supported]


class RepositoryDefinition(BaseModel):
    """A repository configured for day-clone and optional Ursa launches."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = ""
    description: str = ""
    https_url: str
    ssh_url: Optional[str] = None
    default_ref: str
    relative_path: str
    analysis_commands: List[AnalysisCommand] = Field(default_factory=list)


class RepositoryCatalog(BaseModel):
    """Complete daylily_available_repositories.yaml contract."""

    model_config = ConfigDict(extra="forbid")

    command_catalog_version: int
    default_repository: str
    repositories: Dict[str, RepositoryDefinition]

    @model_validator(mode="after")
    def _validate_catalog(self) -> "RepositoryCatalog":
        if self.command_catalog_version != CATALOG_VERSION:
            raise ValueError(
                f"command_catalog_version must be {CATALOG_VERSION}; "
                f"got {self.command_catalog_version}"
            )
        if self.default_repository not in self.repositories:
            raise ValueError(f"default_repository {self.default_repository!r} is not configured")
        seen: set[str] = set()
        for repo_key, repo in self.repositories.items():
            for command in repo.analysis_commands:
                if command.command_id in seen:
                    raise ValueError(f"Duplicate analysis command id: {command.command_id}")
                seen.add(command.command_id)
                command.repository = repo_key
        return self

    def commands(self) -> List[AnalysisCommand]:
        result: List[AnalysisCommand] = []
        for repo in self.repositories.values():
            result.extend(repo.analysis_commands)
        return result

    def get_command(self, command_id: str) -> AnalysisCommand:
        command_key = _clean_id(command_id, field_name="command_id")
        for command in self.commands():
            if command.command_id == command_key:
                return command
        raise KeyError(f"Unknown analysis command: {command_key}")

    def to_public_payload(self) -> Dict[str, Any]:
        return {
            "command_catalog_version": self.command_catalog_version,
            "default_repository": self.default_repository,
            "repositories": {
                repo_key: repo.model_dump(mode="json")
                for repo_key, repo in self.repositories.items()
            },
            "commands": [command.model_dump(mode="json") for command in self.commands()],
        }


def default_catalog_path() -> Path:
    return resource_path("config/daylily_available_repositories.yaml")


def load_repository_catalog(path: Optional[Path] = None) -> RepositoryCatalog:
    catalog_path = Path(path).expanduser() if path is not None else default_catalog_path()
    raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Repository catalog must be a YAML mapping: {catalog_path}")
    if "command_catalog_version" not in raw:
        raise ValueError("Repository catalog is missing command_catalog_version")
    return RepositoryCatalog.model_validate(raw)
