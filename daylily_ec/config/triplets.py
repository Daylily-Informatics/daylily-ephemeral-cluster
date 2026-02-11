"""Config triplet loading, resolution, and write-back.

This module is the Python equivalent of the Bash triplet helpers in
``bin/daylily-create-ephemeral-cluster`` (lines 388–970).  It provides:

- :func:`load_config` — parse a daylily config YAML into a :class:`ConfigFile`
- :func:`ensure_required_keys` — add missing required keys as PROMPTUSER triplets
- :func:`should_auto_apply` — auto-select decision matching Bash exactly
- :func:`resolve_value` — get the effective value for a key
- :func:`get_effective_default` — default cascade: config → template_defaults → fallback
- :func:`write_config` — serialize back to YAML (preserving triplet list format)
- :func:`write_next_run_template` — write a next-run template with USESETVALUE actions
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

from daylily_ec.config.models import (
    ConfigFile,
    EphemeralClusterConfig,
    REQUIRED_CONFIG_KEYS,
    Triplet,
)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_config(path: str | Path) -> ConfigFile:
    """Load and parse a daylily config YAML file.

    Handles the ``ephemeral_cluster.config`` section where each key is a
    triplet in string, list, or map format.

    Returns a fully normalized :class:`ConfigFile`.
    """
    path = Path(path)
    raw: Dict[str, Any] = {}
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

    ec_raw = raw.get("ephemeral_cluster", {}) or {}
    config_raw = ec_raw.get("config", {}) or {}
    template_defaults_raw = ec_raw.get("template_defaults", {}) or {}

    # Parse each config value through the Triplet model (handles all formats)
    triplets: Dict[str, Triplet] = {}
    for key, val in config_raw.items():
        triplets[key] = Triplet.model_validate(val)

    # Normalize template_defaults values
    td: Dict[str, str] = {}
    for key, val in template_defaults_raw.items():
        if val is not None and str(val) not in ("null", "None", "__MISSING__"):
            td[key] = str(val)

    return ConfigFile(
        ephemeral_cluster=EphemeralClusterConfig(
            config=triplets,
            template_defaults=td,
        )
    )


def ensure_required_keys(cfg: ConfigFile) -> bool:
    """Add missing required keys as ``[PROMPTUSER, "", ""]`` triplets.

    Returns ``True`` if any keys were added.
    """
    added = False
    for key in REQUIRED_CONFIG_KEYS:
        if key not in cfg.ephemeral_cluster.config:
            cfg.ephemeral_cluster.config[key] = Triplet(
                action="PROMPTUSER", default_value="", set_value=""
            )
            added = True
    return added


# ---------------------------------------------------------------------------
# Auto-select logic (exact parity with Bash ``should_auto_apply_config_value``)
# ---------------------------------------------------------------------------

def is_auto_select_disabled() -> bool:
    """Check if ``DAY_DISABLE_AUTO_SELECT`` is set to ``"1"``."""
    return os.environ.get("DAY_DISABLE_AUTO_SELECT", "") == "1"


def has_effective_set_value(set_value: str) -> bool:
    """True if *set_value* is non-empty and not ``PROMPTUSER``."""
    return bool(set_value) and set_value != "PROMPTUSER"


def should_auto_apply(action: str, set_value: str) -> bool:
    """Decide whether to auto-apply a config value.

    Matches Bash ``should_auto_apply_config_value`` exactly:

    1. If ``DAY_DISABLE_AUTO_SELECT=1`` → **False** (always prompt)
    2. If ``action == "USESETVALUE"`` and *set_value* is non-empty → **True**
    3. If *set_value* is non-empty and not ``"PROMPTUSER"`` → **True**
    4. Otherwise → **False**
    """
    if is_auto_select_disabled():
        return False
    if action == "USESETVALUE" and set_value:
        return True
    if has_effective_set_value(set_value):
        return True
    return False


def resolve_value(triplet: Triplet) -> str:
    """Return the auto-selected value, or empty string if prompting needed.

    Equivalent to Bash ``get_action_set_or_empty``.
    """
    if should_auto_apply(triplet.action, triplet.set_value):
        return triplet.set_value
    return ""


def get_effective_default(
    cfg: ConfigFile, key: str, fallback: str = ""
) -> str:
    """Return the effective default for *key*.

    Cascade: ``config[key].default_value`` → ``template_defaults[key]`` → *fallback*.
    """
    ec = cfg.ephemeral_cluster
    triplet = ec.config.get(key)
    if triplet and triplet.default_value:
        return triplet.default_value
    td_val = ec.template_defaults.get(key, "")
    if td_val:
        return td_val
    return fallback


# ---------------------------------------------------------------------------
# Write-back
# ---------------------------------------------------------------------------

def write_config(cfg: ConfigFile, path: str | Path) -> None:
    """Serialize *cfg* back to YAML at *path*, using list triplet format."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {"ephemeral_cluster": {"config": {}}}
    for key, triplet in cfg.ephemeral_cluster.config.items():
        data["ephemeral_cluster"]["config"][key] = triplet.to_list()

    if cfg.ephemeral_cluster.template_defaults:
        data["ephemeral_cluster"]["template_defaults"] = dict(
            cfg.ephemeral_cluster.template_defaults
        )

    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=None, sort_keys=False)


def write_next_run_template(
    cfg: ConfigFile,
    final_values: Dict[str, str],
    dest: str | Path,
) -> Path:
    """Write a next-run triplet template with resolved values.

    For each key:
    - If auto-select is **not** disabled, action becomes ``USESETVALUE``
    - ``set_value`` is replaced with the final resolved value

    Matches Bash ``write_next_run_triplet_template``.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    out_data: Dict[str, Any] = {"ephemeral_cluster": {"config": {}}}
    for key, triplet in cfg.ephemeral_cluster.config.items():
        next_action = triplet.action
        if not is_auto_select_disabled():
            next_action = "USESETVALUE"
        dval = triplet.default_value
        sval = final_values.get(key, triplet.set_value)
        out_data["ephemeral_cluster"]["config"][key] = [next_action, dval, sval]

    if cfg.ephemeral_cluster.template_defaults:
        out_data["ephemeral_cluster"]["template_defaults"] = dict(
            cfg.ephemeral_cluster.template_defaults
        )

    with open(dest, "w", encoding="utf-8") as fh:
        yaml.dump(out_data, fh, default_flow_style=None, sort_keys=False)

    return dest

