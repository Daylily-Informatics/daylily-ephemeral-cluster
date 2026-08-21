"""Repository and blessed analysis command catalog support."""

from __future__ import annotations

import re
import shlex
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from daylily_ec.analysis_identity import validate_analysis_segment
from daylily_ec.resources import resource_path
from daylily_ec.workflow.dyr_preflight import normalize_dyr_preflight_options

CATALOG_VERSION = 6
SUPPORTED_CATALOG_VERSIONS = {1, 2, 3, 4, 5, CATALOG_VERSION}
CURRENT_DYEC_BUILD = "19.0.8"
DYEC_BUILD_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?$")
CROSS_BUILD_ALIAS_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?(?:[/:@])")
ALIAS_CONFIG_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
ALIAS_ENVIRONMENT_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
ALIAS_TARGET_PATTERN = re.compile(r"^[A-Za-z0-9_./:-]+$")
SHELL_WORD_PATTERN = re.compile(r"""(?:[^\s'"\\]+|\\.|'(?:[^']*)'|"(?:\\.|[^"\\])*")+""")
COMMAND_CLASSES = {"sample_analysis", "run_analysis", "utility"}
COMMAND_TYPES = {"prod", "test", "dev", "research"}
CLUSTER_TYPES = {"daywgs", "dragen", "sentieon-single"}
INPUT_CONTRACTS = {
    "six_manifest",
    "sample_manifest",
    "sample_manifest_v12",
    "run_context",
    "none",
}
SAMPLE_INPUT_CONTRACTS = {"six_manifest", "sample_manifest", "sample_manifest_v12"}
EXPORT_TRIGGERS = {"none", "on-success", "on-fail", "all"}
VALIDATION_STATUSES = {"success", "failed", "blocked", "not_run"}
SOURCE_MOUNT_MODES = {
    "none",
    "default_mounted",
    "explicit_run_mounts",
    "run_dra_required",
}
ARTIFACT_REGISTRATION_INCLUDE_MODES = {"classification", "path"}
ARTIFACT_REGISTRATION_MANIFEST_SOURCES = {"dayoa_manifest", "s3_inventory"}


def _validate_s3_uri_prefix(value: str, *, field_name: str) -> str:
    """Validate an explicit, prefix-shaped S3 URI without contacting AWS."""

    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    if not cleaned.startswith("s3://"):
        raise ValueError(f"{field_name} must be an s3:// URI")
    bucket_and_key = cleaned.removeprefix("s3://")
    bucket, separator, key = bucket_and_key.partition("/")
    if not bucket or not separator or not key.strip("/"):
        raise ValueError(f"{field_name} must name a non-root S3 prefix")
    return f"s3://{bucket}/{key.strip('/')}/"


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


class ResultExportGuidance(BaseModel):
    """Catalog-level contract for exporting completed analysis results."""

    model_config = ConfigDict(extra="forbid")

    description: str
    post_controller_protocol: List[str]
    manual_visit_command: str
    manual_export_command: str
    success_checks: List[str]
    preserves_fsx_by_default: bool

    @field_validator(
        "description",
        "manual_visit_command",
        "manual_export_command",
    )
    @classmethod
    def _validate_non_empty_text(cls, value: str) -> str:
        return _clean_id(value, field_name="result export guidance value")

    @field_validator("post_controller_protocol", "success_checks")
    @classmethod
    def _validate_non_empty_list(cls, values: List[str]) -> List[str]:
        cleaned = [str(value).strip() for value in values]
        if not cleaned or any(not value for value in cleaned):
            raise ValueError("result export guidance lists must not be empty")
        return cleaned

    @model_validator(mode="after")
    def _validate_export_contract(self) -> "ResultExportGuidance":
        protocol = "\n".join(self.post_controller_protocol)
        for token in ("DYEC", "controller", "dyec analysis visit", "dyec export"):
            if token not in protocol:
                raise ValueError(
                    "post_controller_protocol must require DYEC post-controller visit and export"
                )
        for token in ("dyec analysis visit", "--mode export", "--intent"):
            if token not in self.manual_visit_command:
                raise ValueError(f"manual_visit_command must include {token!r}")
        for token in ("dyec export", "--source-path", "--destination-s3-uri", "--output-dir"):
            if token not in self.manual_export_command:
                raise ValueError(f"manual_export_command must include {token!r}")
        if "--delete-data-in-file-system" in self.manual_export_command:
            raise ValueError("manual_export_command must preserve FSx data by default")
        if not self.preserves_fsx_by_default:
            raise ValueError("result export guidance must preserve FSx data by default")
        return self


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


