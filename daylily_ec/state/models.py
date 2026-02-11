"""Preflight report models — CheckStatus, CheckResult, PreflightReport.

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
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# CheckStatus enum
# ---------------------------------------------------------------------------


class CheckStatus(str, Enum):
    """Outcome of a single preflight check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


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

