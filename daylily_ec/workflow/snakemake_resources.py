"""Snakemake resource argument helpers."""

from __future__ import annotations


DEFAULT_JOB_MAX_RUNTIME_MINUTES = 100


def validate_job_max_runtime_minutes(value: int) -> int:
    """Validate a default Snakemake job runtime cap in minutes."""
    if value < 0:
        raise ValueError("--max-runtime-minutes must be >= 0.")
    return value


def append_default_job_runtime(command: str, *, max_runtime_minutes: int) -> str:
    """Validate the legacy runtime option without mutating the DayOA command."""
    validate_job_max_runtime_minutes(max_runtime_minutes)
    return command