class TestDataLocation(BaseModel):
    """Default-mounted catalog validation data root."""

    model_config = ConfigDict(extra="forbid")

    location_id: str
    description: str
    mount_path: str
    data_root: str
    s3_uri: str = ""
    applies_to_command_classes: List[str] = Field(default_factory=list)

    @field_validator("location_id", "description", "mount_path", "data_root")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        return _clean_id(value, field_name="test_data_locations value")

    @field_validator("s3_uri")
    @classmethod
    def _validate_optional_s3_uri(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("applies_to_command_classes")
    @classmethod
    def _validate_command_classes(cls, values: List[str]) -> List[str]:
        cleaned = [str(value).strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("applies_to_command_classes values must not be empty")
        unknown = set(cleaned) - COMMAND_CLASSES
        if unknown:
            raise ValueError(
                "applies_to_command_classes must use known command classes: "
                + ", ".join(sorted(unknown))
            )
        return cleaned


class TestDataProfile(BaseModel):
    """Reusable source-data profile for validating catalog commands."""

    model_config = ConfigDict(extra="forbid")

    description: str
    source_mount_mode: str
    source_s3_uri_template: str = ""
    source_fsx_prefix: str = ""
    locations: List[str] = Field(default_factory=list)
    run_context_source_s3_column: str = ""
    run_context_mount_id_column: str = ""
    run_context_values: Dict[str, str] = Field(default_factory=dict)
    source_notes: List[str] = Field(default_factory=list)

    @field_validator("description", "source_mount_mode")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        return _clean_id(value, field_name="test_data_profiles value")

    @field_validator("source_mount_mode")
    @classmethod
    def _validate_source_mount_mode(cls, value: str) -> str:
        cleaned = _clean_id(value, field_name="test_data_profiles.source_mount_mode")
        if cleaned not in SOURCE_MOUNT_MODES:
            raise ValueError(
                "test_data_profiles.source_mount_mode must be one of: "
                + ", ".join(sorted(SOURCE_MOUNT_MODES))
            )
        return cleaned

    @field_validator(
        "locations",
        "source_notes",
    )
    @classmethod
    def _validate_string_lists(cls, values: List[str]) -> List[str]:
        cleaned = [str(value).strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("test_data_profiles list values must not be empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("test_data_profiles list values must be unique")
        return cleaned

    @field_validator(
        "source_s3_uri_template",
        "source_fsx_prefix",
        "run_context_source_s3_column",
        "run_context_mount_id_column",
    )
    @classmethod
    def _validate_optional_strings(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("run_context_values")
    @classmethod
    def _validate_run_context_values(cls, values: Dict[str, str]) -> Dict[str, str]:
        return {
            _clean_id(str(key), field_name="run_context_values key"): str(value or "").strip()
            for key, value in values.items()
        }

    @model_validator(mode="after")
    def _validate_mount_contract(self) -> "TestDataProfile":
        if self.source_mount_mode == "none":
            if self.locations or self.source_s3_uri_template or self.source_fsx_prefix:
                raise ValueError("source_mount_mode none must not declare source locations")
            if self.run_context_source_s3_column or self.run_context_mount_id_column:
                raise ValueError("source_mount_mode none must not declare run-context columns")
            if self.run_context_values:
                raise ValueError("source_mount_mode none must not declare run-context values")
        elif self.source_mount_mode == "default_mounted":
            if not self.locations:
                raise ValueError("default_mounted profiles must declare locations")
            if not self.source_s3_uri_template:
                raise ValueError("default_mounted profiles must declare source_s3_uri_template")
            if not self.source_fsx_prefix:
                raise ValueError("default_mounted profiles must declare source_fsx_prefix")
            if self.run_context_source_s3_column or self.run_context_mount_id_column:
                raise ValueError("default_mounted profiles must not declare run-context columns")
            if self.run_context_values:
                raise ValueError("default_mounted profiles must not declare run-context values")
        elif self.source_mount_mode == "explicit_run_mounts":
            if not self.source_s3_uri_template:
                raise ValueError("explicit_run_mounts profiles must declare source_s3_uri_template")
            if not self.source_fsx_prefix:
                raise ValueError("explicit_run_mounts profiles must declare source_fsx_prefix")
            if self.locations:
                raise ValueError("explicit_run_mounts profiles must not declare default locations")
            if self.run_context_source_s3_column or self.run_context_mount_id_column:
                raise ValueError("explicit_run_mounts profiles must not declare run-context columns")
            if self.run_context_values:
                raise ValueError("explicit_run_mounts profiles must not declare run-context values")
        elif self.source_mount_mode == "run_dra_required":
            if not self.source_s3_uri_template:
                raise ValueError("run_dra_required profiles must declare source_s3_uri_template")
            if not self.source_fsx_prefix:
                raise ValueError("run_dra_required profiles must declare source_fsx_prefix")
            if not self.run_context_source_s3_column:
                raise ValueError(
                    "run_dra_required profiles must declare run_context_source_s3_column"
                )
            if not self.run_context_mount_id_column:
                raise ValueError(
                    "run_dra_required profiles must declare run_context_mount_id_column"
                )
        return self


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


class ArtifactRegistrationMultiQCReport(BaseModel):
    """Explicit MultiQC report root registered from an exported analysis."""

    model_config = ConfigDict(extra="forbid")

    report_kind: str
    html_path: str
    data_dir_path: str

    @field_validator("report_kind", "html_path", "data_dir_path")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        return _clean_id(value, field_name="artifact_registration.multiqc_reports value")

    @field_validator("html_path", "data_dir_path")
    @classmethod
    def _validate_relative_paths(cls, value: str) -> str:
        cleaned = str(value).strip()
        if cleaned.startswith("/"):
            raise ValueError("artifact registration MultiQC paths must be relative")
        if ".." in Path(cleaned).parts:
            raise ValueError("artifact registration MultiQC paths must not contain '..'")
        return cleaned


class ArtifactRegistrationPolicy(BaseModel):
    """Explicit command policy for registering exported DayOA evidence."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    manifest_source: str
    evidence_manifest_path: str
    include_classifications: List[str] = Field(default_factory=list)
    include_paths: List[str] = Field(default_factory=list)
    require_existing: bool = True
    allow_s3_body_sha256: bool = False
    s3_body_sha256_max_bytes: int = 50_000_000
    parser_family_hint: str
    multiqc_report_kind: str
    multiqc_version: str
    multiqc_reports: List[ArtifactRegistrationMultiQCReport] = Field(default_factory=list)
    identity: ArtifactRegistrationIdentity

    @field_validator(
        "manifest_source",
        "evidence_manifest_path",
        "parser_family_hint",
        "multiqc_report_kind",
        "multiqc_version",
    )
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        return _clean_id(value, field_name="artifact_registration value")

    @field_validator("manifest_source")
    @classmethod
    def _validate_manifest_source(cls, value: str) -> str:
        cleaned = _clean_id(value, field_name="artifact_registration.manifest_source")
        if cleaned not in ARTIFACT_REGISTRATION_MANIFEST_SOURCES:
            raise ValueError(
                "artifact_registration.manifest_source must be one of: "
                + ", ".join(sorted(ARTIFACT_REGISTRATION_MANIFEST_SOURCES))
            )
        return cleaned

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
        if self.s3_body_sha256_max_bytes <= 0:
            raise ValueError("artifact_registration.s3_body_sha256_max_bytes must be positive")
        if self.enabled and self.parser_family_hint == "multiqc" and not self.multiqc_reports:
            raise ValueError("enabled MultiQC artifact_registration requires multiqc_reports")
        report_kinds = [report.report_kind for report in self.multiqc_reports]
        if len(set(report_kinds)) != len(report_kinds):
            raise ValueError(
                "artifact_registration.multiqc_reports report_kind values must be unique"
            )
        return self


class AnalysisCommand(BaseModel):
    """Structured daylily-ec workflow launch profile."""

    model_config = ConfigDict(extra="forbid")

    command_id: str
    repository: str = ""
    type: str
    validated_version: str
    test_data_profile: str
    sample_manifest_template: str = ""
    manifest_dir_template: str = ""
    display_name: str
    description: str = ""
    datasource: str
    launcher: str = "workflow_launch"
    command_class: str
    input_contract: str
    requires_staging: bool
    requires_run_mount: bool
    staging_receipt_required: bool = False
    cost_center_required: bool = False
    runtime_config_target: str = ""
    runtime_parameters: Dict[str, Any] = Field(default_factory=dict)
    input_requirements: CommandInputRequirements = Field(default_factory=CommandInputRequirements)
    targets: List[str]
    genome: str
    day_profile: str = "slurm"
    jobs: int = Field(gt=0)
    keep_going: bool = True
    restart_times: int = Field(default=1, ge=0)
    aligners: List[str]
    dedupers: List[str]
    snv_callers: List[str]
    sv_callers: List[str] = Field(default_factory=list)
    dy_command: str
    dryrun_dy_command: str
    compatible_platforms: List[str]
    compatible_cluster_types: List[str]
    compatible_data_modes: List[str]
    git_tag: str = "main"
    no_containerized: bool = False
    return_results: bool = True
    default_activation: bool = True
    optional_features: Dict[str, AnalysisCommandFeature] = Field(default_factory=dict)
    validation_runs: List[CommandValidationRun] = Field(default_factory=list)
    validation_evidence_s3_uri_prefix: str = ""
    artifact_registration: Optional[ArtifactRegistrationPolicy] = None

    @property
    def validation_pending(self) -> bool:
        """Whether the target ref lacks matching recorded validation evidence."""

        return self.git_tag != self.validated_version

    def to_public_payload(self) -> Dict[str, Any]:
        """Serialize one command with derived validation state for public CLI output."""

        payload = self.model_dump(mode="json")
        payload["validation_pending"] = self.validation_pending
        return payload

    @field_validator(
        "command_id",
        "type",
        "validated_version",
        "test_data_profile",
        "display_name",
        "datasource",
        "launcher",
        "command_class",
        "input_contract",
        "genome",
        "day_profile",
        "dy_command",
        "dryrun_dy_command",
        "git_tag",
    )
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        return _clean_id(value, field_name="value")

    @field_validator("type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        cleaned = _clean_id(value, field_name="type")
        if cleaned not in COMMAND_TYPES:
            raise ValueError("type must be one of: " + ", ".join(sorted(COMMAND_TYPES)))
        return cleaned

    @field_validator(
        "targets",
        "aligners",
        "dedupers",
        "snv_callers",
        "sv_callers",
        "compatible_platforms",
        "compatible_cluster_types",
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

    @field_validator("sample_manifest_template", "manifest_dir_template")
    @classmethod
    def _validate_manifest_template_path(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            return ""
        path = Path(cleaned)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("manifest template paths must be relative and must not contain '..'")
        return cleaned

    @field_validator("runtime_config_target")
    @classmethod
    def _validate_runtime_config_target(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            return ""
        if cleaned != "config/dyec_runtime_config.yaml":
            raise ValueError(
                "runtime_config_target must be exactly config/dyec_runtime_config.yaml"
            )
        return cleaned

    @field_validator("validation_evidence_s3_uri_prefix")
    @classmethod
    def _validate_validation_evidence_s3_uri_prefix(cls, value: str) -> str:
        return _validate_s3_uri_prefix(value, field_name="validation_evidence_s3_uri_prefix")

    @model_validator(mode="after")
    def _validate_launcher(self) -> "AnalysisCommand":
        if self.launcher != "workflow_launch":
            raise ValueError("launcher must be workflow_launch")
        if self.command_class not in COMMAND_CLASSES:
            raise ValueError("command_class must be one of: " + ", ".join(sorted(COMMAND_CLASSES)))
        if self.input_contract not in INPUT_CONTRACTS:
            raise ValueError("input_contract must be one of: " + ", ".join(sorted(INPUT_CONTRACTS)))
        if self.manifest_dir_template and self.input_contract != "six_manifest":
            raise ValueError("manifest_dir_template requires the six_manifest input contract")
        if self.staging_receipt_required and self.input_contract != "six_manifest":
            raise ValueError("staging_receipt_required requires the six_manifest input contract")
        if self.runtime_config_target:
            if self.input_contract != "six_manifest" or not self.requires_staging:
                raise ValueError(
                    "runtime_config_target requires a staged six_manifest command"
                )
            required_configfile = f"--configfile {self.runtime_config_target}"
            if (
                required_configfile not in self.dy_command
                or required_configfile not in self.dryrun_dy_command
            ):
                raise ValueError(
                    "runtime_config_target must be the exact --configfile path in both commands"
                )
        if self.sample_manifest_template and self.input_contract == "six_manifest":
            raise ValueError(
                "six_manifest commands must use manifest_dir_template, not sample_manifest_template"
            )
        if self.sample_manifest_template and self.manifest_dir_template:
            raise ValueError(
                "sample_manifest_template and manifest_dir_template are mutually exclusive"
            )
        if self.command_class == "sample_analysis":
            if self.input_contract not in SAMPLE_INPUT_CONTRACTS:
                raise ValueError(
                    "sample_analysis commands must use an explicit sample manifest input contract"
                )
            if not self.requires_staging:
                raise ValueError("sample_analysis commands must require staging")
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
        if not self.compatible_cluster_types:
            raise ValueError("compatible_cluster_types must not be empty")
        unknown_cluster_types = set(self.compatible_cluster_types) - CLUSTER_TYPES
        if unknown_cluster_types:
            raise ValueError(
                "compatible_cluster_types must use known cluster types: "
                + ", ".join(sorted(unknown_cluster_types))
            )
        if not self.compatible_data_modes:
            raise ValueError("compatible_data_modes must not be empty")
        if not self.default_activation:
            activation_prefixes = ("source dyoainit;", ". dyoainit;")
            if not self.dy_command.startswith(activation_prefixes):
                raise ValueError(
                    "commands with default_activation=false must source dyoainit in dy_command"
                )
            if not self.dryrun_dy_command.startswith(activation_prefixes):
                raise ValueError(
                    "commands with default_activation=false must source dyoainit in dryrun_dy_command"
                )
        if self.day_profile != "slurm":
            expected_activation = f"dy-a {self.day_profile} {self.genome}"
            if self.default_activation:
                raise ValueError(
                    "commands with non-default day_profile must set default_activation=false"
                )
            if expected_activation not in self.dy_command:
                raise ValueError(f"dy_command must explicitly activate {expected_activation!r}")
            if expected_activation not in self.dryrun_dy_command:
                raise ValueError(
                    f"dryrun_dy_command must explicitly activate {expected_activation!r}"
                )
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
        manifest_dir: Optional[str] = None,
        session_name: Optional[str] = None,
        project: Optional[str] = None,
        cost_center: Optional[str] = None,
        run_context_file: Optional[str] = None,
        specimens_file: Optional[str] = None,
        samples_file: Optional[str] = None,
        libraries_file: Optional[str] = None,
        units_file: Optional[str] = None,
        runtime_config_file: Optional[str] = None,
        dry_run: bool = False,
        skip_project_check: bool = True,
        export_destination_s3_uri: Optional[str] = None,
        export_trigger: str = "none",
        delete_on_export_success: bool = False,
        replace_existing_analysis_dir: bool = False,
        remote_user: Optional[str] = None,
    ) -> List[str]:
        """Render a daylily-ec workflow launch argv for this profile."""

        resolved_analysis_id = validate_analysis_segment(analysis_id, field_name="analysis_id")
        resolved_executing_entity = validate_analysis_segment(
            executing_entity, field_name="executing_entity"
        )
        resolved_git_tag = git_tag or self.git_tag
        resolved_cost_center = None
        if cost_center is not None:
            from daylily_ec.aws.cost_centers import validate_cost_center_name

            resolved_cost_center = validate_cost_center_name(cost_center)
        if self.cost_center_required and resolved_cost_center is None:
            raise ValueError(
                f"{self.command_id} requires an explicit --cost-center; "
                "select an active DYEC cost center and do not infer it from --cluster"
            )
        if export_trigger not in EXPORT_TRIGGERS:
            raise ValueError("export_trigger must be one of: " + ", ".join(sorted(EXPORT_TRIGGERS)))
        if export_destination_s3_uri and export_trigger == "none":
            raise ValueError(
                "export_trigger must not be 'none' when export_destination_s3_uri is set"
            )
        if delete_on_export_success and not export_destination_s3_uri:
            raise ValueError("delete_on_export_success requires export_destination_s3_uri")
        dy_command = self.dryrun_dy_command if dry_run else self.dy_command
        dy_command = dy_command.replace("$ANALYSIS_ID", shlex.quote(resolved_analysis_id))
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
        dy_command = normalize_dyr_preflight_options(dy_command)
        if self.input_contract == "six_manifest":
            if not manifest_dir:
                raise ValueError("six_manifest commands require manifest_dir")
            if any((stage_dir, specimens_file, samples_file, libraries_file, units_file)):
                raise ValueError(
                    "manifest_dir cannot be combined with legacy stage or manifest arguments"
                )
            if self.runtime_config_target and not runtime_config_file:
                raise ValueError(
                    f"{self.command_id} requires runtime_config_file for "
                    f"{self.runtime_config_target}"
                )
        elif manifest_dir:
            raise ValueError("manifest_dir requires the six_manifest input contract")
        elif runtime_config_file:
            raise ValueError("runtime_config_file requires the six_manifest input contract")
        elif self.input_contract == "sample_manifest_v12":
            if units_file:
                raise ValueError(
                    "DayOA 12 commands reject units.tsv. Provide specimens_file, samples_file, "
                    "and libraries_file, or run `dayoa migrate-manifests` with a reviewed "
                    "identity map."
                )
            provided = (specimens_file, samples_file, libraries_file)
            if any(provided) and not all(provided):
                raise ValueError(
                    "specimens_file, samples_file, and libraries_file must be provided together"
                )
        elif specimens_file or libraries_file:
            raise ValueError(
                "specimens_file and libraries_file require the DayOA 12 sample_manifest_v12 contract"
            )
        elif samples_file or units_file:
            if not (samples_file and units_file):
                raise ValueError("samples_file and units_file must be provided together")
            if self.input_contract != "sample_manifest":
                raise ValueError(
                    "samples_file and units_file are only valid for legacy sample_analysis commands"
                )
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
            ("--manifest-dir", manifest_dir),
            ("--run-context-file", run_context_file),
            ("--specimens-file", specimens_file),
            ("--samples-file", samples_file),
            ("--libraries-file", libraries_file),
            ("--units-file", units_file),
            ("--session-name", session_name),
            ("--project", project),
            ("--cost-center", resolved_cost_center),
            ("--remote-user", remote_user),
        ):
            if value:
                argv.extend([flag, value])
        argv.append("--skip-project-check" if skip_project_check else "--strict-project-check")
        if self.no_containerized:
            argv.append("--no-containerized")
        if runtime_config_file:
            argv.extend(["--runtime-config-file", runtime_config_file])
        if not self.default_activation:
            argv.append("--no-default-activation")
        if self.input_contract == "none":
            argv.append("--no-input-staging")
            if "--no-default-activation" not in argv:
                argv.append("--no-default-activation")
            argv.append("--bootstrap-test-config")
        elif self.input_contract == "six_manifest":
            argv.extend(["--input-contract", "six_manifest"])
        elif self.input_contract == "sample_manifest_v12":
            argv.extend(["--input-contract", "sample_manifest_v12"])
        elif self.input_contract == "sample_manifest":
            argv.extend(["--input-contract", "sample_manifest"])
        if export_destination_s3_uri:
            argv.extend(["--export-destination-s3-uri", export_destination_s3_uri])
        if export_trigger != "none":
            argv.extend(["--export-trigger", export_trigger])
        if delete_on_export_success:
            argv.append("--delete-on-export-success")
        if replace_existing_analysis_dir:
            argv.append("--replace-existing-analysis-dir")
        if dry_run:
            argv.append("--dry-run")
        return argv

    def incompatible_modes(self, modes: Sequence[str]) -> List[str]:
        """Return manifest data modes this command does not support."""

        supported = set(self.compatible_data_modes)
        return [mode for mode in modes if mode not in supported]


class AnalysisCommandAliasMetadata(BaseModel):
    """Typed non-command fields that an alias may override on its base."""

    model_config = ConfigDict(extra="forbid")

    type: Optional[str] = None
    validated_version: Optional[str] = None
    test_data_profile: Optional[str] = None
    sample_manifest_template: Optional[str] = None
    manifest_dir_template: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    datasource: Optional[str] = None
    launcher: Optional[str] = None
    command_class: Optional[str] = None
    input_contract: Optional[str] = None
    requires_staging: Optional[bool] = None
    requires_run_mount: Optional[bool] = None
    staging_receipt_required: Optional[bool] = None
    cost_center_required: Optional[bool] = None
    runtime_parameters: Optional[Dict[str, Any]] = None
    input_requirements: Optional[CommandInputRequirements] = None
    genome: Optional[str] = None
    day_profile: Optional[str] = None
    jobs: Optional[int] = Field(default=None, gt=0)
    keep_going: Optional[bool] = None
    restart_times: Optional[int] = Field(default=None, ge=0)
    aligners: Optional[List[str]] = None
    dedupers: Optional[List[str]] = None
    snv_callers: Optional[List[str]] = None
    sv_callers: Optional[List[str]] = None
    compatible_platforms: Optional[List[str]] = None
    compatible_cluster_types: Optional[List[str]] = None
    compatible_data_modes: Optional[List[str]] = None
    git_tag: Optional[str] = None
    no_containerized: Optional[bool] = None
    return_results: Optional[bool] = None
    default_activation: Optional[bool] = None
    optional_features: Optional[Dict[str, AnalysisCommandFeature]] = None
    validation_runs: Optional[List[CommandValidationRun]] = None
    validation_evidence_s3_uri_prefix: Optional[str] = None
    artifact_registration: Optional[ArtifactRegistrationPolicy] = None


class AnalysisCommandAliasConfigValue(BaseModel):
    """One literal or environment-bound ``--config`` value for an alias."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: Optional[str] = None
    environment: Optional[str] = None

    @field_validator("key")
    @classmethod
    def _validate_key(cls, value: str) -> str:
        cleaned = _clean_id(value, field_name="alias config key")
        if not ALIAS_CONFIG_KEY_PATTERN.fullmatch(cleaned):
            raise ValueError("alias config key must be a simple DayOA config identifier")
        return cleaned

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _clean_id(value, field_name="alias config value")

    @field_validator("environment")
    @classmethod
    def _validate_environment(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = _clean_id(value, field_name="alias config environment")
        if not ALIAS_ENVIRONMENT_PATTERN.fullmatch(cleaned):
            raise ValueError("alias config environment must be an uppercase shell identifier")
        return cleaned

    @model_validator(mode="after")
    def _validate_source(self) -> "AnalysisCommandAliasConfigValue":
        if (self.value is None) == (self.environment is None):
            raise ValueError("alias config must set exactly one of value or environment")
        return self

    def render(self) -> str:
        """Render one shell-safe DayOA config token."""

        if self.environment is not None:
            return f'"{self.key}=${self.environment}"'
        return shlex.quote(f"{self.key}={self.value}")


class AnalysisCommandAliasExtension(BaseModel):
    """Declarative additions to a base DayOA command."""

    model_config = ConfigDict(extra="forbid")

    targets: List[str] = Field(default_factory=list)
    config: List[AnalysisCommandAliasConfigValue] = Field(default_factory=list)

    @field_validator("targets")
    @classmethod
    def _validate_targets(cls, values: List[str]) -> List[str]:
        cleaned = [_clean_id(value, field_name="alias extension target") for value in values]
        if any(not ALIAS_TARGET_PATTERN.fullmatch(value) for value in cleaned):
            raise ValueError("alias extension targets must be simple DayOA target names")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("alias extension targets must be unique")
        return cleaned

    @model_validator(mode="after")
    def _validate_extension(self) -> "AnalysisCommandAliasExtension":
        if not self.targets and not self.config:
            raise ValueError("alias extension must add at least one target or config value")
        keys = [item.key for item in self.config]
        if len(set(keys)) != len(keys):
            raise ValueError("alias extension config keys must be unique")
        return self


class AnalysisCommandAliasReplacement(BaseModel):
    """Complete command-bearing fields for an independent alias command."""

    model_config = ConfigDict(extra="forbid")

    targets: List[str]
    dy_command: str
    dryrun_dy_command: str

    @field_validator("targets")
    @classmethod
    def _validate_targets(cls, values: List[str]) -> List[str]:
        cleaned = [_clean_id(value, field_name="alias replacement target") for value in values]
        if any(not ALIAS_TARGET_PATTERN.fullmatch(value) for value in cleaned):
            raise ValueError("alias replacement targets must be simple DayOA target names")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("alias replacement targets must be unique")
        return cleaned

    @field_validator("dy_command", "dryrun_dy_command")
    @classmethod
    def _validate_commands(cls, value: str) -> str:
        return _clean_id(value, field_name="alias replacement command")


class AnalysisCommandAlias(BaseModel):
    """A one-hop alias to a direct command in the same DYEC build."""

    model_config = ConfigDict(extra="forbid")

    command_id: str
    alias_of: str
    metadata_overrides: AnalysisCommandAliasMetadata = Field(
        default_factory=AnalysisCommandAliasMetadata
    )
    extend: Optional[AnalysisCommandAliasExtension] = None
    replace: Optional[AnalysisCommandAliasReplacement] = None

    @field_validator("command_id", "alias_of")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        return _clean_id(value, field_name="alias id")

    @model_validator(mode="after")
    def _validate_mode(self) -> "AnalysisCommandAlias":
        if self.extend is not None and self.replace is not None:
            raise ValueError("alias extend and replace modes are mutually exclusive")
        if (
            self.extend is None
            and self.replace is None
            and not self.metadata_overrides.model_fields_set
        ):
            raise ValueError("alias must override metadata, extend the base, or replace commands")
        return self


def _shell_words(command: str) -> tuple[List[re.Match[str]], List[str]]:
    matches = list(SHELL_WORD_PATTERN.finditer(command))
    try:
        values = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ValueError(f"alias base command is not valid shell syntax: {exc}") from exc
    if len(matches) != len(values):
        raise ValueError("alias base command uses unsupported shell token syntax")
    return matches, values


def _render_extended_command(command: str, extension: AnalysisCommandAliasExtension) -> str:
    """Insert declarative target/config values into one strict ``dy-r`` command."""

    matches, values = _shell_words(command)
    dy_r_indices = [index for index, value in enumerate(values) if value == "dy-r"]
    if len(dy_r_indices) != 1:
        raise ValueError("alias extension requires exactly one dy-r token in the base command")
    dy_r_index = dy_r_indices[0]
    target_end = dy_r_index + 1
    while target_end < len(values) and not values[target_end].startswith("-"):
        target_end += 1

    insertions: List[tuple[int, List[str]]] = []
    if extension.targets:
        existing_targets = set(values[dy_r_index + 1 : target_end])
        duplicates = sorted(existing_targets.intersection(extension.targets))
        if duplicates:
            raise ValueError("alias extension repeats base target(s): " + ", ".join(duplicates))
        target_position = matches[target_end].start() if target_end < len(matches) else len(command)
        insertions.append((target_position, list(extension.targets)))

    if extension.config:
        config_indices = [
            index
            for index, value in enumerate(values[dy_r_index + 1 :], start=dy_r_index + 1)
            if value == "--config"
        ]
        if len(config_indices) != 1:
            raise ValueError(
                "alias config extension requires exactly one --config token in the base command"
            )
        config_index = config_indices[0]
        config_end = config_index + 1
        while config_end < len(values) and not values[config_end].startswith("-"):
            config_end += 1
        existing_keys = {
            value.split("=", 1)[0]
            for value in values[config_index + 1 : config_end]
            if "=" in value
        }
        duplicates = sorted(existing_keys.intersection(item.key for item in extension.config))
        if duplicates:
            raise ValueError("alias extension repeats base config key(s): " + ", ".join(duplicates))
        config_position = matches[config_end].start() if config_end < len(matches) else len(command)
        insertions.append(
            (config_position, [config_value.render() for config_value in extension.config])
        )

    rendered = command
    for position, words in sorted(insertions, key=lambda item: item[0], reverse=True):
        fragment = " ".join(words)
        if position and not rendered[position - 1].isspace():
            fragment = " " + fragment
        if position < len(rendered) and not rendered[position].isspace():
            fragment += " "
        rendered = rendered[:position] + fragment + rendered[position:]
    return rendered


def _resolve_analysis_command_alias(
    alias: AnalysisCommandAlias, base: AnalysisCommand
) -> AnalysisCommand:
    values = base.model_dump(mode="python")
    values.update(alias.metadata_overrides.model_dump(mode="python", exclude_unset=True))
    values["command_id"] = alias.command_id
    if alias.extend is not None:
        repeated_targets = sorted(set(base.targets).intersection(alias.extend.targets))
        if repeated_targets:
            raise ValueError(
                "alias extension repeats base target(s): " + ", ".join(repeated_targets)
            )
        values["targets"] = [*base.targets, *alias.extend.targets]
        values["dy_command"] = _render_extended_command(base.dy_command, alias.extend)
        values["dryrun_dy_command"] = _render_extended_command(base.dryrun_dy_command, alias.extend)
    elif alias.replace is not None:
        values.update(alias.replace.model_dump(mode="python"))
    return AnalysisCommand.model_validate(values)


class DyecBuildCommandSet(BaseModel):
    """Catalog command shapes for one immutable numeric DYEC build."""

    model_config = ConfigDict(extra="forbid")

    repository: str
    dayoa_git_tags: List[str]
    commands: Dict[str, AnalysisCommand]
    aliases: Dict[str, AnalysisCommandAlias] = Field(default_factory=dict)

    @field_validator("dayoa_git_tags")
    @classmethod
    def _validate_dayoa_git_tags(cls, values: List[str]) -> List[str]:
        cleaned = [_clean_id(value, field_name="dayoa_git_tags value") for value in values]
        if not cleaned:
            raise ValueError("dayoa_git_tags must not be empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("dayoa_git_tags values must be unique")
        return cleaned

    @model_validator(mode="after")
    def _validate_commands(self) -> "DyecBuildCommandSet":
        repository = _clean_id(self.repository, field_name="DYEC build repository")
        if not self.commands:
            raise ValueError("DYEC build command set must contain at least one command")
        for command_id, command in self.commands.items():
            cleaned_id = _clean_id(command_id, field_name="DYEC build command id")
            if command.command_id != cleaned_id:
                raise ValueError(
                    f"DYEC build command key {cleaned_id!r} must match command_id "
                    f"{command.command_id!r}"
                )
            if command.repository and command.repository != repository:
                raise ValueError(
                    f"DYEC build command {command.command_id!r} repository "
                    f"{command.repository!r} does not match build repository {repository!r}"
                )
            command.repository = repository
            if command.git_tag not in self.dayoa_git_tags:
                raise ValueError(
                    f"DYEC build command {command.command_id!r} pins DayOA "
                    f"{command.git_tag!r}, which is not declared in dayoa_git_tags"
                )
        alias_command_ids = [alias.command_id for alias in self.aliases.values()]
        if len(set(alias_command_ids)) != len(alias_command_ids):
            raise ValueError("Duplicate DYEC build alias command id")
        direct_ids = set(self.commands)
        alias_ids = set(alias_command_ids)
        duplicate_ids = sorted(direct_ids.intersection(alias_ids))
        if duplicate_ids:
            raise ValueError(
                "Duplicate DYEC build command and alias id: " + ", ".join(duplicate_ids)
            )
        for alias_key, alias in self.aliases.items():
            cleaned_key = _clean_id(alias_key, field_name="DYEC build alias id")
            if alias.command_id != cleaned_key:
                raise ValueError(
                    f"DYEC build alias key {cleaned_key!r} must match command_id "
                    f"{alias.command_id!r}"
                )
            if CROSS_BUILD_ALIAS_PATTERN.match(alias.alias_of):
                raise ValueError(
                    f"DYEC build alias {alias.command_id!r} must not use a cross-build reference"
                )
            if alias.alias_of in alias_ids:
                raise ValueError(
                    f"DYEC build alias {alias.command_id!r} creates an alias chain or cycle; "
                    "alias_of must name a direct same-build command"
                )
            if alias.alias_of not in self.commands:
                raise ValueError(
                    f"DYEC build alias {alias.command_id!r} references missing same-build "
                    f"base command {alias.alias_of!r}"
                )
            resolved = _resolve_analysis_command_alias(alias, self.commands[alias.alias_of])
            if resolved.repository != repository:
                raise ValueError(
                    f"Resolved DYEC build alias {resolved.command_id!r} repository "
                    f"{resolved.repository!r} does not match build repository {repository!r}"
                )
            if resolved.git_tag not in self.dayoa_git_tags:
                raise ValueError(
                    f"Resolved DYEC build alias {resolved.command_id!r} pins DayOA "
                    f"{resolved.git_tag!r}, which is not declared in dayoa_git_tags"
                )
        return self

    def resolved_commands(self) -> Dict[str, AnalysisCommand]:
        """Return direct commands plus one-hop aliases as ordinary commands."""

        resolved = dict(self.commands)
        for alias_id, alias in self.aliases.items():
            resolved[alias_id] = _resolve_analysis_command_alias(
                alias, self.commands[alias.alias_of]
            )
        return resolved

    def to_public_payload(self) -> Dict[str, Any]:
        """Serialize direct command pins with their derived validation state."""

        payload = self.model_dump(mode="json")
        payload["commands"] = {
            command_id: command.to_public_payload()
            for command_id, command in self.commands.items()
        }
        return payload


class RepositoryDefinition(BaseModel):
    """A repository configured for explicit-ref day-clone launches."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = ""
    description: str = ""
    clone_transport: Literal["https", "ssh"]
    auth_mode: Literal["none", "aws_deploy_key"]
    https_url: str
    ssh_url: Optional[str] = None
    default_ref: str
    relative_path: str
    analysis_commands: List[AnalysisCommand] = Field(default_factory=list)

    def to_public_payload(self) -> Dict[str, Any]:
        """Serialize repository commands with their derived validation state."""

        payload = self.model_dump(mode="json")
        payload["analysis_commands"] = [
            command.to_public_payload() for command in self.analysis_commands
        ]
        return payload

    @model_validator(mode="after")
    def _validate_clone_auth(self) -> "RepositoryDefinition":
        if self.auth_mode == "aws_deploy_key":
            if self.clone_transport != "ssh":
                raise ValueError("aws_deploy_key authentication requires clone_transport ssh")
            if not self.ssh_url:
                raise ValueError("aws_deploy_key authentication requires ssh_url")
        return self


class RepositoryCatalog(BaseModel):
    """Complete daylily_pipeline_command_catalog.yaml contract."""

    model_config = ConfigDict(extra="forbid")

    command_catalog_version: int
    default_repository: str
    result_export: Optional[ResultExportGuidance] = None
    input_contracts: Dict[str, InputContractDefinition] = Field(default_factory=dict)
    test_data_locations: List[TestDataLocation] = Field(default_factory=list)
    test_data_profiles: Dict[str, TestDataProfile] = Field(default_factory=dict)
    dyec_builds: Dict[str, DyecBuildCommandSet] = Field(default_factory=dict)
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
        if self.command_catalog_version >= 3 and self.result_export is None:
            raise ValueError("command catalog version 3 requires result_export guidance")
        if self.command_catalog_version >= 4 and not self.dyec_builds:
            raise ValueError("command catalog version 4 requires dyec_builds")
        if self.command_catalog_version >= 5 and CURRENT_DYEC_BUILD not in self.dyec_builds:
            raise ValueError(
                "command catalog version 5 or newer requires the exact current DYEC release snapshot"
            )
        if self.command_catalog_version < 6 and any(
            command_set.aliases for command_set in self.dyec_builds.values()
        ):
            raise ValueError("command catalog aliases require command_catalog_version 6")
        for build_version in self.dyec_builds:
            if str(build_version).startswith("v"):
                raise ValueError("dyec_builds keys must use non-v semver release identifiers")
            _clean_id(build_version, field_name="dyec_builds key")
            if self.command_catalog_version >= 5 and not DYEC_BUILD_VERSION_PATTERN.fullmatch(
                str(build_version)
            ):
                raise ValueError(
                    "dyec_builds keys must be non-v semver release identifiers"
                )
        unknown_contracts = set(self.input_contracts) - INPUT_CONTRACTS
        if unknown_contracts:
            raise ValueError(
                "input_contracts contains unknown contract id(s): "
                + ", ".join(sorted(unknown_contracts))
            )
        location_ids = {location.location_id for location in self.test_data_locations}
        for profile_id, profile in self.test_data_profiles.items():
            _clean_id(profile_id, field_name="test_data_profiles key")
            unknown_locations = set(profile.locations) - location_ids
            if unknown_locations:
                raise ValueError(
                    f"test_data_profile {profile_id!r} references unknown location(s): "
                    + ", ".join(sorted(unknown_locations))
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
                if command.test_data_profile not in self.test_data_profiles:
                    raise ValueError(
                        f"Command {command.command_id!r} references unknown "
                        f"test_data_profile {command.test_data_profile!r}"
                    )
                profile = self.test_data_profiles[command.test_data_profile]
                if command.command_class == "utility" and profile.source_mount_mode != "none":
                    raise ValueError(
                        f"Command {command.command_id!r} is utility but test_data_profile "
                        f"{command.test_data_profile!r} is {profile.source_mount_mode!r}"
                    )
                if (
                    command.command_class == "sample_analysis"
                    and profile.source_mount_mode == "run_dra_required"
                ):
                    raise ValueError(
                        f"Command {command.command_id!r} is sample_analysis but "
                        f"test_data_profile {command.test_data_profile!r} requires a run DRA"
                    )
                if command.command_class == "sample_analysis":
                    if (
                        profile.source_mount_mode == "explicit_run_mounts"
                        and not command.requires_run_mount
                    ):
                        raise ValueError(
                            f"Command {command.command_id!r} uses explicit run mounts but "
                            "does not require them"
                        )
                    if (
                        profile.source_mount_mode != "explicit_run_mounts"
                        and command.requires_run_mount
                    ):
                        raise ValueError(
                            f"Command {command.command_id!r} requires run mounts but "
                            f"test_data_profile {command.test_data_profile!r} is "
                            f"{profile.source_mount_mode!r}"
                        )
                if command.command_class == "run_analysis":
                    if profile.source_mount_mode != "run_dra_required":
                        raise ValueError(
                            f"Command {command.command_id!r} is run_analysis but "
                            f"test_data_profile {command.test_data_profile!r} is "
                            f"{profile.source_mount_mode!r}"
                        )
                    contract = self.input_contracts.get(command.input_contract)
                    source_table = contract.source_table if contract is not None else None
                    required_columns = (
                        set(source_table.required_columns) if source_table is not None else set()
                    )
                    missing_columns = {
                        profile.run_context_source_s3_column,
                        profile.run_context_mount_id_column,
                    } - required_columns
                    if missing_columns:
                        raise ValueError(
                            f"Command {command.command_id!r} uses run DRA profile "
                            f"{command.test_data_profile!r}, but input_contract "
                            f"{command.input_contract!r} is missing required column(s): "
                            + ", ".join(sorted(missing_columns))
                        )
        for build_version, command_set in self.dyec_builds.items():
            for command in command_set.resolved_commands().values():
                if command.repository not in self.repositories:
                    raise ValueError(
                        f"DYEC build {build_version!r} command {command.command_id!r} "
                        f"references unknown repository {command.repository!r}"
                    )
                if (
                    command.input_contract != "none"
                    and command.input_contract not in self.input_contracts
                ):
                    raise ValueError(
                        f"DYEC build {build_version!r} command {command.command_id!r} "
                        f"references unknown input contract {command.input_contract!r}"
                    )
                if command.test_data_profile not in self.test_data_profiles:
                    raise ValueError(
                        f"DYEC build {build_version!r} command {command.command_id!r} "
                        f"references unknown test_data_profile {command.test_data_profile!r}"
                    )
                profile = self.test_data_profiles[command.test_data_profile]
                if (
                    command.command_class == "sample_analysis"
                    and profile.source_mount_mode == "run_dra_required"
                ):
                    raise ValueError(
                        f"DYEC build {build_version!r} command {command.command_id!r} is "
                        "sample_analysis but its profile requires a run DRA"
                    )
                if command.command_class == "sample_analysis":
                    if (
                        profile.source_mount_mode == "explicit_run_mounts"
                        and not command.requires_run_mount
                    ):
                        raise ValueError(
                            f"DYEC build {build_version!r} command {command.command_id!r} "
                            "uses explicit run mounts but does not require them"
                        )
                    if (
                        profile.source_mount_mode != "explicit_run_mounts"
                        and command.requires_run_mount
                    ):
                        raise ValueError(
                            f"DYEC build {build_version!r} command {command.command_id!r} "
                            "requires run mounts without an explicit_run_mounts profile"
                        )
        return self

    def _repository_commands(self) -> List[AnalysisCommand]:
        result: List[AnalysisCommand] = []
        for repo in self.repositories.values():
            result.extend(repo.analysis_commands)
        return result

    def commands(self) -> List[AnalysisCommand]:
        """Return the default command view for this catalog schema."""

        if self.command_catalog_version >= 5:
            return self.commands_for_dyec_build()
        return self._repository_commands()

    def get_command(self, command_id: str) -> AnalysisCommand:
        command_key = _clean_id(command_id, field_name="command_id")
        for command in self.commands():
            if command.command_id == command_key:
                return command
        raise KeyError(f"Unknown analysis command: {command_key}")

    def resolve_dyec_build_key(self, dyec_version: Optional[str] = None) -> str:
        """Resolve an omitted selector to this release's immutable snapshot."""

        return _clean_id(
            dyec_version if dyec_version is not None else CURRENT_DYEC_BUILD,
            field_name="dyec_version",
        )

    def commands_for_dyec_build(self, dyec_version: Optional[str] = None) -> List[AnalysisCommand]:
        """Return the requested immutable DYEC-build command snapshot."""

        build_key = self.resolve_dyec_build_key(dyec_version)
        try:
            build = self.dyec_builds[build_key]
        except KeyError as exc:
            raise KeyError(f"No command eligibility set for DYEC build: {build_key}") from exc
        return list(build.resolved_commands().values())

    def get_command_for_dyec_build(
        self, command_id: str, dyec_version: Optional[str] = None
    ) -> AnalysisCommand:
        """Resolve ``current`` by default or an explicit released-build snapshot."""

        command_key = _clean_id(command_id, field_name="command_id")
        for command in self.commands_for_dyec_build(dyec_version):
            if command.command_id == command_key:
                return command
        raise KeyError(
            "Command "
            f"{command_key!r} is not eligible for DYEC build "
            f"{self.resolve_dyec_build_key(dyec_version)!r}"
        )

    def to_public_payload(self) -> Dict[str, Any]:
        return {
            "command_catalog_version": self.command_catalog_version,
            "default_repository": self.default_repository,
            "input_contracts": {
                key: contract.model_dump(mode="json")
                for key, contract in self.input_contracts.items()
            },
            "test_data_locations": [
                location.model_dump(mode="json") for location in self.test_data_locations
            ],
            "test_data_profiles": {
                key: profile.model_dump(mode="json")
                for key, profile in self.test_data_profiles.items()
            },
            "dyec_builds": {
                build_version: command_set.to_public_payload()
                for build_version, command_set in self.dyec_builds.items()
            },
            "repositories": {
                repo_key: repo.to_public_payload()
                for repo_key, repo in self.repositories.items()
            },
            "commands": [command.to_public_payload() for command in self.commands()],
        }


def default_catalog_path() -> Path:
    return resource_path("config/daylily_pipeline_command_catalog.yaml")


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
    migrated.setdefault(
        "test_data_profiles",
        {
            "legacy_v1": {
                "description": "Legacy v1 command profile created during catalog migration.",
                "source_mount_mode": "none",
                "locations": [],
                "source_notes": [],
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
        repo.setdefault("clone_transport", "https")
        repo.setdefault("auth_mode", "none")
        commands = repo.get("analysis_commands")
        if isinstance(commands, list):
            migrated_commands = []
            for command_value in commands:
                if not isinstance(command_value, dict):
                    migrated_commands.append(command_value)
                    continue
                command = dict(command_value)
                command["command_class"] = "sample_analysis"
                command["type"] = "dev"
                command["validated_version"] = str(repo.get("default_ref", "main"))
                command["test_data_profile"] = "legacy_v1"
                command["input_contract"] = "sample_manifest"
                command["requires_staging"] = True
                command["requires_run_mount"] = False
                command["runtime_parameters"] = {}
                command.setdefault("compatible_cluster_types", ["daywgs"])
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
