"""Explicit cli-core-yo v2 registration helpers for daylily-ec."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Sequence, Tuple

from cli_core_yo.registry import CommandRegistry
from cli_core_yo.spec import CommandPolicy

DAYLILY_EC_RUNTIME_TAG = "daylily-ec-runtime"

EXEMPT = CommandPolicy(runtime_guard="exempt")
EXEMPT_JSON = CommandPolicy(supports_json=True, runtime_guard="exempt")
REQUIRED = CommandPolicy(runtime_guard="required", prereq_tags={DAYLILY_EC_RUNTIME_TAG})
REQUIRED_JSON = CommandPolicy(
    supports_json=True,
    runtime_guard="required",
    prereq_tags={DAYLILY_EC_RUNTIME_TAG},
)
REQUIRED_LONG_RUNNING = CommandPolicy(
    long_running=True,
    runtime_guard="required",
    prereq_tags={DAYLILY_EC_RUNTIME_TAG},
)
REQUIRED_MUTATING_INTERACTIVE = CommandPolicy(
    mutates_state=True,
    interactive=True,
    runtime_guard="required",
    prereq_tags={DAYLILY_EC_RUNTIME_TAG},
)
REQUIRED_MUTATING_LONG_RUNNING = CommandPolicy(
    mutates_state=True,
    long_running=True,
    runtime_guard="required",
    prereq_tags={DAYLILY_EC_RUNTIME_TAG},
)

CommandDef = Tuple[str, Callable[..., Any], CommandPolicy]


def required_policy(
    *,
    supports_json: bool = False,
    mutates_state: bool = False,
    interactive: bool = False,
    long_running: bool = False,
) -> CommandPolicy:
    return CommandPolicy(
        supports_json=supports_json,
        mutates_state=mutates_state,
        interactive=interactive,
        long_running=long_running,
        runtime_guard="required",
        prereq_tags={DAYLILY_EC_RUNTIME_TAG},
    )


def help_text(callback: Callable[..., Any]) -> str:
    """Return deterministic CLI help text from the callback docstring."""
    return inspect.getdoc(callback) or ""


def register_group_commands(
    registry: CommandRegistry,
    group_path: str,
    group_help: str,
    commands: Sequence[CommandDef],
) -> None:
    """Register one explicit command group and its command callbacks."""
    if "/" in group_path:
        parent = registry._resolve_parent(group_path)  # type: ignore[attr-defined]
        if parent is None:
            raise ValueError(f"Unable to create command group {group_path!r}")
        if group_help and parent.help_text and parent.help_text != group_help:
            raise ValueError(f"Conflicting help text for command group {group_path!r}")
        if group_help and not parent.help_text:
            parent.help_text = group_help
    else:
        registry.add_group(group_path, help_text=group_help)
    for name, callback, policy in commands:
        registry.add_command(
            group_path,
            name,
            callback,
            help_text=help_text(callback),
            policy=policy,
        )


def register_root_command(
    registry: CommandRegistry,
    name: str,
    callback: Callable[..., Any],
    policy: CommandPolicy,
) -> None:
    """Register a root-level command callback."""
    registry.add_command(
        None,
        name,
        callback,
        help_text=help_text(callback),
        policy=policy,
    )
