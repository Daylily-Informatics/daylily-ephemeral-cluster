"""Orchestrator for ephemeral cluster creation.

Implements the three-phase execution model:

1. **Preflight** — validate environment, credentials, quotas, resources.
2. **Create** — render YAML, invoke pcluster, attach policies.
3. **Post-create** — budgets, heartbeat, state snapshot.

Preflight gating order (§10.5, strict)::

    1. ToolchainValidator
    2. AWS Identity Validator
    3. IAM Permission Validator
    4. ConfigValidator
    5. QuotaValidator
    6. S3 Bucket Selector
    7. S3 Bucket Validator
    8. KeyPair Selector
    9. Baseline Network Inspector

A single FAIL aborts immediately — no AWS mutations occur.
WARN aborts unless ``--pass-on-warn`` is set.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from daylily_ec.state.models import PreflightReport
from daylily_ec.state.store import write_preflight_report

logger = logging.getLogger(__name__)

# Exit codes per spec
EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILURE = 1
EXIT_AWS_FAILURE = 2
EXIT_DRIFT = 3
EXIT_TOOLCHAIN = 4

# ---------------------------------------------------------------------------
# Preflight gate ordering — validators are registered in spec §10.5 order
# ---------------------------------------------------------------------------

# Each validator is a callable: (PreflightReport) -> PreflightReport
# Validators append CheckResult(s) to report.checks and return the report.
# Populated by later CPs (CP-005 through CP-009).
PreflightStep = Callable[[PreflightReport], PreflightReport]

# Ordered list — filled by register_preflight_step or directly in wire_workflow
_PREFLIGHT_STEPS: List[PreflightStep] = []


def register_preflight_step(step: PreflightStep) -> None:
    """Append a validator to the global preflight pipeline.

    Steps execute in registration order, which **must** match §10.5.
    """
    _PREFLIGHT_STEPS.append(step)


def clear_preflight_steps() -> None:
    """Reset the pipeline (used in tests)."""
    _PREFLIGHT_STEPS.clear()


# ---------------------------------------------------------------------------
# Preflight runner
# ---------------------------------------------------------------------------


def run_preflight(
    report: PreflightReport,
    *,
    pass_on_warn: bool = False,
    steps: Optional[List[PreflightStep]] = None,
) -> PreflightReport:
    """Execute all registered preflight validators in order.

    Args:
        report: Initial report populated with identity/config metadata.
        pass_on_warn: If *True*, WARN results do not abort.
        steps: Override the global ``_PREFLIGHT_STEPS`` (mainly for tests).

    Returns:
        The populated :class:`PreflightReport`.

    Side-effects:
        - Writes the report JSON to ``~/.config/daylily/``.
        - On FAIL: logs remediation and returns (caller should ``sys.exit``).
    """
    pipeline = steps if steps is not None else _PREFLIGHT_STEPS

    for step in pipeline:
        report = step(report)

        # Check for FAIL after each step — abort immediately
        if not report.passed:
            logger.error("Preflight FAIL detected — aborting.")
            for chk in report.failed_checks:
                logger.error("  [FAIL] %s: %s", chk.id, chk.remediation)
            write_preflight_report(report)
            return report

    # All steps passed — check for warnings
    if report.has_warnings and not pass_on_warn:
        logger.warning("Preflight WARN detected and --pass-on-warn not set.")
        for chk in report.warned_checks:
            logger.warning("  [WARN] %s: %s", chk.id, chk.remediation)
        write_preflight_report(report)
        return report

    # Success
    write_preflight_report(report)
    logger.info("Preflight passed — %d checks OK.", len(report.checks))
    return report


def should_abort(report: PreflightReport, *, pass_on_warn: bool = False) -> bool:
    """Return *True* if the report indicates the workflow should stop."""
    if not report.passed:
        return True
    if report.has_warnings and not pass_on_warn:
        return True
    return False


def exit_code_for(report: PreflightReport) -> int:
    """Map a preflight report to the appropriate exit code."""
    if not report.passed:
        return EXIT_VALIDATION_FAILURE
    if report.has_warnings:
        # Only reached when pass_on_warn was False (caller should have aborted)
        return EXIT_VALIDATION_FAILURE
    return EXIT_SUCCESS

