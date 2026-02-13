"""Pydantic models for daylily ephemeral cluster configuration.

Defines the data structures for:
- Individual triplets (action, default_value, set_value)
- The full ephemeral_cluster config section
- Template defaults
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field, model_validator


class TripletAction(str, Enum):
    """Valid actions for a config triplet."""

    PROMPTUSER = "PROMPTUSER"
    USESETVALUE = "USESETVALUE"


class Triplet(BaseModel):
    """A single config triplet: [action, default_value, set_value].

    Supports three input formats (matching Bash ``parse_triplet_for_key``):
    - **String**: ``"PROMPTUSER"`` → action only, default and set are empty
    - **List**: ``["USESETVALUE", "default", "value"]`` → positional
    - **Map**: ``{action: ..., default_value: ..., set_value: ...}`` → named
    """

    action: str = Field(default="PROMPTUSER")
    default_value: str = Field(default="")
    set_value: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, data: Any) -> Any:
        """Accept string, list, or dict input and normalize to dict."""
        if isinstance(data, str):
            return {"action": data or "PROMPTUSER", "default_value": "", "set_value": ""}
        if isinstance(data, (list, tuple)):
            action = (data[0] if len(data) > 0 else "PROMPTUSER") or "PROMPTUSER"
            default = (data[1] if len(data) > 1 else "") or ""
            setv = (data[2] if len(data) > 2 else "") or ""
            return {"action": str(action), "default_value": str(default), "set_value": str(setv)}
        if isinstance(data, dict):
            action = data.get("action") or "PROMPTUSER"
            default = data.get("default_value") or ""
            setv = data.get("set_value") or ""
            return {"action": str(action), "default_value": str(default), "set_value": str(setv)}
        # None / null → empty PROMPTUSER triplet
        if data is None:
            return {"action": "PROMPTUSER", "default_value": "", "set_value": ""}
        return data

    @model_validator(mode="after")
    def _normalize_components(self) -> "Triplet":
        """Normalize values: null/None → '', True/False → 'true'/'false'."""
        self.action = _normalize(self.action) or "PROMPTUSER"
        self.default_value = _normalize(self.default_value)
        self.set_value = _normalize(self.set_value)
        return self

    def to_list(self) -> list:
        """Serialize back to ``[action, default_value, set_value]``."""
        return [self.action, self.default_value, self.set_value]


class EphemeralClusterConfig(BaseModel):
    """Top-level model for the config YAML file.

    Structure::

        ephemeral_cluster:
          config:
            <key>: <triplet>
          template_defaults:
            <key>: <string>
    """

    config: Dict[str, Triplet] = Field(default_factory=dict)
    template_defaults: Dict[str, str] = Field(default_factory=dict)


class ConfigFile(BaseModel):
    """Root model wrapping ``ephemeral_cluster:`` key."""

    ephemeral_cluster: EphemeralClusterConfig = Field(
        default_factory=EphemeralClusterConfig
    )


# ---------------------------------------------------------------------------
# Required config keys — must exist in the config section.  If missing,
# ``ensure_required_keys`` adds them as ``[PROMPTUSER, "", ""]``.
# ---------------------------------------------------------------------------

REQUIRED_CONFIG_KEYS: list[str] = [
    "allowed_budget_users",
    "auto_delete_fsx",
    "budget_amount",
    "budget_email",
    "cluster_name",
    "cluster_template_yaml",
    "delete_local_root",
    "enable_detailed_monitoring",
    "enforce_budget",
    "fsx_fs_size",
    "global_allowed_budget_users",
    "global_budget_amount",
    "headnode_instance_type",
    "heartbeat_email",
    "heartbeat_schedule",
    "heartbeat_scheduler_role_arn",
    "iam_policy_arn",
    "max_count_128I",
    "max_count_192I",
    "max_count_8I",
    "private_subnet_id",
    "public_subnet_id",
    "s3_bucket_name",
    "spot_instance_allocation_strategy",
    "ssh_key_name",
]


# ---------------------------------------------------------------------------
# Normalization helper (matches Bash ``normalize_config_component``)
# ---------------------------------------------------------------------------

def _normalize(value: str) -> str:
    """Normalize a single config component string.

    - ``"null"`` / ``"None"`` → ``""``
    - ``"True"`` / ``"TRUE"`` → ``"true"``
    - ``"False"`` / ``"FALSE"`` → ``"false"``
    """
    if value in ("null", "None"):
        return ""
    if value in ("True", "TRUE"):
        return "true"
    if value in ("False", "FALSE"):
        return "false"
    return value

