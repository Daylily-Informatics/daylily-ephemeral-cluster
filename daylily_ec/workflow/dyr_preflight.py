from __future__ import annotations

import shlex
from collections.abc import Mapping, Sequence


class DyrPreflightOptionsError(ValueError):
    """Raised when DYEC cannot normalize DayOA preflight producer options."""


PRODUCER_OPTION_DEFAULTS: tuple[tuple[str, bool], ...] = (
    ("--produce-rulegraph", False),
    ("--produce-filegraph", False),
    ("--produce-dag", True),
)
PRODUCER_OPTIONS = frozenset(option for option, _default in PRODUCER_OPTION_DEFAULTS)
DYR_EXECUTABLES = frozenset({"dy-r", "bin/day_run"})
SHELL_CONTROL_TOKENS = frozenset({";", "&&", "||"})


def parse_strict_bool(value: str | bool, *, option: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise DyrPreflightOptionsError(f"{option} requires true or false; got {value!r}")


def split_shell_command(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    return list(lexer)


def join_shell_command(tokens: Sequence[str]) -> str:
    parts: list[str] = []
    for token in tokens:
        if token in SHELL_CONTROL_TOKENS:
            if not parts:
                parts.append(token)
            else:
                parts[-1] = f"{parts[-1]}{token}"
            continue
        parts.append(shlex.quote(token))
    return " ".join(parts)


def normalize_dyr_preflight_options(
    command: str,
    *,
    overrides: Mapping[str, str | bool | None] | None = None,
) -> str:
    tokens = split_shell_command(command)
    override_values: dict[str, bool] = {}
    for option, value in (overrides or {}).items():
        if option not in PRODUCER_OPTIONS:
            raise DyrPreflightOptionsError(f"Unknown dy-r producer option override: {option}")
        if value is not None:
            override_values[option] = parse_strict_bool(value, option=option)

    executor_indexes = [index for index, token in enumerate(tokens) if token in DYR_EXECUTABLES]
    default_values = dict(PRODUCER_OPTION_DEFAULTS)
    if len(executor_indexes) != 1:
        effective_without_command = {
            option: override_values.get(option, default)
            for option, default in PRODUCER_OPTION_DEFAULTS
        }
        if any(effective_without_command.values()):
            raise DyrPreflightOptionsError(
                "Enabled dy-r producer options require exactly one dy-r or bin/day_run invocation; "
                f"found {len(executor_indexes)}"
            )
        return command

    executor_index = executor_indexes[0]
    segment_end = next(
        (
            index
            for index in range(executor_index + 1, len(tokens))
            if tokens[index] in SHELL_CONTROL_TOKENS
        ),
        len(tokens),
    )
    existing: dict[str, bool] = {}
    stripped: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        option = token.split("=", 1)[0]
        if option in PRODUCER_OPTIONS:
            if not (executor_index < index < segment_end):
                raise DyrPreflightOptionsError(
                    f"{option} must belong to the dy-r/bin/day_run command segment"
                )
            if option in existing:
                raise DyrPreflightOptionsError(f"{option} may be specified only once")
            if "=" in token:
                raw_value = token.split("=", 1)[1]
                consumed = 1
            else:
                if index + 1 >= segment_end:
                    raise DyrPreflightOptionsError(f"{option} requires true or false")
                raw_value = tokens[index + 1]
                consumed = 2
            existing[option] = parse_strict_bool(raw_value, option=option)
            index += consumed
            continue
        stripped.append(token)
        index += 1

    stripped_executor_index = next(
        index for index, token in enumerate(stripped) if token in DYR_EXECUTABLES
    )
    stripped_segment_end = next(
        (
            index
            for index in range(stripped_executor_index + 1, len(stripped))
            if stripped[index] in SHELL_CONTROL_TOKENS
        ),
        len(stripped),
    )
    injected: list[str] = []
    for option, default in PRODUCER_OPTION_DEFAULTS:
        value = override_values.get(option, existing.get(option, default_values[option]))
        injected.extend((option, "true" if value else "false"))
    if not existing and stripped_segment_end == len(stripped):
        return command.rstrip() + " " + " ".join(injected)
    normalized = stripped[:stripped_segment_end] + injected + stripped[stripped_segment_end:]
    return join_shell_command(normalized)
