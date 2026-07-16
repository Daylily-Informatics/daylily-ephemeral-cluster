"""Preflight report and state record models (CP-004 / CP-016).

Matches the JSON schema from REFACTOR_SPEC §7::

    {
      "run_id": "YYYYMMDDHHMMSS",
      "cluster_name": "string or null",
      "region": "us-west-2",
      "region_az": "us-west-2b",
      "aws_profile": "profile",
      "account_id": "123456789012",
      "caller_arn": "arn:aws:iam::...:user/...",
      "checks": [
        {
          "id": "toolchain.python",
          "status": "PASS|WARN|FAIL",
          "details": { ... },
          "remediation": "string"
        }
      ]
    }
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# CheckStatus enum
# ---------------------------------------------------------------------------


class CheckStatus(str, Enum):
    """Outcome of a single preflight check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class SlurmAccountingOutcome(str, Enum):
    """User-facing result of the optional post-create accounting stage."""

    OFF = "OFF"
    ENABLED = "ENABLED"
    WARNING = "WARNING"
    RECOVERY_REQUIRED = "RECOVERY REQUIRED"


class SlurmAccountingStage(str, Enum):
    """Bounded stages safe to persist or display without exception details."""

    NOT_STARTED = "not_started"
    OFF = "off"
    SERVICE_PREPARATION = "service_preparation"
    SERVICE_READY = "service_ready"
    FLEET_DESCRIBE = "fleet_describe"
    FLEET_STOP_REQUEST = "fleet_stop_request"
    FLEET_STOPPED = "fleet_stopped"
    UPDATE_DRY_RUN = "update_dry_run"
    UPDATE_SUBMIT = "update_submit"
    UPDATE_WAIT = "update_wait"
    UPDATE_COMPLETE = "update_complete"
    FLEET_RESTORE_REQUEST = "fleet_restore_request"
    FLEET_RESTORED = "fleet_restored"
    HEADNODE_READINESS = "headnode_readiness"
    VERIFICATION = "verification"
    COMPLETE = "complete"


class SlurmAccountingReceipt(BaseModel):
    """Non-secret receipt for the post-create accounting lifecycle.

    Deliberately enumerating every accepted field prevents resolved database
    connection details, private addresses, credentials, or arbitrary exception
    text from entering the persisted receipt.
    """

    model_config = ConfigDict(extra="forbid")

    requested_mode: Literal["on", "off"] = "on"
    create_approval_flag: bool = False
    cost_acknowledgement_flag: bool = False
    service_created: bool = False
    stage_reached: SlurmAccountingStage = SlurmAccountingStage.NOT_STARTED
    update_config_path: str = ""
    terminal_cluster_state: str = ""
    terminal_fleet_state: str = ""
    fleet_restored: Optional[bool] = None
    error_stage: Optional[SlurmAccountingStage] = None
    recovery_required: bool = False
    stack_name: str = ""

    @field_validator("update_config_path")
    @classmethod
    def _validate_update_config_path(cls, value: str) -> str:
        """Accept only a local path, never an endpoint or an ARN."""
        if not value:
            return value
        lowered = value.lower()
        if "://" in value or lowered.startswith("arn:"):
            raise ValueError("update_config_path must be a local filesystem path")
        if "\n" in value or "\r" in value or "\x00" in value:
            raise ValueError("update_config_path contains invalid characters")
        return value

    @field_validator("terminal_cluster_state")
    @classmethod
    def _validate_terminal_cluster_state(cls, value: str) -> str:
        """Accept only bounded ParallelCluster lifecycle states."""
        allowed = {
            "",
            "UNKNOWN",
            "CREATE_COMPLETE",
            "UPDATE_IN_PROGRESS",
            "UPDATE_COMPLETE",
            "UPDATE_FAILED",
            "UPDATE_ROLLBACK_IN_PROGRESS",
            "UPDATE_ROLLBACK_COMPLETE",
            "UPDATE_ROLLBACK_FAILED",
        }
        if value not in allowed:
            raise ValueError("terminal_cluster_state is not a supported lifecycle state")
        return value

    @field_validator("terminal_fleet_state")
    @classmethod
    def _validate_terminal_fleet_state(cls, value: str) -> str:
        """Accept only bounded ParallelCluster compute-fleet states."""
        allowed = {"", "UNKNOWN", "RUNNING", "STOPPED", "START_REQUESTED", "STOP_REQUESTED"}
        if value not in allowed:
            raise ValueError("terminal_fleet_state is not a supported lifecycle state")
        return value

    @field_validator("stack_name")
    @classmethod
    def _validate_stack_name(cls, value: str) -> str:
        """Restrict the optional stack identity to CloudFormation name syntax."""
        if not value:
            return value
        if len(value) > 128 or not value[0].isalpha():
            raise ValueError("stack_name is not a valid CloudFormation stack name")
        if not all(char.isalnum() or char == "-" for char in value):
            raise ValueError("stack_name is not a valid CloudFormation stack name")
        return value


