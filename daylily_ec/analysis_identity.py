"""Explicit analysis identity helpers."""

from __future__ import annotations

import re


SAFE_ANALYSIS_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class AnalysisIdentityError(ValueError):
    """Raised when an analysis identity is missing or unsafe."""


def validate_analysis_segment(value: object, *, field_name: str) -> str:
    """Validate one FSx/S3 path segment used in analysis result paths."""
    text = str(value or "").strip()
    if not text:
        raise AnalysisIdentityError(f"{field_name} is required.")
    if not SAFE_ANALYSIS_SEGMENT_RE.fullmatch(text):
        raise AnalysisIdentityError(
            f"{field_name} must be a single path-safe segment matching "
            f"{SAFE_ANALYSIS_SEGMENT_RE.pattern!r}; got {text!r}."
        )
    if text in {".", ".."} or ".." in text or "/" in text or "%" in text:
        raise AnalysisIdentityError(f"{field_name} must not contain path traversal.")
    return text


def analysis_source_path(
    *, executing_entity: object, analysis_id: object, headnode: bool = False
) -> str:
    """Return the analysis root path for an explicit entity and analysis id."""
    entity = validate_analysis_segment(executing_entity, field_name="executing_entity")
    identifier = validate_analysis_segment(analysis_id, field_name="analysis_id")
    prefix = "/fsx/analysis_results" if headnode else "/analysis_results"
    return f"{prefix}/{entity}/{identifier}/"

