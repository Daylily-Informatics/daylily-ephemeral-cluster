"""Repository and blessed analysis command catalog support."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from daylily_ec.analysis_identity import validate_analysis_segment
from daylily_ec.resources import resource_path


CATALOG_VERSION = 2
SUPPORTED_CATALOG_VERSIONS = {1, CATALOG_VERSION}
COMMAND_CLASSES = {"sample_analysis", "run_analysis", "utility"}
INPUT_CONTRACTS = {"sample_manifest", "run_context", "none"}
EXPORT_TRIGGERS = {"none", "on-success", "on-fail", "all"}
VALIDATION_STATUSES = {"success", "failed", "blocked", "not_run"}
ARTIFACT_REGISTRATION_INCLUDE_MODES = {"classification", "path"}


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


class TableSchema(BaseModel):
    """Tabular file contract exposed by the repository catalog."""

    model_config = ConfigDict(extra="forbid")

    path: str
    required_columns: List[str]

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _clean_id(value, field_name="path")

    @field_validator("required_columns")
    @classmethod
    def _validate_required_columns(cls, values: List[str]) -> List[str]:
        cleaned = [str(value).strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("required_columns values must not be empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("required_columns values must be unique")
        return cleaned


class InputContractDefinition(BaseModel):
    """Input and generated-table contract for a catalog command class."""

    model_config = ConfigDict(extra="forbid")

    description: str = ""
    source_table: Optional[TableSchema] = None
    generated_tables: Dict[str, TableSchema] = Field(default_factory=dict)

    @field_validator("generated_tables")
    @classmethod
    def _validate_generated_tables(cls, values: Dict[str, TableSchema]) -> Dict[str, TableSchema]:
        for key in values:
            _clean_id(key, field_name="generated_tables key")
        return values


class CommandInputRequirements(BaseModel):
    """Command-specific input requirements beyond the shared contract."""

    model_config = ConfigDict(extra="forbid")

    required_source_columns: List[str] = Field(default_factory=list)
    accepted_source_column_sets: List[List[str]] = Field(default_factory=list)
    required_run_context_values: Dict[str, str] = Field(default_factory=dict)

    @field_validator("required_source_columns")
    @classmethod
    def _validate_required_source_columns(cls, values: List[str]) -> List[str]:
        cleaned = [str(value).strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("required_source_columns values must not be empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("required_source_columns values must be unique")
        return cleaned

    @field_validator("accepted_source_column_sets")
    @classmethod
    def _validate_accepted_source_column_sets(cls, values: List[List[str]]) -> List[List[str]]:
        cleaned_sets: List[List[str]] = []
        for column_set in values:
            cleaned = [str(value).strip() for value in column_set]
            if any(not value for value in cleaned):
                raise ValueError("accepted_source_column_sets values must not be empty")
            if len(set(cleaned)) != len(cleaned):
                raise ValueError("accepted_source_column_sets values must be unique")
            cleaned_sets.append(cleaned)
        return cleaned_sets

    @field_validator("required_run_context_values")
    @classmethod
    def _validate_required_run_context_values(cls, values: Dict[str, str]) -> Dict[str, str]:
        return {
            _clean_id(key, field_name="required_run_context_values key"): _clean_id(
                value, field_name="required_run_context_values value"
            )
            for key, value in values.items()
        }


class CommandValidationRun(BaseModel):
    """A recorded validation attempt for a catalog command recipe."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    generated_at: str
    report_path: str
    ledger_path: str
    cluster: str
    region: str
    region_az: str
    dayec_tag: str
    dayec_commit: str
    dayoa_tag: str
    dayoa_commit: str
    tested_command: str
    status: str
    dryrun_status: str
    live_status: str
    dryrun_analysis_id: str = ""
    live_analysis_id: str = ""
    stage_or_context: str = ""
    failure_cause: str = ""
    notes: str = ""

    @field_validator(
        "run_id",
        "generated_at",
        "report_path",
        "ledger_path",
        "cluster",
        "region",
        "region_az",
        "dayec_tag",
        "dayec_commit",
        "dayoa_tag",
        "dayoa_commit",
        "tested_command",
    )
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        return _clean_id(value, field_name="validation_run value")

    @field_validator("status", "dryrun_status", "live_status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        cleaned = _clean_id(value, field_name="validation status").lower()
        if cleaned not in VALIDATION_STATUSES:
            raise ValueError(
                "validation status must be one of: " + ", ".join(sorted(VALIDATION_STATUSES))
            )
        return cleaned


class ArtifactRegistrationIdentity(BaseModel):
    """Explicit identity templates for downstream artifact registration."""

    model_config = ConfigDict(extra="forbid")

    analysis_euid: str
    run_euid: str
    workset_euid: str = ""
    project_euid: str = ""
    assay_id: str = ""

    @field_validator("analysis_euid", "run_euid")
    @classmethod
    def _validate_required_identity(cls, value: str) -> str:
        return _clean_id(value, field_name="artifact registration identity")


class ArtifactRegistrationPolicy(BaseModel):
    """Explicit command policy for registering exported DayOA evidence."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    evidence_manifest_path: str
    include_classifications: List[str] = Field(default_factory=list)
    include_paths: List[str] = Field(default_factory=list)
    require_existing: bool = True
    parser_family_hint: str
    multiqc_report_kind: str
    multiqc_version: str
    identity: ArtifactRegistrationIdentity

    @field_validator(
        "evidence_manifest_path",
        "parser_family_hint",
        "multiqc_report_kind",
        "multiqc_version",
    )
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        return _clean_id(value, field_name="artifact_registration value")

    @field_validator("include_classifications", "include_paths")
    @classmethod
    def _validate_include_lists(cls, values: List[str]) -> List[str]:
        cleaned = [str(value).strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("artifact_registration include values must not be empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("artifact_registration include values must be unique")
        return cleaned

    @field_validator("evidence_manifest_path", "include_paths")
    @classmethod
    def _validate_relative_paths(cls, value: Any) -> Any:
        paths = value if isinstance(value, list) else [value]
        for path in paths:
            cleaned = str(path).strip()
            if cleaned.startswith("/"):
                raise ValueError("artifact registration paths must be relative")
            if ".." in Path(cleaned).parts:
                raise ValueError("artifact registration paths must not contain '..'")
        return value

    @model_validator(mode="after")
    def _validate_selection(self) -> "ArtifactRegistrationPolicy":
        if self.enabled and not (self.include_classifications or self.include_paths):
            raise ValueError(
                "enabled artifact_registration requires include_classifications or include_paths"
            )
        return self


class AnalysisCommand(BaseModel):
    """Structured daylily-ec workflow launch profile."""

    model_config = ConfigDict(extra="forbid")

    command_id: str
    repository: str = ""
    display_name: str
    description: str = ""
    datasource: str
    launcher: str = "workflow_launch"
    command_class: str
    input_contract: str
    requires_staging: bool
    requires_run_mount: bool
    runtime_parameters: Dict[str, Any] = Field(default_factory=dict)
    input_requirements: CommandInputRequirements = Field(default_factory=CommandInputRequirements)
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
    git_tag: str = "main"
    no_containerized: bool = False
    optional_features: Dict[str, AnalysisCommandFeature] = Field(default_factory=dict)
    validation_runs: List[CommandValidationRun] = Field(default_factory=list)
    artifact_registration: Optional[ArtifactRegistrationPolicy] = None

    @field_validator(
        "command_id",
        "display_name",
        "datasource",
        "launcher",
        "command_class",
        "input_contract",
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

    @field_validator("runtime_parameters")
    @classmethod
    def _validate_runtime_parameters(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        cleaned: Dict[str, str] = {}
        for key, value in values.items():
            cleaned_key = _clean_id(key, field_name="runtime_parameters key")
            cleaned_value = _clean_id(str(value), field_name=f"runtime_parameters.{cleaned_key}")
            cleaned[cleaned_key] = cleaned_value
        return cleaned

    @model_validator(mode="after")
    def _validate_launcher(self) -> "AnalysisCommand":
        if self.launcher != "workflow_launch":
            raise ValueError("launcher must be workflow_launch")
        if self.command_class not in COMMAND_CLASSES:
            raise ValueError("command_class must be one of: " + ", ".join(sorted(COMMAND_CLASSES)))
        if self.input_contract not in INPUT_CONTRACTS:
            raise ValueError("input_contract must be one of: " + ", ".join(sorted(INPUT_CONTRACTS)))
        if self.command_class == "sample_analysis":
            if self.input_contract != "sample_manifest":
                raise ValueError("sample_analysis commands must use sample_manifest input")
            if not self.requires_staging:
                raise ValueError("sample_analysis commands must require staging")
            if self.requires_run_mount:
                raise ValueError("sample_analysis commands must not require run mounts")
        if self.command_class == "run_analysis":
            if self.input_contract != "run_context":
                raise ValueError("run_analysis commands must use run_context input")
            if self.requires_staging:
                raise ValueError("run_analysis commands must not require sample staging")
            if not self.requires_run_mount:
                raise ValueError("run_analysis commands must require run mounts")
        if self.command_class == "utility":
            if self.input_contract != "none":
                raise ValueError("utility commands must use none input")
            if self.requires_staging:
                raise ValueError("utility commands must not require sample staging")
            if self.requires_run_mount:
                raise ValueError("utility commands must not require run mounts")
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
        analysis_id: str,
        executing_entity: str,
        git_tag: Optional[str] = None,
        profile: Optional[str] = None,
        region: Optional[str] = None,
        cluster: Optional[str] = None,
        stage_dir: Optional[str] = None,
        session_name: Optional[str] = None,
        project: Optional[str] = None,
        run_context_file: Optional[str] = None,
        dry_run: bool = False,
        skip_project_check: bool = True,
        export_destination_s3_uri: Optional[str] = None,
        export_trigger: str = "none",
        delete_on_export_success: bool = False,
        artifact_registration_command_id: Optional[str] = None,
        dewey_url: Optional[str] = None,
        dewey_token_env: Optional[str] = None,
        dewey_analysis_dir_external_object_id: Optional[str] = None,
        dewey_run_artifact_euid: Optional[str] = None,
        dewey_ursa_analysis_euid: Optional[str] = None,
        replace_existing_analysis_dir: bool = False,
    ) -> List[str]:
        """Render a daylily-ec workflow launch argv for this profile."""

        resolved_analysis_id = validate_analysis_segment(analysis_id, field_name="analysis_id")
        resolved_executing_entity = validate_analysis_segment(
            executing_entity, field_name="executing_entity"
        )
        resolved_git_tag = git_tag or self.git_tag
        if export_trigger not in EXPORT_TRIGGERS:
            raise ValueError("export_trigger must be one of: " + ", ".join(sorted(EXPORT_TRIGGERS)))
        if export_destination_s3_uri and export_trigger == "none":
            raise ValueError(
                "export_trigger must not be 'none' when export_destination_s3_uri is set"
            )
        if delete_on_export_success and not export_destination_s3_uri:
            raise ValueError("delete_on_export_success requires export_destination_s3_uri")
        if artifact_registration_command_id and (not dewey_url or not dewey_token_env):
            raise ValueError(
                "artifact_registration_command_id requires dewey_url and dewey_token_env"
            )
        if not artifact_registration_command_id and (dewey_url or dewey_token_env):
            raise ValueError(
                "dewey_url and dewey_token_env require artifact_registration_command_id"
            )
        dewey_link_options = {
            "dewey_analysis_dir_external_object_id": dewey_analysis_dir_external_object_id,
            "dewey_run_artifact_euid": dewey_run_artifact_euid,
            "dewey_ursa_analysis_euid": dewey_ursa_analysis_euid,
        }
        if any(str(value or "").strip() for value in dewey_link_options.values()):
            missing = [
                name for name, value in dewey_link_options.items() if not str(value or "").strip()
            ]
            if missing:
                raise ValueError(
                    "Dewey analysis-directory external-link options must be provided together: "
                    + ", ".join(missing)
                )
            if not artifact_registration_command_id:
                raise ValueError(
                    "artifact_registration_command_id is required with Dewey external-link options"
                )
        dy_command = self.dryrun_dy_command if dry_run else self.dy_command
        if self.input_contract == "run_context":
            if not run_context_file:
                raise ValueError("run_context_file is required for run_analysis commands")
            if "run_context_file" not in self.runtime_parameters:
                raise ValueError(
                    f"runtime_parameters.run_context_file is required for {self.command_id}"
                )
            runtime_config = " ".join(
                shlex.quote(f"{key}={value}") for key, value in self.runtime_parameters.items()
            )
            dy_command = f"{dy_command} --config {runtime_config}"
        elif run_context_file:
            raise ValueError("run_context_file is only valid for run_analysis commands")
        if stage_dir and not self.requires_staging:
            raise ValueError("stage_dir is only valid for commands that require staging")
        argv = [
            "workflow",
            "launch",
            "--repository",
            self.repository,
            "--analysis-id",
            resolved_analysis_id,
            "--executing-entity",
            resolved_executing_entity,
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
            ("--run-context-file", run_context_file),
            ("--session-name", session_name),
            ("--project", project),
        ):
            if value:
                argv.extend([flag, value])
        argv.append("--skip-project-check" if skip_project_check else "--strict-project-check")
        if self.no_containerized:
            argv.append("--no-containerized")
        if self.input_contract == "none":
            argv.extend(["--no-input-staging", "--no-default-activation"])
            argv.append("--bootstrap-test-config")
        if export_destination_s3_uri:
            argv.extend(["--export-destination-s3-uri", export_destination_s3_uri])
        if export_trigger != "none":
            argv.extend(["--export-trigger", export_trigger])
        if delete_on_export_success:
            argv.append("--delete-on-export-success")
        if replace_existing_analysis_dir:
            argv.append("--replace-existing-analysis-dir")
        if artifact_registration_command_id:
            argv.extend(["--artifact-registration-command-id", artifact_registration_command_id])
            if dewey_url:
                argv.extend(["--dewey-url", dewey_url])
            if dewey_token_env:
                argv.extend(["--dewey-token-env", dewey_token_env])
            for flag, value in (
                ("--dewey-analysis-dir-external-object-id", dewey_analysis_dir_external_object_id),
                ("--dewey-run-artifact-euid", dewey_run_artifact_euid),
                ("--dewey-ursa-analysis-euid", dewey_ursa_analysis_euid),
            ):
                if value:
                    argv.extend([flag, value])
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
    input_contracts: Dict[str, InputContractDefinition] = Field(default_factory=dict)
    repositories: Dict[str, RepositoryDefinition]

    @model_validator(mode="after")
    def _validate_catalog(self) -> "RepositoryCatalog":
        if self.command_catalog_version not in SUPPORTED_CATALOG_VERSIONS:
            raise ValueError(
                f"command_catalog_version must be one of "
                f"{sorted(SUPPORTED_CATALOG_VERSIONS)}; "
                f"got {self.command_catalog_version}"
            )
        if self.default_repository not in self.repositories:
            raise ValueError(f"default_repository {self.default_repository!r} is not configured")
        unknown_contracts = set(self.input_contracts) - INPUT_CONTRACTS
        if unknown_contracts:
            raise ValueError(
                "input_contracts contains unknown contract id(s): "
                + ", ".join(sorted(unknown_contracts))
            )
        seen: set[str] = set()
        for repo_key, repo in self.repositories.items():
            for command in repo.analysis_commands:
                if command.command_id in seen:
                    raise ValueError(f"Duplicate analysis command id: {command.command_id}")
                seen.add(command.command_id)
                command.repository = repo_key
                if (
                    command.input_contract != "none"
                    and command.input_contract not in self.input_contracts
                ):
                    raise ValueError(
                        f"Missing input_contracts definition for {command.input_contract!r}"
                    )
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
            "input_contracts": {
                key: contract.model_dump(mode="json")
                for key, contract in self.input_contracts.items()
            },
            "repositories": {
                repo_key: repo.model_dump(mode="json")
                for repo_key, repo in self.repositories.items()
            },
            "commands": [command.model_dump(mode="json") for command in self.commands()],
        }


def default_catalog_path() -> Path:
    return resource_path("config/daylily_available_repositories.yaml")


def _migrate_v1_analysis_commands(raw: Dict[str, Any]) -> Dict[str, Any]:
    if raw.get("command_catalog_version") != 1:
        return raw
    migrated = dict(raw)
    migrated.setdefault(
        "input_contracts",
        {
            "sample_manifest": {
                "description": "Migrated v1 sample manifest contract.",
            }
        },
    )
    repositories = migrated.get("repositories")
    if not isinstance(repositories, dict):
        return migrated
    migrated_repositories: Dict[str, Any] = {}
    for repo_key, repo_value in repositories.items():
        if not isinstance(repo_value, dict):
            migrated_repositories[repo_key] = repo_value
            continue
        repo = dict(repo_value)
        commands = repo.get("analysis_commands")
        if isinstance(commands, list):
            migrated_commands = []
            for command_value in commands:
                if not isinstance(command_value, dict):
                    migrated_commands.append(command_value)
                    continue
                command = dict(command_value)
                command["command_class"] = "sample_analysis"
                command["input_contract"] = "sample_manifest"
                command["requires_staging"] = True
                command["requires_run_mount"] = False
                command["runtime_parameters"] = {}
                migrated_commands.append(command)
            repo["analysis_commands"] = migrated_commands
        migrated_repositories[repo_key] = repo
    migrated["repositories"] = migrated_repositories
    return migrated


def load_repository_catalog(path: Optional[Path] = None) -> RepositoryCatalog:
    catalog_path = Path(path).expanduser() if path is not None else default_catalog_path()
    raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Repository catalog must be a YAML mapping: {catalog_path}")
    if "command_catalog_version" not in raw:
        raise ValueError("Repository catalog is missing command_catalog_version")
    return RepositoryCatalog.model_validate(_migrate_v1_analysis_commands(raw))