# ---------------------------------------------------------------------------
# CheckResult
# ---------------------------------------------------------------------------


class CheckResult(BaseModel):
    """A single preflight check result.

    Attributes:
        id: Dotted identifier, e.g. ``toolchain.python`` or ``quota.spot_vcpu``.
        status: PASS, WARN, or FAIL.
        details: Arbitrary structured data (version info, quota numbers, etc.).
        remediation: Human-readable fix suggestion.  Empty when status is PASS.
    """

    id: str
    status: CheckStatus
    details: Dict[str, Any] = Field(default_factory=dict)
    remediation: str = ""


# ---------------------------------------------------------------------------
# PreflightReport
# ---------------------------------------------------------------------------


class PreflightReport(BaseModel):
    """Full preflight report written to ``~/.config/daylily/``.

    Serialise with ``model_dump_json(indent=2)`` to get sorted-key JSON
    suitable for deterministic file output.
    """

    run_id: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
    )
    cluster_name: Optional[str] = None
    region: str = ""
    region_az: str = ""
    aws_profile: str = ""
    account_id: str = ""
    caller_arn: str = ""
    checks: List[CheckResult] = Field(default_factory=list)

    # -- convenience helpers ------------------------------------------------

    @property
    def passed(self) -> bool:
        """True when **no** check has FAIL status."""
        return not any(c.status == CheckStatus.FAIL for c in self.checks)

    @property
    def has_warnings(self) -> bool:
        """True when at least one check has WARN status."""
        return any(c.status == CheckStatus.WARN for c in self.checks)

    @property
    def failed_checks(self) -> List[CheckResult]:
        """Return only FAIL checks."""
        return [c for c in self.checks if c.status == CheckStatus.FAIL]

    @property
    def warned_checks(self) -> List[CheckResult]:
        """Return only WARN checks."""
        return [c for c in self.checks if c.status == CheckStatus.WARN]

    def to_sorted_json(self, indent: int = 2) -> str:
        """Serialise with sorted keys for deterministic output."""
        import json

        return json.dumps(
            self.model_dump(mode="json"),
            indent=indent,
            sort_keys=True,
        )


# ---------------------------------------------------------------------------
# StateRecord — persisted per run (CP-016)
# ---------------------------------------------------------------------------


class StateRecord(BaseModel):
    """Per-run state snapshot written to ``~/.config/daylily/state_<cluster>_<ts>.json``.

    Captures every selected resource so that drift detection can later
    compare live AWS state against the recorded baseline.
    """

    run_id: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
    )
    cluster_name: Optional[str] = None
    region: str = ""
    region_az: str = ""
    aws_profile: str = ""
    account_id: str = ""

    # -- Selected resources --------------------------------------------------
    bucket: str = ""
    reference_s3_uri: str = ""
    control_data_s3_uri: str = ""
    stage_s3_uri: str = ""
    export_destination_s3_uri: str = ""
    keypair: str = ""
    public_subnet_id: str = ""
    private_subnet_id: str = ""
    policy_arn: str = ""

    # -- DYEC-owned external FSx --------------------------------------------
    fsx_owner: str = ""
    fsx_lifecycle: str = ""
    fsx_deployment_type: str = ""
    fsx_file_system_id: str = ""
    fsx_security_group_id: str = ""
    fsx_data_repository_association_id: str = ""
    fsx_resource_receipt_path: str = ""

    # -- Budget info ---------------------------------------------------------
    global_budget_name: str = ""
    cluster_budget_name: str = ""

    # -- Heartbeat resources -------------------------------------------------
    heartbeat_topic_arn: str = ""
    heartbeat_schedule_name: str = ""
    heartbeat_role_arn: str = ""
    heartbeat_email: str = ""
    heartbeat_schedule_expression: str = ""

    # -- Slurm accounting ----------------------------------------------------
    slurm_accounting_requested_mode: Literal["on", "off"] = "on"
    slurm_accounting_outcome: Optional[SlurmAccountingOutcome] = None
    slurm_accounting_receipt_path: str = ""
    slurm_accounting_stack_name: str = ""
    slurm_accounting_service_created: bool = False
    slurm_accounting_recovery_required: bool = False

    # -- Generated artifact paths --------------------------------------------
    init_template_path: str = ""
    cluster_yaml_path: str = ""
    resolved_cli_config_path: str = ""
    preflight_report_path: str = ""
    spot_price_summary_path: str = ""
    spot_price_partitions: List[Dict[str, Any]] = Field(default_factory=list)

    # -- CloudFormation ------------------------------------------------------
    cfn_stack_name: str = ""

    def to_sorted_json(self, indent: int = 2) -> str:
        """Serialise with sorted keys for deterministic output."""
        import json

        return json.dumps(
            self.model_dump(mode="json"),
            indent=indent,
            sort_keys=True,
        )
