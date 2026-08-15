"""Project-local invocation context for the DYEC CLI.

The context deliberately lives only in the invoking directory.  It is not an
environment-variable shim and it never mutates the caller's environment.
"""

from __future__ import annotations

import functools
import inspect
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar, get_args, get_origin

import click
import typer
import yaml

CONTEXT_FILENAME = ".dyec.config.yaml"
CONTEXT_FIELDS = (
    "aws_profile",
    "aws_region",
    "aws_region_az",
    "cluster_admin_email",
)
_PARAMETER_FIELDS = {
    "profile": "aws_profile",
    "region": "aws_region",
    "region_az": "aws_region_az",
    "regions": "aws_region",
}
_MULTIPLE_PARAMETERS = {"regions"}
_REQUIRED_ATTRIBUTE = "_dyec_context_required"
_FIELD_ATTRIBUTE = "_dyec_context_field"
_FALLBACK_ATTRIBUTE = "_dyec_context_fallback"
_MISSING = object()
F = TypeVar("F", bound=Callable[..., Any])


class ContextConfigError(click.UsageError):
    """Raised when the project-local DYEC context is invalid."""


def context_path(cwd: Path | None = None) -> Path:
    """Return the only supported local context path."""

    base = cwd if cwd is not None else Path.cwd()
    return base / CONTEXT_FILENAME


def _normalise_value(
    value: Any,
    *,
    field: str,
    allow_none: bool = False,
) -> str | None:
    if value is None:
        if allow_none:
            return None
        raise ContextConfigError(f"{CONTEXT_FILENAME} field {field!r} must be a string.")
    if not isinstance(value, str):
        raise ContextConfigError(f"{CONTEXT_FILENAME} field {field!r} must be a string.")
    cleaned = value.strip()
    return cleaned or None


@dataclass(frozen=True)
class LocalContext:
    """Validated values loaded from one project-local context file."""

    path: Path
    aws_profile: str | None = None
    aws_region: str | None = None
    aws_region_az: str | None = None
    cluster_admin_email: str | None = None

    @property
    def present(self) -> bool:
        return self.path.exists()

    def value(self, field: str) -> str | None:
        if field not in CONTEXT_FIELDS:
            raise ValueError(f"Unknown DYEC local context field: {field}")
        return getattr(self, field)

    def populated_values(self) -> dict[str, str]:
        return {
            field: value for field in CONTEXT_FIELDS if (value := self.value(field)) is not None
        }


