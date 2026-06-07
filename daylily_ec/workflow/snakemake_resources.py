"""Snakemake resource argument helpers."""

from __future__ import annotations

import shlex


DEFAULT_JOB_MAX_RUNTIME_MINUTES = 100


def validate_job_max_runtime_minutes(value: int) -> int:
    """Validate a default Snakemake job runtime cap in minutes."""
    if value < 0:
        raise ValueError("--max-runtime-minutes must be >= 0.")
    return value


def has_default_time_resource(command: str) -> bool:
    """Return true when a command already sets a default Snakemake time resource."""
    tokens = shlex.split(command)
    for index, token in enumerate(tokens):
        if token == "--default-resources":
            for resource_token in tokens[index + 1 :]:
                if resource_token.startswith("-"):
                    break
                if any(part.startswith("time=") for part in resource_token.split()):
                    return True
        elif token.startswith("--default-resources="):
            resource_text = token.split("=", 1)[1]
            if any(part.startswith("time=") for part in resource_text.split()):
                return True
    return False


def append_default_job_runtime(command: str, *, max_runtime_minutes: int) -> str:
    """Append a default Snakemake time resource unless the command already has one."""
    validate_job_max_runtime_minutes(max_runtime_minutes)
    if max_runtime_minutes == 0 or has_default_time_resource(command):
        return command
    return f"{command} --default-resources time={max_runtime_minutes}"
