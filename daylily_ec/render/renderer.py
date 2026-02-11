"""YAML template renderer — replaces ``${REGSUB_*}`` tokens.

This module is the Python equivalent of:

* ``bin/other/regsub_yaml.sh`` (Perl regex substitution)
* ``write_init_template_yaml()`` in the Bash monolith (``envsubst``)

It performs **text-level** token replacement so YAML key ordering and
comments are preserved byte-for-byte across runs.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Tuple

# ── constants ────────────────────────────────────────────────────────

#: All 26 substitution keys recognised by the Bash ``REG_SUBSTITUTIONS``
#: associative array (lines 2396-2426 of the monolith).
ALL_SUBSTITUTION_KEYS: FrozenSet[str] = frozenset(
    {
        "REGSUB_REGION",
        "REGSUB_PUB_SUBNET",
        "REGSUB_KEYNAME",
        "REGSUB_S3_BUCKET_INIT",
        "REGSUB_S3_BUCKET_NAME",
        "REGSUB_S3_IAM_POLICY",
        "REGSUB_PRIVATE_SUBNET",
        "REGSUB_S3_BUCKET_REF",
        "REGSUB_XMR_MINE",
        "REGSUB_XMR_POOL_URL",
        "REGSUB_XMR_WALLET",
        "REGSUB_FSX_SIZE",
        "REGSUB_DETAILED_MONITORING",
        "REGSUB_CLUSTER_NAME",
        "REGSUB_USERNAME",
        "REGSUB_PROJECT",
        "REGSUB_DELETE_LOCAL_ROOT",
        "REGSUB_SAVE_FSX",
        "REGSUB_ENFORCE_BUDGET",
        "REGSUB_AWS_ACCOUNT_ID",
        "REGSUB_ALLOCATION_STRATEGY",
        "REGSUB_DAYLILY_GIT_DEETS",
        "REGSUB_MAX_COUNT_8I",
        "REGSUB_MAX_COUNT_128I",
        "REGSUB_MAX_COUNT_192I",
        "REGSUB_HEADNODE_INSTANCE_TYPE",
        "REGSUB_HEARTBEAT_EMAIL",
        "REGSUB_HEARTBEAT_SCHEDULE",
        "REGSUB_HEARTBEAT_SCHEDULER_ROLE_ARN",
    },
)

#: Minimum required keys — the renderer will raise if any are absent.
REQUIRED_KEYS: FrozenSet[str] = frozenset(
    {
        "REGSUB_REGION",
        "REGSUB_PUB_SUBNET",
        "REGSUB_PRIVATE_SUBNET",
        "REGSUB_CLUSTER_NAME",
    },
)

#: Default config directory (matches Bash: ``~/.config/daylily``).
CONFIG_DIR: Path = Path.home() / ".config" / "daylily"


# ── public API ───────────────────────────────────────────────────────


def render_template(
    template_text: str,
    substitutions: Dict[str, str],
    *,
    required_keys: Optional[FrozenSet[str]] = None,
) -> str:
    """Replace all ``${REGSUB_*}`` tokens in *template_text*.

    Parameters
    ----------
    template_text:
        Raw template content (e.g. from ``config/day_cluster/prod_cluster.yaml``).
    substitutions:
        Mapping of key → value.  Keys should include the ``REGSUB_`` prefix
        (e.g. ``{"REGSUB_REGION": "us-west-2", ...}``).
    required_keys:
        Set of keys that **must** be present in *substitutions* with a
        non-empty value.  Defaults to :data:`REQUIRED_KEYS`.

    Returns
    -------
    str
        Template text with every ``${KEY}`` replaced by its value.

    Raises
    ------
    ValueError
        If a required key is missing or has an empty value.
    """
    if required_keys is None:
        required_keys = REQUIRED_KEYS

    # ── validate required keys ───────────────────────────────────
    missing: List[str] = sorted(
        k for k in required_keys if not substitutions.get(k)
    )
    if missing:
        raise ValueError(
            f"Missing required substitution key(s): {', '.join(missing)}"
        )

    # ── deterministic replacement order (sorted keys) ────────────
    result = template_text
    for key in sorted(substitutions):
        token = "${" + key + "}"
        result = result.replace(token, substitutions[key])
    return result


def write_init_artifacts(
    cluster_name: str,
    timestamp: str,
    template_path: str,
    substitutions: Dict[str, str],
    *,
    config_dir: Optional[Path] = None,
    required_keys: Optional[FrozenSet[str]] = None,
) -> Tuple[str, str]:
    """Copy template and write rendered init-template YAML.

    Produces two files that mirror the Bash behaviour:

    1. ``<cluster>_cluster_<ts>.yaml.init`` — **raw** template copy
    2. ``<cluster>_init_template_<ts>.yaml`` — ``${REGSUB_*}`` tokens
       replaced

    Parameters
    ----------
    cluster_name:
        Cluster identifier (e.g. ``prod``).
    timestamp:
        Timestamp string (e.g. ``20260211140000``).
    template_path:
        Filesystem path to the source template YAML.
    substitutions:
        Substitution dict passed through to :func:`render_template`.
    config_dir:
        Override for the output directory (default ``~/.config/daylily``).
    required_keys:
        Forwarded to :func:`render_template`.

    Returns
    -------
    tuple[str, str]
        ``(yaml_init_path, init_template_path)``

    Raises
    ------
    FileNotFoundError
        If *template_path* does not exist.
    ValueError
        Propagated from :func:`render_template` on missing required keys.
    """
    src = Path(template_path)
    if not src.is_file():
        raise FileNotFoundError(f"Template not found: {template_path}")

    out_dir = config_dir if config_dir is not None else CONFIG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    yaml_init = out_dir / f"{cluster_name}_cluster_{timestamp}.yaml.init"
    init_template = out_dir / f"{cluster_name}_init_template_{timestamp}.yaml"

    # 1. Raw template copy
    shutil.copy2(str(src), str(yaml_init))

    # 2. Rendered init template
    template_text = src.read_text(encoding="utf-8")
    rendered = render_template(
        template_text, substitutions, required_keys=required_keys
    )
    init_template.write_text(rendered, encoding="utf-8")

    return str(yaml_init), str(init_template)