def load_local_context(cwd: Path | None = None) -> LocalContext:
    """Load the strict local context, treating blank values as absent."""

    path = context_path(cwd)
    if path.is_symlink():
        raise ContextConfigError(f"{path} must be a regular file.")
    if not path.exists():
        return LocalContext(path=path)
    if not path.is_file():
        raise ContextConfigError(f"{path} must be a regular file.")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContextConfigError(f"Unable to read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ContextConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ContextConfigError(f"{path} must contain a mapping of DYEC context fields.")
    unknown = sorted(set(raw) - set(CONTEXT_FIELDS))
    if unknown:
        raise ContextConfigError(f"{path} contains unsupported field(s): {', '.join(unknown)}.")
    values = {
        field: _normalise_value(raw[field], field=field) if field in raw else None
        for field in CONTEXT_FIELDS
    }
    return LocalContext(path=path, **values)


def _write_values(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{CONTEXT_FILENAME}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            yaml.safe_dump(values, handle, default_flow_style=False, sort_keys=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def update_local_context(
    *,
    updates: dict[str, str | None],
    cwd: Path | None = None,
) -> tuple[LocalContext, tuple[str, ...], bool]:
    """Apply supplied context fields and return context, affected fields, and presence."""

    unknown = sorted(set(updates) - set(CONTEXT_FIELDS))
    if unknown:
        raise ValueError(f"Unknown DYEC local context field(s): {', '.join(unknown)}")
    current = load_local_context(cwd)
    values = current.populated_values()
    affected: list[str] = []
    for field, supplied_value in updates.items():
        normalised = _normalise_value(
            supplied_value,
            field=field,
            allow_none=True,
        )
        affected.append(field)
        if normalised is None:
            values.pop(field, None)
        else:
            values[field] = normalised
    if values:
        _write_values(current.path, values)
    elif current.path.exists():
        current.path.unlink()
    updated = load_local_context(cwd)
    return updated, tuple(affected), updated.present


def clear_local_context(
    *,
    fields: tuple[str, ...],
    cwd: Path | None = None,
) -> tuple[LocalContext, tuple[str, ...], bool]:
    """Clear selected fields, or all fields when no selectors were supplied."""

    selected = fields or CONTEXT_FIELDS
    return update_local_context(
        updates={field: None for field in selected},
        cwd=cwd,
    )


def context_option(
    field: str,
    default: str | None,
    *param_decls: str,
    required: bool = False,
    fallback: object = _MISSING,
    **kwargs: Any,
) -> Any:
    """Create a Typer option annotated for local-context resolution."""

    if field not in CONTEXT_FIELDS:
        raise ValueError(f"Unknown DYEC local context field: {field}")
    option = typer.Option(default, *param_decls, **kwargs)
    setattr(option, _FIELD_ATTRIBUTE, field)
    setattr(option, _REQUIRED_ATTRIBUTE, required)
    setattr(option, _FALLBACK_ATTRIBUTE, fallback)
    return option


def _option_hint(option: Any, parameter_name: str) -> str:
    for declaration in getattr(option, "param_decls", ()):
        if declaration.startswith("--"):
            return declaration
    return "--" + parameter_name.replace("_", "-")


def _is_multiple_parameter(parameter: inspect.Parameter) -> bool:
    """Return whether a CLI parameter receives a sequence of option values."""

    if parameter.name in _MULTIPLE_PARAMETERS:
        return True
    annotation = parameter.annotation
    if isinstance(annotation, str):
        return any(token in annotation for token in ("List[", "list[", "Tuple[", "tuple["))
    origin = get_origin(annotation)
    if origin in (list, tuple, set):
        return True
    return any(get_origin(argument) in (list, tuple, set) for argument in get_args(annotation))


def _context_specs(
    callback: Callable[..., Any],
) -> tuple[tuple[str, str, bool, object, Any, bool], ...]:
    specs: list[tuple[str, str, bool, object, Any, bool]] = []
    for parameter in inspect.signature(callback).parameters.values():
        option = parameter.default
        field = getattr(option, _FIELD_ATTRIBUTE, _PARAMETER_FIELDS.get(parameter.name))
        if field not in CONTEXT_FIELDS:
            continue
        specs.append(
            (
                parameter.name,
                field,
                bool(getattr(option, _REQUIRED_ATTRIBUTE, False)),
                getattr(option, _FALLBACK_ATTRIBUTE, _MISSING),
                option,
                _is_multiple_parameter(parameter),
            )
        )
    return tuple(specs)


def contextualize_callback(callback: F) -> F:
    """Inject project-local context into a registered CLI callback."""

    signature = inspect.signature(callback)
    specs = _context_specs(callback)
    if not specs:
        return callback

    @functools.wraps(callback)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        bound = signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        context = load_local_context()
        for parameter_name, field, required, fallback, option, multiple in specs:
            supplied = bound.arguments.get(parameter_name)
            if multiple:
                if supplied is None:
                    value: Any = None
                else:
                    supplied_values = tuple(supplied)
                    value = [
                        normalised
                        for raw_value in supplied_values
                        if (
                            normalised := _normalise_value(
                                raw_value,
                                field=field,
                                allow_none=True,
                            )
                        )
                        is not None
                    ]
                if not value:
                    context_value = context.value(field)
                    value = [context_value] if context_value is not None else None
                if not value and fallback is not _MISSING:
                    value = fallback
            else:
                value = _normalise_value(supplied, field=field, allow_none=True)
                if value is None:
                    value = context.value(field)
                if value is None and fallback is not _MISSING:
                    value = fallback
            if required and not value:
                raise click.MissingParameter(
                    param_type="option",
                    param_hint=_option_hint(option, parameter_name),
                )
            bound.arguments[parameter_name] = value
        return callback(*bound.args, **bound.kwargs)

    wrapped.__signature__ = signature
    wrapped.__dyec_context_specs__ = specs
    return wrapped  # type: ignore[return-value]
