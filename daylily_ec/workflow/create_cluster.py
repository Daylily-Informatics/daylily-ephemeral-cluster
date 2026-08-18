"""Orchestrator for ephemeral cluster creation (CP-004 / CP-017).

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
    6. S3 Bucket Selector + Validator
    7. Baseline Network Inspector (CFN + subnet + policy)

A single FAIL aborts immediately — no AWS mutations occur.
WARN aborts unless ``--pass-on-warn`` is set.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os as _os
import re
import shlex
import subprocess
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Literal, Optional, cast
from urllib.parse import urlparse

import typer
from botocore.exceptions import ClientError

from daylily_ec import ui
from daylily_ec.aws.idle_cost import (
    IdleClusterCostEstimate,
    IdleCostPricingError,
    estimate_idle_cluster_cost,
)
from daylily_ec.aws.spot_pricing import (
    DEFAULT_GLOBAL_SPOT_MAX_COST,
    DEFAULT_SPOT_COST_LIMIT_PCT,
    DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
    validate_spot_pricing_limits,
)
from daylily_ec.headnode_readiness import validate_headnode_readiness
from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport, StateRecord
from daylily_ec.state.store import (
    write_preflight_report,
    write_resource_receipt,
    write_state_record,
)

logger = logging.getLogger(__name__)

# Exit codes per spec
EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILURE = 1
EXIT_AWS_FAILURE = 2
EXIT_DRIFT = 3
EXIT_TOOLCHAIN = 4

CLUSTER_NAME_MIN_LENGTH = 5
CLUSTER_NAME_MAX_LENGTH = 20
CLUSTER_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
DYEC_RELEASE_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?$")
CLUSTER_NAME_RULE_TEXT = (
    f"DYEC requires cluster names to be {CLUSTER_NAME_MIN_LENGTH}-"
    f"{CLUSTER_NAME_MAX_LENGTH} characters, start with a lowercase letter, "
    "and contain only lowercase letters, digits, and hyphens"
)
DEFAULT_REGIONAL_CLUSTER_CAP = 5
DEFAULT_BUDGET_EMAIL = "contact@lsmc.com"
DEFAULT_COST_CENTER_MONTHLY_CAP_USD = "200"
REGIONAL_CAP_INCREASE_ACK_FLAG = "--acknowledge-regional-cap-increase"
REGIONAL_CAP_RISK_ACK_FLAG = "--acknowledge-regional-cap-risk"

# ---------------------------------------------------------------------------
# Preflight gate ordering — validators are registered in spec §10.5 order
# ---------------------------------------------------------------------------

# Each validator is a callable: (PreflightReport) -> PreflightReport
# Validators append CheckResult(s) to report.checks and return the report.
PreflightStep = Callable[[PreflightReport], PreflightReport]

# Ordered list — filled by register_preflight_step or directly in wire_workflow
_PREFLIGHT_STEPS: List[PreflightStep] = []

CLUSTER_BOOT_CONFIG_FILENAMES = (
    "install_slurm_job_submit_policy.sh",
    "job_submit.lua",
    "post_install_almalinux8_dragen.sh",
    "post_install_rhel8_dragen.sh",
    "post_install_ubuntu_combined.sh",
    "sbatch",
    "sleep_test.sh",
)
BOOT_CONFIG_REFERENCE_COMPAT_LINE = b'reference_compat_root="/fsx/data"'
DEFAULT_CREATE_CLUSTER_TYPE = "intel"
DRAGEN_CLUSTER_TYPE = "dragen"
SENTIEON_SINGLE_CLUSTER_TYPE = "sentieon-single"
SENTIEON_SINGLE_REGION_AZ = "us-west-2c"
SENTIEON_SINGLE_QUEUE_MAX_COUNT = 12
# Pinned from 2026-07-12 read-only EC2 type, AZ-offering, and Linux Spot
# metadata: Intel x86_64, exact queue vCPU, required local NVMe, at least
# 1200 GB instance storage, and no accelerator hardware.
# X-family types are intentionally excluded: their separate 128-vCPU Spot
# quota cannot cover the fixed one-node i96nvme and i128nvme queue maxima.
SENTIEON_SINGLE_QUEUE_INSTANCE_TYPES = {
    "i8": (
        "i3en.2xlarge",
        "i4i.2xlarge",
        "i7i.2xlarge",
        "i7ie.2xlarge",
    ),
    "i96nvme": (
        "c5d.24xlarge",
        "c5d.metal",
        "c6id.24xlarge",
        "c8id.24xlarge",
        "i3en.24xlarge",
        "i3en.metal",
        "i4i.24xlarge",
        "i7i.24xlarge",
        "i7i.metal-24xl",
        "i7ie.24xlarge",
        "i7ie.metal-24xl",
        "m5d.24xlarge",
        "m5d.metal",
        "m5dn.24xlarge",
        "m5dn.metal",
        "m6id.24xlarge",
        "m6idn.24xlarge",
        "m8id.24xlarge",
        "m8idb.24xlarge",
        "m8idn.24xlarge",
        "r5d.24xlarge",
        "r5d.metal",
        "r5dn.24xlarge",
        "r5dn.metal",
        "r6id.24xlarge",
        "r6idn.24xlarge",
        "r8id.24xlarge",
        "r8idb.24xlarge",
        "r8idn.24xlarge",
    ),
    "i128nvme": (
        "c6id.32xlarge",
        "c6id.metal",
        "c8id.32xlarge",
        "i4i.32xlarge",
        "i4i.metal",
        "m6id.32xlarge",
        "m6id.metal",
        "m6idn.32xlarge",
        "m6idn.metal",
        "m8id.32xlarge",
        "m8idb.32xlarge",
        "m8idn.32xlarge",
        "r6id.32xlarge",
        "r6id.metal",
        "r6idn.32xlarge",
        "r6idn.metal",
        "r8id.32xlarge",
        "r8idb.32xlarge",
        "r8idn.32xlarge",
    ),
    "i192nvme": (
        "c8id.48xlarge",
        "c8id.metal-48xl",
        "i7i.48xlarge",
        "i7i.metal-48xl",
        "i7ie.48xlarge",
        "i7ie.metal-48xl",
        "m8id.48xlarge",
        "m8id.metal-48xl",
        "m8idb.48xlarge",
        "m8idn.48xlarge",
        "r8id.48xlarge",
        "r8id.metal-48xl",
        "r8idb.48xlarge",
        "r8idn.48xlarge",
    ),
    "i384nvme": (
        "c8id.96xlarge",
        "c8id.metal-96xl",
        "m8id.96xlarge",
        "m8id.metal-96xl",
        "m8idb.96xlarge",
        "m8idn.96xlarge",
        "r8id.96xlarge",
        "r8id.metal-96xl",
        "r8idb.96xlarge",
        "r8idn.96xlarge",
    ),
}
SENTIEON_SINGLE_QUEUE_RESOURCE_NAMES = {
    "i8": "price8",
    "i96nvme": "price96nvme",
    "i128nvme": "price128nvme",
    "i192nvme": "price192nvme",
    "i384nvme": "price384nvme",
}
CPU_ONLY_SLURM_CUSTOM_SETTINGS = [
    {"JobSubmitPlugins": "lua"},
    {"AccountingStoreFlags": "job_comment"},
    {"PrologFlags": "Alloc"},
]
CREATE_CLUSTER_TYPES = frozenset(
    {"intel", "rhel", DRAGEN_CLUSTER_TYPE, SENTIEON_SINGLE_CLUSTER_TYPE}
)


@dataclass(frozen=True)
class DragenCreateInputs:
    """Private inputs required to render a qualified DRAGEN cluster."""

    backport: Any
    license_secret_arn: str
    license_policy_arn: str


@dataclass(frozen=True)
class DayoaDeployKeyInputs:
    """Explicit AWS resources used for read-only DayOA repository access."""

    secret_arn: str
    policy_arn: str
    region: str


@dataclass(frozen=True)
class DyecDeployKeyInputs:
    """Explicit AWS resources used to bootstrap the private DYEC repository."""

    secret_arn: str
    policy_arn: str
    region: str


@dataclass(frozen=True)
class HeadnodeRepoSpec:
    url: str
    ref: str


@dataclass(frozen=True)
class RegionalClusterCapDecision:
    """Projected regional ParallelCluster count for one create request."""

    effective_cap: int
    current_count: int
    projected_count: int
    requested_name_present: bool
    counted_records: tuple[tuple[str, str], ...]


def validate_regional_cluster_cap_options(
    regional_cluster_cap: Optional[int],
    *,
    acknowledge_regional_cap_increase: bool = False,
    acknowledge_regional_cap_risk: bool = False,
) -> int:
    """Return the effective regional cap after validating override acknowledgements."""

    acknowledgements = {
        REGIONAL_CAP_INCREASE_ACK_FLAG: acknowledge_regional_cap_increase,
        REGIONAL_CAP_RISK_ACK_FLAG: acknowledge_regional_cap_risk,
    }
    for flag, value in acknowledgements.items():
        if not isinstance(value, bool):
            raise ValueError(f"{flag} must be a boolean flag.")

    if regional_cluster_cap is None:
        effective_cap = DEFAULT_REGIONAL_CLUSTER_CAP
    elif isinstance(regional_cluster_cap, bool) or not isinstance(regional_cluster_cap, int):
        raise ValueError("--regional-cluster-cap must be an integer.")
    else:
        effective_cap = regional_cluster_cap

    if effective_cap < 1:
        raise ValueError("--regional-cluster-cap must be at least 1.")

    has_any_acknowledgement = any(acknowledgements.values())
    if effective_cap <= DEFAULT_REGIONAL_CLUSTER_CAP:
        if has_any_acknowledgement:
            raise ValueError(
                f"{REGIONAL_CAP_INCREASE_ACK_FLAG} and {REGIONAL_CAP_RISK_ACK_FLAG} "
                "are valid only with an explicit --regional-cluster-cap greater than "
                f"{DEFAULT_REGIONAL_CLUSTER_CAP}."
            )
        return effective_cap

    missing_acknowledgements = [
        flag for flag, acknowledged in acknowledgements.items() if not acknowledged
    ]
    if missing_acknowledgements:
        raise ValueError(
            f"Increasing --regional-cluster-cap above {DEFAULT_REGIONAL_CLUSTER_CAP} "
            "requires both independent acknowledgements; missing: "
            + ", ".join(missing_acknowledgements)
            + "."
        )

    return effective_cap


def evaluate_regional_cluster_cap(
    *,
    cluster_name: str,
    records: Any,
    effective_cap: int,
) -> RegionalClusterCapDecision:
    """Count non-deleted records and project the requested cluster create."""

    if not isinstance(records, list):
        raise ValueError("the validated inventory does not contain a clusters list")

    counted_records: list[tuple[str, str]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"clusters[{index}] is not an object")
        name = record.get("clusterName")
        status = record.get("clusterStatus")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"clusters[{index}].clusterName is invalid")
        if not isinstance(status, str) or not status.strip():
            raise ValueError(f"clusters[{index}].clusterStatus is invalid")
        if status == "DELETE_COMPLETE":
            continue
        counted_records.append((name, status))

    requested_name_present = any(name == cluster_name for name, _status in counted_records)
    current_count = len(counted_records)
    projected_count = current_count + (0 if requested_name_present else 1)
    return RegionalClusterCapDecision(
        effective_cap=effective_cap,
        current_count=current_count,
        projected_count=projected_count,
        requested_name_present=requested_name_present,
        counted_records=tuple(counted_records),
    )


def register_preflight_step(step: PreflightStep) -> None:
    """Append a validator to the global preflight pipeline.

    Steps execute in registration order, which **must** match §10.5.
    """
    _PREFLIGHT_STEPS.append(step)


def clear_preflight_steps() -> None:
    """Reset the pipeline (used in tests)."""
    _PREFLIGHT_STEPS.clear()


def _normalize_headnode_repo_url(repo_url: str, *, deploy_key_auth: bool = False) -> str:
    """Return a headnode-safe clone URL for the Daylily control repo."""
    github_path = ""
    if repo_url.startswith("git@github.com:"):
        github_path = repo_url.removeprefix("git@github.com:")
        if "/" not in github_path:
            raise RuntimeError(f"Unsupported GitHub SSH repository URL: {repo_url}")
    elif repo_url.startswith("ssh://git@github.com/"):
        github_path = repo_url.removeprefix("ssh://git@github.com/")
        if "/" not in github_path:
            raise RuntimeError(f"Unsupported GitHub SSH repository URL: {repo_url}")
    elif repo_url.startswith("https://github.com/"):
        github_path = repo_url.removeprefix("https://github.com/")
        if "/" not in github_path:
            raise RuntimeError(f"Unsupported GitHub repository URL: {repo_url}")
    elif repo_url.startswith("git@") or repo_url.startswith("ssh://"):
        raise RuntimeError(
            "Headnode repository clone requires HTTPS or a supported GitHub SSH remote; "
            f"got {repo_url}"
        )

    if github_path:
        if deploy_key_auth:
            return f"git@github.com:{github_path}"
        return f"https://github.com/{github_path}"
    if deploy_key_auth:
        raise RuntimeError(
            "DYEC deploy-key bootstrap requires a supported github.com repository URL; "
            f"got {repo_url}"
        )
    return repo_url


def resolve_configured_headnode_repo_spec(*, deploy_key_auth: bool) -> HeadnodeRepoSpec:
    """Resolve the repository URL at the exact release reported by this DYEC."""
    import yaml

    from daylily_ec.resources import resource_path
    from daylily_ec.versioning import get_release_version

    user_cfg_path = Path.home() / ".config" / "daylily" / "daylily_cli_global.yaml"
    cfg_path = (
        user_cfg_path
        if user_cfg_path.exists()
        else (
            Path("config/daylily_cli_global.yaml")
            if Path("config/daylily_cli_global.yaml").exists()
            else resource_path("config/daylily_cli_global.yaml")
        )
    )
    with open(cfg_path, encoding="utf-8") as fh:
        cli_cfg = yaml.safe_load(fh) or {}
    daylily = cli_cfg.get("daylily", {}) or {}
    repo_url = str(daylily.get("git_ephemeral_cluster_repo") or "").strip()
    if not repo_url:
        raise RuntimeError(f"DYEC repository URL must be explicit in {cfg_path}.")
    return HeadnodeRepoSpec(
        url=_normalize_headnode_repo_url(repo_url, deploy_key_auth=deploy_key_auth),
        ref=get_release_version(),
    )


def resolve_configured_headnode_dayoa_repo_spec(
    *,
    deploy_key_auth: bool,
    repo_overrides: Optional[Dict[str, str]] = None,
) -> HeadnodeRepoSpec:
    """Resolve the exact DayOA repository/ref that headnode configure must bootstrap."""
    from daylily_ec.repositories import load_repository_catalog

    repository_key = "daylily-omics-analysis"
    catalog = load_repository_catalog(_repository_catalog_path())
    repository = catalog.repositories.get(repository_key)
    if repository is None:
        raise RuntimeError(f"Repository catalog does not define {repository_key!r}.")

    if repo_overrides:
        unknown_repositories = sorted(set(repo_overrides) - set(catalog.repositories))
        if unknown_repositories:
            raise RuntimeError(
                "Repository override keys are absent from the command catalog: "
                + ", ".join(unknown_repositories)
            )

    requested_ref = ""
    if repo_overrides and repository_key in repo_overrides:
        requested_ref = str(repo_overrides[repository_key] or "").strip()
        if not requested_ref:
            raise RuntimeError(
                f"Repository override for {repository_key!r} must name a non-empty Git ref."
            )
    dayoa_ref = requested_ref or str(repository.default_ref or "").strip()
    if not dayoa_ref:
        raise RuntimeError(f"Repository catalog {repository_key!r} has no default_ref.")

    repository_url = repository.ssh_url if deploy_key_auth else repository.https_url
    if not repository_url:
        transport = "SSH" if deploy_key_auth else "HTTPS"
        raise RuntimeError(f"Repository catalog {repository_key!r} has no {transport} clone URL.")
    return HeadnodeRepoSpec(
        url=_normalize_headnode_repo_url(repository_url, deploy_key_auth=deploy_key_auth),
        ref=dayoa_ref,
    )


def _build_headnode_config_yaml_sync_command(repo_name: str) -> str:
    """Copy the exact DYEC top-level YAML configuration into the headnode home config."""
    repo_name_q = shlex.quote(repo_name)
    return "\n".join(
        (
            "set -euo pipefail",
            f"repo_name={repo_name_q}",
            'repo_dir="$HOME/projects/$repo_name"',
            'source_dir="$repo_dir/config"',
            'destination_dir="$HOME/.config/daylily"',
            'test -d "$source_dir"',
            'set -- "$source_dir"/*.yaml',
            'if [ ! -f "$1" ]; then',
            '  echo "No DYEC config/*.yaml files found at $source_dir" >&2',
            "  exit 1",
            "fi",
            'install -d -m 0700 "$destination_dir"',
            'install -m 0644 "$@" "$destination_dir/"',
        )
    )


def _build_headnode_conda_environment_reset_command() -> str:
    """Return the explicit, opt-in reset for the two named headnode environments."""
    return "\n".join(
        (
            "set -euo pipefail",
            'source "$HOME/miniconda3/etc/profile.d/conda.sh"',
            'case "${CONDA_DEFAULT_ENV:-}" in',
            "  DAYOA|DAY-EC) conda deactivate ;;",
            "esac",
            "for env_name in DAYOA DAY-EC; do",
            '  if conda env list | awk \'{print $1}\' | grep -Fx "$env_name" >/dev/null 2>&1; then',
            '    conda env remove -n "$env_name" --yes',
            "  fi",
            "done",
            'rm -f "$HOME/.config/daylily/headnode_dayoa_bootstrap.tsv"',
        )
    )


def _build_headnode_dayec_install_command(repo_name: str) -> str:
    """Build or update the named DAY-EC environment without ambient confirmation settings."""
    repo_name_q = shlex.quote(repo_name)
    return "\n".join(
        (
            "set -euo pipefail",
            f"repo_name={repo_name_q}",
            'repo_dir="$HOME/projects/$repo_name"',
            'cd "$repo_dir"',
            'source "$HOME/miniconda3/etc/profile.d/conda.sh"',
            'if conda env list | awk \'{print $1}\' | grep -Fx DAY-EC >/dev/null 2>&1; then',
            "  conda env update --name DAY-EC --file environment.yaml --prune --yes",
            "else",
            "  conda env create --name DAY-EC --file environment.yaml --yes",
            "fi",
            "conda activate DAY-EC",
            "python -m pip install --editable .",
            "python -m pip install --upgrade pygraphviz",
            "python -c 'import pygraphviz; print(\"pygraphviz DAY-EC import OK\", pygraphviz.__version__)'",
            'source "$repo_dir/activate"',
            '"$repo_dir/bin/install-daylily-headnode-tools"',
            'test -f "$repo_dir/config/day_cluster/sbatch"',
            'sudo install -o root -g root -m 0755 "$repo_dir/config/day_cluster/sbatch" /opt/slurm/bin/sbatch',
            'cmp --silent "$repo_dir/config/day_cluster/sbatch" /opt/slurm/bin/sbatch',
        )
    )


def _build_headnode_dayoa_bootstrap_command(
    *,
    cluster_name: str,
    dayoa_ref: str,
    dyec_version: str,
) -> str:
    """Serialize first-use DayOA bootstrap in the required Ubuntu interactive login shell."""
    body = "\n".join(
        (
            "set -euo pipefail",
            'test "$(id -un)" = ubuntu',
            'repo_dir="$HOME/projects/daylily-omics-analysis"',
            'dayec_repo_dir="$HOME/projects/daylily-ephemeral-cluster"',
            'receipt="$HOME/.config/daylily/headnode_dayoa_bootstrap.tsv"',
            'lock_path="$HOME/.config/daylily/headnode_dayoa_bootstrap.lock"',
            f"expected_ref={shlex.quote(dayoa_ref)}",
            f"expected_dyec_version={shlex.quote(dyec_version)}",
            f"project_name={shlex.quote(cluster_name)}",
            'test -d "$repo_dir/.git"',
            'test -f "$repo_dir/dyoainit"',
            'test -x "$dayec_repo_dir/bin/init_dayec"',
            'command -v flock >/dev/null 2>&1',
            'source "$HOME/miniconda3/etc/profile.d/conda.sh"',
            'install -d -m 0700 "$HOME/.config/daylily"',
            'exec 9>"$lock_path"',
            "flock -x 9",
            'dayoa_commit="$(git -C "$repo_dir" rev-parse HEAD)"',
            "daylily_env_exists() {",
            '  conda env list | awk \'{print $1}\' | grep -Fx "$1" >/dev/null 2>&1',
            "}",
            "receipt_value() {",
            '  receipt_key="$1"',
            '  receipt_count="$(awk -F \'\\t\' -v key="$receipt_key" \'$1 == key {count += 1} END {print count + 0}\' "$receipt")"',
            '  if [ "$receipt_count" != "1" ]; then',
            '    echo "Malformed DayOA bootstrap receipt: expected one $receipt_key field" >&2',
            "    exit 1",
            "  fi",
            '  awk -F \'\\t\' -v key="$receipt_key" \'$1 == key {print $2}\' "$receipt"',
            "}",
            'if [ -e "$receipt" ]; then',
            '  if [ ! -f "$receipt" ]; then',
            '    echo "DayOA bootstrap receipt is not a regular file: $receipt" >&2',
            "    exit 1",
            "  fi",
            '  stored_schema="$(receipt_value schema_version)"',
            '  stored_ref="$(receipt_value dayoa_ref)"',
            '  stored_commit="$(receipt_value dayoa_commit)"',
            '  if [ "$stored_schema" != "1" ] || [ "$stored_ref" != "$expected_ref" ] || [ "$stored_commit" != "$dayoa_commit" ]; then',
            '    printf "Refreshing stale DayOA bootstrap receipt for %s @ %s\\n" "$expected_ref" "$dayoa_commit"',
            "  elif ! daylily_env_exists DAYOA; then",
            '    printf "Refreshing missing DAYOA environment for %s @ %s\\n" "$expected_ref" "$dayoa_commit"',
            "  else",
            '    printf "Pinned DayOA bootstrap already complete: %s @ %s\\n" "$expected_ref" "$dayoa_commit"',
            "    exit 0",
            "  fi",
            "fi",
            'cd "$repo_dir"',
            'source dyoainit --project "$project_name" --skip-project-check',
            "shopt -s expand_aliases",
            'alias dy-b="$dayec_repo_dir/bin/init_dayec"',
            # A bash -c payload is parsed before its alias definition executes.
            # Re-parse this fixed literal so the required DayOA/DYEC ``dy-b``
            # interface is really used rather than calling the target path directly.
            'eval "dy-b BUILD"',
            "if ! daylily_env_exists DAYOA; then",
            '  echo "dyoainit completed but DAYOA is absent" >&2',
            "  exit 1",
            "fi",
            "if ! daylily_env_exists DAY-EC; then",
            '  echo "dy-b BUILD completed but DAY-EC is absent" >&2',
            "  exit 1",
            "fi",
            'receipt_stage="$(mktemp "${receipt}.tmp.XXXXXX")"',
            'trap \'rm -f "$receipt_stage"\' EXIT',
            "printf 'schema_version\\t1\\n' > \"$receipt_stage\"",
            "printf 'dyec_version\\t%s\\n' \"$expected_dyec_version\" >> \"$receipt_stage\"",
            "printf 'dayoa_ref\\t%s\\n' \"$expected_ref\" >> \"$receipt_stage\"",
            "printf 'dayoa_commit\\t%s\\n' \"$dayoa_commit\" >> \"$receipt_stage\"",
            'mv "$receipt_stage" "$receipt"',
            "trap - EXIT",
            'printf "Pinned DayOA bootstrap complete: %s @ %s\\n" "$expected_ref" "$dayoa_commit"',
        )
    )
    return f"bash --login --interactive -c {shlex.quote(body)}"


def _build_headnode_repo_sync_command(
    repo_name: str,
    repo_url: str,
    repo_ref: str,
    *,
    deploy_key_secret_arn: str = "",
    deploy_key_region: str = "",
) -> str:
    if bool(deploy_key_secret_arn) != bool(deploy_key_region):
        raise ValueError("DYEC deploy-key secret ARN and region must be provided together.")

    repo_name_q = shlex.quote(repo_name)
    repo_url_q = shlex.quote(repo_url)
    repo_ref_q = shlex.quote(repo_ref)
    origin_ref_q = shlex.quote(f"refs/remotes/origin/{repo_ref}")
    origin_checkout_q = shlex.quote(f"origin/{repo_ref}")
    repo_error_q = shlex.quote(f"Expected ~/projects/{repo_name} to be a git checkout")
    if repo_ref.startswith("refs/tags/"):
        checkout_cmd = f"git checkout --detach {repo_ref_q}"
    elif DYEC_RELEASE_VERSION_PATTERN.fullmatch(repo_ref):
        release_ref_q = shlex.quote(f"refs/tags/{repo_ref}")
        checkout_cmd = f"git checkout --detach {release_ref_q}"
    else:
        checkout_cmd = (
            f"if git show-ref --verify --quiet {origin_ref_q}; then "
            f"git checkout -B daylily-managed {origin_checkout_q}; "
            "else "
            f"git checkout --detach {repo_ref_q}; "
            "fi"
        )

    auth_setup = ""
    if deploy_key_secret_arn:
        secret_arn_q = shlex.quote(deploy_key_secret_arn)
        region_q = shlex.quote(deploy_key_region)
        auth_setup = (
            "umask 077 && "
            "dayec_key_dir=$(mktemp -d) && "
            "trap 'rm -rf \"$dayec_key_dir\"' EXIT && "
            f"aws secretsmanager get-secret-value --region {region_q} "
            f"--secret-id {secret_arn_q} --query SecretString --output text "
            '--no-cli-pager >"$dayec_key_dir/deploy_key" && '
            'chmod 0600 "$dayec_key_dir/deploy_key" && '
            'ssh-keygen -y -f "$dayec_key_dir/deploy_key" >/dev/null && '
            'test -s "$HOME/.config/daylily/github_known_hosts" && '
            "export GIT_TERMINAL_PROMPT=0 && "
            'export GIT_SSH_COMMAND="ssh -i $dayec_key_dir/deploy_key '
            "-o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes "
            '-o UserKnownHostsFile=$HOME/.config/daylily/github_known_hosts" && '
        )

    return (
        auth_setup + "mkdir -p ~/projects && cd ~/projects && "
        f"if [ -e {repo_name_q} ] && [ ! -d {repo_name_q}/.git ]; then "
        f"echo {repo_error_q} >&2; exit 1; "
        "fi && "
        f"if [ ! -d {repo_name_q}/.git ]; then git clone {repo_url_q} {repo_name_q}; fi && "
        f"cd {repo_name_q} && "
        "git fetch origin --tags --prune && "
        "git reset --hard HEAD && "
        "git clean -fdx && " + checkout_cmd
    )


def _build_headnode_github_token_setup_command() -> str:
    """Install the no-persist GitHub credential helper for the two LSMC repos."""

    helper_stage = "$HOME/.config/daylily/daylily-github-credential.py"
    helper_path = "$HOME/.local/bin/daylily-github-credential"
    token_config = "$HOME/.config/daylily/github_token.json"
    url_key = 'url.https://github.com/lsmc-bio/.insteadOf'
    ssh_aliases = (
        "git@github.com:lsmc-bio/",
        "ssh://git@github.com/lsmc-bio/",
    )
    ensure_aliases = " && ".join(
        (
            "if ! git config --global --get-all "
            f"{shlex.quote(url_key)} | grep -Fxq {shlex.quote(alias)}; then "
            f"git config --global --add {shlex.quote(url_key)} {shlex.quote(alias)}; fi"
        )
        for alias in ssh_aliases
    )
    return " && ".join(
        (
            "install -d -m 0700 ~/.config/daylily ~/.local/bin",
            f"install -m 0755 \"{helper_stage}\" \"{helper_path}\"",
            f"chmod 0600 \"{token_config}\"",
            "git config --global credential.useHttpPath true",
            "git config --global credential.interactive false",
            "git config --global "
            + shlex.quote("credential.https://github.com.helper")
            + " "
            + shlex.quote(f"!{helper_path}"),
            ensure_aliases,
        )
    )


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
        prev_count = len(report.checks)
        report = step(report)

        # Print result only for checks just added by this step
        for chk in report.checks[prev_count:]:
            if chk.status.value == "FAIL":
                ui.fail(f"{chk.id}: {chk.remediation or chk.message}")
            elif chk.status.value == "WARN":
                ui.warn(f"{chk.id}: {chk.remediation or chk.message}")
            elif chk.status.value == "PASS":
                ui.ok(chk.id)

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
        ui.warn("Preflight has warnings and --pass-on-warn not set — aborting.")
        write_preflight_report(report)
        return report

    # Success
    write_preflight_report(report)
    logger.info("Preflight passed — %d checks OK.", len(report.checks))
    ui.ok(f"Preflight passed — {len(report.checks)} checks OK")
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
        return EXIT_VALIDATION_FAILURE
    return EXIT_SUCCESS


def _repository_catalog_path() -> Path:
    """Return the repository catalog path used by local create/headnode setup."""
    local_catalog = Path("config/daylily_pipeline_command_catalog.yaml")
    if local_catalog.exists():
        return local_catalog

    from daylily_ec.repositories import default_catalog_path

    return default_catalog_path()


def make_repository_catalog_preflight_step(
    catalog_path: Optional[Path] = None,
) -> PreflightStep:
    """Validate the repository catalog consumed by ``day-clone`` on headnodes."""

    def step(report: PreflightReport) -> PreflightReport:
        from daylily_ec.repositories import load_repository_catalog

        path = (
            Path(catalog_path).expanduser()
            if catalog_path is not None
            else _repository_catalog_path()
        )
        try:
            catalog = load_repository_catalog(path)
        except Exception as exc:
            report.checks.append(
                CheckResult(
                    id="config.repository_catalog",
                    status=CheckStatus.FAIL,
                    details={
                        "path": str(path),
                        "error": str(exc),
                    },
                    remediation=(
                        f"Fix repository catalog {path}. Headnode configuration would fail "
                        "because day-clone consumes this file."
                    ),
                )
            )
            return report

        report.checks.append(
            CheckResult(
                id="config.repository_catalog",
                status=CheckStatus.PASS,
                details={
                    "path": str(path),
                    "command_catalog_version": catalog.command_catalog_version,
                    "default_repository": catalog.default_repository,
                    "repository_count": len(catalog.repositories),
                    "command_count": len(catalog.commands()),
                },
            )
        )
        return report

    return step


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_selected(
    report: PreflightReport,
    check_id: str,
    detail_key: str,
) -> str:
    """Pull a value from report check details (e.g. selected bucket)."""
    for chk in report.checks:
        if chk.id == check_id:
            return str(chk.details.get(detail_key, ""))
    return ""


def _extract_s3_roles(report: PreflightReport) -> Dict[str, Dict[str, str]]:
    """Pull normalized S3 role details from the preflight report."""
    for chk in report.checks:
        if chk.id == "s3.role_config":
            roles = chk.details.get("roles", {})
            if isinstance(roles, dict):
                return {
                    str(role): {
                        "uri": str(detail.get("uri", "")),
                        "bucket": str(detail.get("bucket", "")),
                        "prefix": str(detail.get("prefix", "")),
                    }
                    for role, detail in roles.items()
                    if isinstance(detail, dict)
                }
    return {}


def _role_uri(roles: Dict[str, Dict[str, str]], role: str) -> str:
    return str((roles.get(role) or {}).get("uri") or "")


def _role_bucket(roles: Dict[str, Dict[str, str]], role: str) -> str:
    return str((roles.get(role) or {}).get("bucket") or "")


SPOT_PRICE_PARTITION_TABLE_HEADERS = (
    "Partition",
    "Min Inst",
    "Max Inst",
    "Raw Min $/hr",
    "Raw Max $/hr",
    "Median $/hr",
    "Max Bid $/vCPU-hr",
    "Uncapped Bid",
    "Final Bid",
    "Global Max",
    "Warn >$",
    "Limiter",
    "Warn",
    "Reference",
)


def _spot_price_partition_table_values(row: Dict[str, Any]) -> list[str]:
    return [
        str(row.get("queue", "")),
        str(row.get("min_instances", "")),
        str(row.get("max_instances", "")),
        f"{float(row.get('raw_min_hourly_cost_without_limiter') or 0):.4f}",
        f"{float(row.get('raw_max_hourly_cost_without_limiter') or 0):.4f}",
        f"{float(row.get('max_reference_median_spot_price') or 0):.4f}",
        f"{float(row.get('max_final_bid_usd_per_vcpu_hour') or 0):.4f}",
        f"{float(row.get('max_uncapped_pct_bid') or 0):.4f}",
        f"{float(row.get('max_final_bid') or 0):.4f}",
        f"{float(row.get('global_spot_max_cost') or 0):.2f}",
        f"{float(row.get('write_spot_pricing_warn_threshold') or 0):.2f}",
        "yes" if row.get("global_limiter_applied") else "no",
        "yes" if row.get("warn_threshold_exceeded") else "no",
        str(row.get("reference_partitions", "")),
    ]


def _markdown_cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", r"\|")


def _format_markdown_table(headers: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    header_values = [_markdown_cell(str(value)) for value in headers]
    lines = [
        "| " + " | ".join(header_values) + " |",
        "| " + " | ".join("---" for _ in header_values) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_markdown_cell(str(value)) for value in row) + " |")
    return "\n".join(lines)


def _write_spot_price_partition_markdown(
    summary: Dict[str, Any],
    *,
    cluster_name: str,
    output_path: Path,
) -> None:
    partitions = summary.get("partitions") or []
    rows = [_spot_price_partition_table_values(row) for row in partitions]
    body = "\n".join(
        [
            f"# DYEC create spot price summary: {cluster_name}",
            "",
            f"- Generated at: {summary.get('generated_at', '')}",
            f"- Availability zone: {summary.get('availability_zone', '')}",
            "",
            _format_markdown_table(SPOT_PRICE_PARTITION_TABLE_HEADERS, rows),
            "",
        ]
    )
    try:
        output_path.write_text(body, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Failed to write spot price markdown table {output_path}: {exc}"
        ) from exc


def _emit_spot_price_partition_table(
    summary: Dict[str, Any],
    *,
    cluster_name: str,
    markdown_output_path: Path,
) -> None:
    """Print the operator-facing partition spot-price summary."""

    from rich.table import Table

    partitions = summary.get("partitions") or []
    if not partitions:
        ui.info("No spot price partition rows were generated.")
        return

    table = Table(title="DYEC create spot price summary")
    for header in SPOT_PRICE_PARTITION_TABLE_HEADERS:
        justify = "right" if header not in {"Partition", "Limiter", "Warn", "Reference"} else "left"
        table.add_column(header, justify=justify)
    for row in partitions:
        table.add_row(*_spot_price_partition_table_values(row))
    ui.console.print(table)
    _write_spot_price_partition_markdown(
        summary,
        cluster_name=cluster_name,
        output_path=markdown_output_path,
    )
    ui.info(f"Spot price summary table markdown: {markdown_output_path}")


def _has_explicit_set_value(cfg: Any, key: str) -> bool:
    triplet = cfg.ephemeral_cluster.config.get(key)
    return bool(
        triplet
        and triplet.action == "USESETVALUE"
        and triplet.set_value.strip()
        and triplet.set_value.strip() != "PROMPTUSER"
    )


def normalize_create_cluster_type(cluster_type: str) -> str:
    """Validate and normalize the create-time cluster template family."""

    normalized = str(cluster_type or "").strip().lower()
    if normalized not in CREATE_CLUSTER_TYPES:
        allowed = ", ".join(sorted(CREATE_CLUSTER_TYPES))
        raise ValueError(f"--cluster-type must be one of: {allowed}")
    return normalized


def parse_create_repo_overrides(values: Optional[Iterable[str]]) -> Dict[str, str]:
    """Parse repeated ``<repo-key>:<git-ref>`` create options."""

    overrides: Dict[str, str] = {}
    for raw_value in values or ():
        value = str(raw_value).strip()
        if ":" not in value:
            raise ValueError(f"--repo-override must use <repo-key>:<git-ref>; got {raw_value!r}.")
        repo_key, git_ref = (part.strip() for part in value.split(":", 1))
        if not repo_key or not git_ref:
            raise ValueError(
                "--repo-override requires non-empty repository and git ref values; "
                f"got {raw_value!r}."
            )
        if repo_key in overrides:
            raise ValueError(
                f"--repo-override was provided more than once for repository {repo_key!r}."
            )
        overrides[repo_key] = git_ref
    return overrides


def validate_create_cluster_type_region(cluster_type: str, region_az: str) -> None:
    """Reject cluster types outside their explicitly supported AZs."""

    normalized = normalize_create_cluster_type(cluster_type)
    if normalized == SENTIEON_SINGLE_CLUSTER_TYPE and region_az != SENTIEON_SINGLE_REGION_AZ:
        raise ValueError(
            f"--cluster-type {SENTIEON_SINGLE_CLUSTER_TYPE} is supported only in "
            f"{SENTIEON_SINGLE_REGION_AZ}; got {region_az!r}."
        )


def resolve_dragen_create_inputs(
    cfg: Any,
    *,
    cluster_type: str,
    region_az: str,
) -> Optional[DragenCreateInputs]:
    """Resolve explicit private inputs for the DRAGEN cluster type."""

    if cluster_type != DRAGEN_CLUSTER_TYPE:
        return None

    from daylily_ec.aws.context import parse_region_az
    from daylily_ec.pcluster.backport import load_operational_backport

    values: dict[str, str] = {}
    for key, label in (
        ("pcluster_backport_manifest", "ParallelCluster backport manifest"),
        ("dragen_license_secret_arn", "DRAGEN license secret ARN"),
        ("dragen_license_policy_arn", "DRAGEN license policy ARN"),
    ):
        if not _has_explicit_set_value(cfg, key):
            raise ValueError(
                f"--cluster-type dragen requires explicit config key {key!r} ({label}); "
                "defaults and discovery are not accepted."
            )
        values[key] = str(cfg.ephemeral_cluster.config[key].set_value).strip()

    backport = load_operational_backport(values["pcluster_backport_manifest"])
    region, _az = parse_region_az(region_az)
    if backport.image_region != region:
        raise ValueError(
            "Qualified image region does not match requested cluster region: "
            f"{backport.image_region} != {region}."
        )

    secret_arn = values["dragen_license_secret_arn"]
    secret_match = re.fullmatch(
        r"arn:(aws(?:-us-gov)?):secretsmanager:([a-z0-9-]+):(\d{12}):secret:[A-Za-z0-9/_+=.@-]+",
        secret_arn,
    )
    if not secret_match or secret_match.group(2) != region:
        raise ValueError(
            f"dragen_license_secret_arn must be an explicit Secrets Manager ARN in {region}."
        )

    policy_arn = values["dragen_license_policy_arn"]
    if not re.fullmatch(
        r"arn:aws(?:-us-gov)?:iam::\d{12}:policy/[A-Za-z0-9+=,.@_/-]+",
        policy_arn,
    ):
        raise ValueError("dragen_license_policy_arn must be an explicit managed-policy ARN.")

    return DragenCreateInputs(
        backport=backport,
        license_secret_arn=secret_arn,
        license_policy_arn=policy_arn,
    )


def _resolve_deploy_key_inputs(
    cfg: Any,
    *,
    config_prefix: str,
    display_name: str,
    region_az: str,
    account_id: str,
    non_interactive: bool,
) -> tuple[str, str, str]:
    """Resolve one explicit repository deploy-key secret and policy pair."""

    from daylily_ec.aws.context import parse_region_az

    region, _az = parse_region_az(region_az)
    secret_key = f"{config_prefix}_deploy_key_secret_arn"
    policy_key = f"{config_prefix}_deploy_key_policy_arn"
    secret_arn = _resolve_config_value(
        cfg,
        secret_key,
        f"{display_name} deploy-key Secrets Manager ARN",
        non_interactive=non_interactive,
    ).strip()
    policy_arn = _resolve_config_value(
        cfg,
        policy_key,
        f"{display_name} deploy-key managed-policy ARN",
        non_interactive=non_interactive,
    ).strip()

    secret_match = re.fullmatch(
        r"arn:(aws(?:-us-gov)?):secretsmanager:([a-z0-9-]+):(\d{12}):secret:[A-Za-z0-9/_+=.@-]+",
        secret_arn,
    )
    if not secret_match:
        raise ValueError(f"{secret_key} must be an explicit Secrets Manager ARN.")
    if secret_match.group(2) != region:
        raise ValueError(
            f"{secret_key} region must match the cluster region: "
            f"{secret_match.group(2)} != {region}."
        )
    if secret_match.group(3) != account_id:
        raise ValueError(f"{secret_key} must belong to the active AWS account.")

    policy_match = re.fullmatch(
        r"arn:aws(?:-us-gov)?:iam::(\d{12}):policy/[A-Za-z0-9+=,.@_/-]+",
        policy_arn,
    )
    if not policy_match:
        raise ValueError(f"{policy_key} must be an explicit managed-policy ARN.")
    if policy_match.group(1) != account_id:
        raise ValueError(f"{policy_key} must belong to the active AWS account.")

    return secret_arn, policy_arn, region


def resolve_dayoa_deploy_key_inputs(
    cfg: Any,
    *,
    region_az: str,
    account_id: str,
    non_interactive: bool,
) -> DayoaDeployKeyInputs:
    """Resolve and validate the explicit DayOA deploy-key secret and policy."""

    secret_arn, policy_arn, region = _resolve_deploy_key_inputs(
        cfg,
        config_prefix="dayoa",
        display_name="DayOA",
        region_az=region_az,
        account_id=account_id,
        non_interactive=non_interactive,
    )

    return DayoaDeployKeyInputs(
        secret_arn=secret_arn,
        policy_arn=policy_arn,
        region=region,
    )


def resolve_dyec_deploy_key_inputs(
    cfg: Any,
    *,
    region_az: str,
    account_id: str,
    non_interactive: bool,
) -> DyecDeployKeyInputs:
    """Resolve and validate the explicit DYEC bootstrap deploy key and policy."""

    secret_arn, policy_arn, region = _resolve_deploy_key_inputs(
        cfg,
        config_prefix="dyec",
        display_name="DYEC",
        region_az=region_az,
        account_id=account_id,
        non_interactive=non_interactive,
    )
    return DyecDeployKeyInputs(
        secret_arn=secret_arn,
        policy_arn=policy_arn,
        region=region,
    )


def attach_headnode_managed_policy(
    cluster_yaml_path: str | Path,
    policy_arn: str,
) -> None:
    """Attach one managed policy to the headnode and reject compute attachment."""

    import yaml

    path = Path(cluster_yaml_path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("Rendered cluster YAML must be a mapping.")

    queues = (payload.get("Scheduling") or {}).get("SlurmQueues") or []
    for queue in queues:
        if not isinstance(queue, dict):
            continue
        queue_policies = [
            str(item.get("Policy") or "")
            for item in ((queue.get("Iam") or {}).get("AdditionalIamPolicies") or [])
            if isinstance(item, dict)
        ]
        if policy_arn in queue_policies:
            raise ValueError(
                "DayOA deploy-key policy must not be attached to compute queue "
                f"{queue.get('Name')!r}."
            )

    headnode = payload.get("HeadNode")
    if not isinstance(headnode, dict):
        raise ValueError("Rendered cluster YAML is missing HeadNode.")
    iam = headnode.get("Iam")
    if not isinstance(iam, dict):
        raise ValueError("Rendered cluster YAML is missing HeadNode.Iam.")
    policies = iam.get("AdditionalIamPolicies")
    if not isinstance(policies, list):
        raise ValueError("Rendered cluster YAML is missing HeadNode.Iam.AdditionalIamPolicies.")
    existing = [
        item
        for item in policies
        if isinstance(item, dict) and str(item.get("Policy") or "") == policy_arn
    ]
    if len(existing) > 1:
        raise ValueError("DayOA deploy-key policy appears more than once on the headnode.")
    if not existing:
        policies.append({"Policy": policy_arn})

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def az_cluster_template_relative_path(cluster_type: str, region_az: str) -> Path:
    """Return the exact AZ-scoped cluster template path for create."""

    from daylily_ec.aws.context import parse_region_az

    normalized_type = normalize_create_cluster_type(cluster_type)
    region, _az = parse_region_az(region_az)
    filename_type = "intel_spot" if normalized_type == "intel" else normalized_type
    return (
        Path("config/day_cluster")
        / normalized_type
        / region
        / region_az
        / f"prod_cluster_{filename_type}_{region_az}.yaml"
    )


def _explicit_cluster_template_yaml(cfg: Any) -> str:
    triplet = cfg.ephemeral_cluster.config.get("cluster_template_yaml")
    if triplet is None:
        return ""
    candidate = str(triplet.set_value or "").strip()
    if candidate and candidate != "PROMPTUSER":
        return candidate
    return ""


def _resolve_existing_template_path(
    template_path: str, resource_path_fn: Callable[[str], Path]
) -> str:
    candidate = Path(template_path).expanduser()
    if candidate.is_file():
        return str(candidate)
    if candidate.is_absolute():
        raise FileNotFoundError(f"Cluster template YAML not found: {candidate}")
    return str(resource_path_fn(template_path))


def resolve_cluster_template_yaml(
    cfg: Any,
    *,
    region_az: str,
    cluster_type: str = DEFAULT_CREATE_CLUSTER_TYPE,
    resource_path_fn: Callable[[str], Path],
) -> str:
    """Resolve the cluster template for create.

    Explicit non-empty ``cluster_template_yaml`` set values are honored. When no
    explicit template is set, the exact cluster-type/AZ-scoped template path is
    required; missing paths fail hard instead of falling back to a generic
    template.
    """

    normalized_type = normalize_create_cluster_type(cluster_type)
    validate_create_cluster_type_region(normalized_type, region_az)
    explicit = _explicit_cluster_template_yaml(cfg)
    if normalized_type == DRAGEN_CLUSTER_TYPE and explicit:
        raise ValueError(
            "--cluster-type dragen requires the canonical AZ-scoped template; "
            "cluster_template_yaml overrides are not accepted."
        )
    if normalized_type == SENTIEON_SINGLE_CLUSTER_TYPE and explicit:
        raise ValueError(
            "--cluster-type sentieon-single requires the canonical us-west-2c template; "
            "cluster_template_yaml overrides are not accepted."
        )
    if explicit:
        return _resolve_existing_template_path(explicit, resource_path_fn)

    relative_path = az_cluster_template_relative_path(normalized_type, region_az)
    return _resolve_existing_template_path(str(relative_path), resource_path_fn)


def _s3_uri_join(base_uri: str, *parts: str) -> str:
    base = base_uri.rstrip("/")
    suffix = "/".join(part.strip("/") for part in parts if part.strip("/"))
    return f"{base}/{suffix}" if suffix else base


def _parse_s3_destination(uri: str) -> tuple[str, str]:
    parsed = urlparse(str(uri or ""))
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Expected s3:// bucket URI, got {uri!r}")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError(f"S3 URI must not include params, query, or fragment: {uri!r}")
    return parsed.netloc, parsed.path.lstrip("/").rstrip("/")


def _boot_body_contains_legacy_fsx_data(filename: str, body: bytes) -> bool:
    if b"/fsx/data" not in body:
        return False
    if filename != "post_install_ubuntu_combined.sh":
        return True
    return any(
        b"/fsx/data" in line and BOOT_CONFIG_REFERENCE_COMPAT_LINE not in line
        for line in body.splitlines()
    )


def cluster_boot_config_release_uri(*, base_uri: str, source_dir: Path) -> str:
    """Return the deterministic immutable S3 prefix for one boot-config bundle."""

    digest = hashlib.sha256()
    for filename in CLUSTER_BOOT_CONFIG_FILENAMES:
        source = source_dir / filename
        if not source.is_file():
            raise FileNotFoundError(f"Cluster boot config source not found: {source}")
        body = source.read_bytes()
        digest.update(len(filename).to_bytes(4, "big"))
        digest.update(filename.encode("utf-8"))
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
    return _s3_uri_join(base_uri, "releases", f"sha256-{digest.hexdigest()}")


def publish_cluster_boot_config(
    s3_client: Any,
    *,
    cluster_boot_s3_uri: str,
    source_dir: Path,
) -> list[str]:
    """Publish current packaged cluster boot scripts to a write-once release prefix.

    The cluster template executes these files directly from
    ``references/runtime_assets/cluster_boot_config``. Treat stale or legacy
    boot scripts as invalid because they can fail cluster creation after
    expensive FSx setup.
    """
    if "/releases/" not in cluster_boot_s3_uri:
        raise ValueError("Cluster boot config destination must use an immutable release prefix.")
    base_uri = cluster_boot_s3_uri.rsplit("/releases/", 1)[0]
    expected_uri = cluster_boot_config_release_uri(base_uri=base_uri, source_dir=source_dir)
    if cluster_boot_s3_uri != expected_uri:
        raise ValueError(
            "Cluster boot config destination must be the exact content-addressed release URI: "
            f"{expected_uri}"
        )
    bucket, prefix = _parse_s3_destination(cluster_boot_s3_uri)
    bodies: list[tuple[str, bytes]] = []
    for filename in CLUSTER_BOOT_CONFIG_FILENAMES:
        source = source_dir / filename
        if not source.is_file():
            raise FileNotFoundError(f"Cluster boot config source not found: {source}")
        body = source.read_bytes()
        if _boot_body_contains_legacy_fsx_data(filename, body):
            raise ValueError(f"Cluster boot config contains legacy /fsx/data path: {source}")
        bodies.append((filename, body))

    uploaded: list[str] = []
    for filename, body in bodies:
        key = f"{prefix}/{filename}" if prefix else filename
        body_sha256 = hashlib.sha256(body).hexdigest()
        try:
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                IfNoneMatch="*",
                Metadata={"daylily-sha256": body_sha256},
            )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code") or "")
            if error_code not in {"PreconditionFailed", "412"}:
                raise
            existing = s3_client.head_object(Bucket=bucket, Key=key)
            metadata = existing.get("Metadata") or {}
            if metadata.get("daylily-sha256") != body_sha256:
                raise ValueError(
                    "Immutable cluster boot object already exists with different content: "
                    f"s3://{bucket}/{key}"
                ) from exc
        uploaded.append(f"s3://{bucket}/{key}")
    return uploaded


def validate_startup_dra_contract(cluster_yaml_path: str | Path) -> None:
    """Fail cluster creation unless startup imports only the references DRA."""
    import yaml

    path = Path(cluster_yaml_path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    associations: list[dict[str, Any]] = []
    for storage in payload.get("SharedStorage") or []:
        if not isinstance(storage, dict) or storage.get("StorageType") != "FsxLustre":
            continue
        fsx_settings = storage.get("FsxLustreSettings") or {}
        if "FileSystemId" in fsx_settings:
            if set(fsx_settings) != {"FileSystemId"} or not str(
                fsx_settings.get("FileSystemId") or ""
            ).startswith("fs-"):
                raise ValueError(
                    "External FSx startup settings must contain only an explicit FileSystemId."
                )
            # PERSISTENT_2 data repository associations are separate FSx API
            # resources and are validated before this mount is rendered.
            return
        for association in fsx_settings.get("DataRepositoryAssociations") or []:
            if isinstance(association, dict):
                associations.append(association)

    paths = [str(item.get("FileSystemPath") or "") for item in associations]
    if paths != ["/references/"]:
        raise ValueError(
            "Cluster startup may import exactly one FSx DRA: /references/. "
            f"Rendered DataRepositoryAssociations were: {paths}"
        )
    data_repository_path = str(associations[0].get("DataRepositoryPath") or "")
    if not data_repository_path:
        raise ValueError("The /references/ startup DRA must define DataRepositoryPath.")


def validate_cpu_only_slurm_contract(cluster_yaml_path: str | Path) -> None:
    """Require declarative CPU-only placement and the server-side submit guard."""

    import yaml

    path = Path(cluster_yaml_path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    scheduling = payload.get("Scheduling") or {}
    if scheduling.get("Scheduler") != "slurm":
        raise ValueError("Cluster Scheduling.Scheduler must be slurm.")

    settings = scheduling.get("SlurmSettings") or {}
    if settings.get("EnableMemoryBasedScheduling") is not False:
        raise ValueError("SlurmSettings.EnableMemoryBasedScheduling must be false.")
    if settings.get("CustomSlurmSettings") != CPU_ONLY_SLURM_CUSTOM_SETTINGS:
        raise ValueError(
            "SlurmSettings.CustomSlurmSettings must enable JobSubmitPlugins=lua, "
            "AccountingStoreFlags=job_comment, and PrologFlags=Alloc."
        )

    head_node = payload.get("HeadNode") or {}
    on_node_start = (head_node.get("CustomActions") or {}).get("OnNodeStart") or {}
    start_script = str(on_node_start.get("Script") or "")
    start_args = on_node_start.get("Args") or []
    expected_script_name = "install_slurm_job_submit_policy.sh"
    valid_start_args = (
        isinstance(start_args, list)
        and len(start_args) == 2
        and str(start_args[0]) == str(payload.get("Region") or "")
        and start_script == f"{str(start_args[1]).rstrip('/')}/{expected_script_name}"
    )
    if not valid_start_args:
        raise ValueError(
            "HeadNode CustomActions.OnNodeStart must install job_submit.lua before "
            "ParallelCluster starts slurmctld: Script must be the immutable boot-config "
            "install_slurm_job_submit_policy.sh with Args [Region, boot-config URI]."
        )

    def _contains_schedulable_memory(value: Any) -> bool:
        if isinstance(value, dict):
            return "SchedulableMemory" in value or any(
                _contains_schedulable_memory(item) for item in value.values()
            )
        if isinstance(value, list):
            return any(_contains_schedulable_memory(item) for item in value)
        return False

    if _contains_schedulable_memory(payload):
        raise ValueError("CPU-only Slurm cluster config must not define SchedulableMemory.")

    queues = scheduling.get("SlurmQueues") or []
    if not isinstance(queues, list) or not queues:
        raise ValueError("Cluster SlurmQueues must be a non-empty list.")
    for queue in queues:
        queue_name = str(queue.get("Name") or "<unnamed>")
        if queue.get("JobExclusiveAllocation") is not False:
            raise ValueError(f"Slurm queue {queue_name} must set JobExclusiveAllocation false.")


def validate_sentieon_single_cluster_contract(cluster_yaml_path: str | Path) -> None:
    """Require the fixed standard-quota Sentieon single-node topology."""

    import yaml

    path = Path(cluster_yaml_path)
    validate_cpu_only_slurm_contract(path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if payload.get("Region") != "us-west-2":
        raise ValueError("Sentieon single cluster Region must be us-west-2.")
    if payload.get("Image") != {"Os": "ubuntu2204"}:
        raise ValueError(
            "Sentieon single cluster Image must be standard Ubuntu 22.04 without a custom AMI."
        )

    _validate_sentieon_single_bootstrap(payload.get("HeadNode") or {}, label="HeadNode")

    queues = (payload.get("Scheduling") or {}).get("SlurmQueues") or []
    if not isinstance(queues, list):
        raise ValueError("Sentieon single cluster SlurmQueues must be a list.")
    expected_queue_names = list(SENTIEON_SINGLE_QUEUE_INSTANCE_TYPES)
    queue_names = [str(queue.get("Name") or "") for queue in queues]
    if queue_names != expected_queue_names:
        raise ValueError(
            "Sentieon single cluster must render exactly the i8, i96nvme, i128nvme, "
            f"i192nvme, and i384nvme queues; rendered queues were {queue_names}."
        )

    for queue in queues:
        queue_name = str(queue.get("Name") or "")
        if queue.get("CapacityType") != "SPOT":
            raise ValueError(f"Sentieon single queue {queue_name} must use SPOT capacity.")
        if queue.get("AllocationStrategy") != "price-capacity-optimized":
            raise ValueError(
                f"Sentieon single queue {queue_name} must use price-capacity-optimized allocation."
            )
        mount_dir = (
            ((queue.get("ComputeSettings") or {}).get("LocalStorage") or {}).get("EphemeralVolume")
            or {}
        ).get("MountDir")
        if mount_dir != "/scratch":
            raise ValueError(
                f"Sentieon single queue {queue_name} must mount local NVMe at /scratch."
            )
        _validate_sentieon_single_bootstrap(queue, label=f"{queue_name} queue")

        resources = queue.get("ComputeResources") or []
        if not isinstance(resources, list) or len(resources) != 1:
            raise ValueError(
                f"Sentieon single queue {queue_name} must render exactly one "
                "multi-instance compute resource."
            )
        resource = resources[0]
        expected_resource_name = SENTIEON_SINGLE_QUEUE_RESOURCE_NAMES[queue_name]
        if resource.get("Name") != expected_resource_name:
            raise ValueError(
                f"Sentieon single queue {queue_name} must use compute resource "
                f"{expected_resource_name}."
            )
        rendered_types = [
            str(item.get("InstanceType") or "") for item in resource.get("Instances") or []
        ]
        expected_types = list(SENTIEON_SINGLE_QUEUE_INSTANCE_TYPES[queue_name])
        if rendered_types != expected_types:
            raise ValueError(
                f"Sentieon single queue {queue_name} instance types must match the "
                "pinned standard-quota Intel local-NVMe pool."
            )
        if any(instance_type.lower().startswith("x") for instance_type in rendered_types):
            raise ValueError(
                f"Sentieon single queue {queue_name} must exclude X-family instance types "
                "because they use a separate Spot quota."
            )
        if (
            resource.get("MinCount") != 0
            or resource.get("MaxCount") != SENTIEON_SINGLE_QUEUE_MAX_COUNT
        ):
            raise ValueError(
                f"Sentieon single queue {queue_name} must set MinCount 0 and "
                f"MaxCount {SENTIEON_SINGLE_QUEUE_MAX_COUNT}."
            )
        if ((resource.get("Efa") or {}).get("Enabled")) is not False:
            raise ValueError(f"Sentieon single queue {queue_name} must keep EFA disabled.")

    shared_storage = payload.get("SharedStorage") or []
    if not isinstance(shared_storage, list) or len(shared_storage) != 1:
        raise ValueError("Sentieon single cluster must define exactly one shared filesystem.")
    fsx = shared_storage[0]
    fsx_settings = fsx.get("FsxLustreSettings") or {}
    if fsx.get("MountDir") != "/fsx" or fsx.get("StorageType") != "FsxLustre":
        raise ValueError("Sentieon single cluster must mount FSx for Lustre at /fsx.")
    if (
        fsx_settings.get("StorageCapacity") != 1200
        or fsx_settings.get("DeploymentType") != "SCRATCH_2"
    ):
        raise ValueError(
            "Sentieon single cluster must use a 1200 GiB SCRATCH_2 FSx for Lustre filesystem."
        )
    associations = fsx_settings.get("DataRepositoryAssociations") or []
    if not isinstance(associations, list) or len(associations) != 1:
        raise ValueError("Sentieon single cluster must define exactly the standard references DRA.")
    reference_dra = associations[0]
    if (
        reference_dra.get("Name") != "reference-data"
        or reference_dra.get("FileSystemPath") != "/references/"
        or not str(reference_dra.get("DataRepositoryPath") or "")
        or reference_dra.get("BatchImportMetaDataOnCreate") is not True
        or reference_dra.get("AutoImportPolicy") != ["NEW", "CHANGED", "DELETED"]
    ):
        raise ValueError(
            "Sentieon single cluster must preserve the standard /references/ FSx DRA contract."
        )


def _validate_sentieon_single_bootstrap(node: dict[str, Any], *, label: str) -> None:
    action = (node.get("CustomActions") or {}).get("OnNodeConfigured") or {}
    script = str(action.get("Script") or "")
    if not script.endswith("/post_install_ubuntu_combined.sh"):
        raise ValueError(f"{label} must use the standard Ubuntu bootstrap.")
    if len(action.get("Args") or []) != 3:
        raise ValueError(f"{label} standard Ubuntu bootstrap must receive exactly three args.")


def validate_dragen_cluster_contract(
    cluster_yaml_path: str | Path,
    inputs: DragenCreateInputs,
) -> None:
    """Require the private mixed DRAGEN/CPU topology after rendering."""

    import yaml

    validate_cpu_only_slurm_contract(cluster_yaml_path)
    payload = yaml.safe_load(Path(cluster_yaml_path).read_text(encoding="utf-8")) or {}
    image = payload.get("Image") or {}
    if image.get("Os") != "almalinux8":
        raise ValueError("DRAGEN cluster Image.Os must be almalinux8.")
    if str(image.get("CustomAmi") or "").strip() != inputs.backport.image_ami_id:
        raise ValueError("DRAGEN cluster-wide AMI does not match the qualified manifest image.")

    headnode = payload.get("HeadNode") or {}
    head_ami = ((headnode.get("Image") or {}).get("CustomAmi") or "").strip()
    if head_ami != inputs.backport.image_ami_id:
        raise ValueError("DRAGEN headnode AMI does not match the qualified manifest image.")
    _validate_dragen_node_policy_and_action(
        headnode,
        inputs,
        label="HeadNode",
        expected_role="headnode",
    )

    queues = (payload.get("Scheduling") or {}).get("SlurmQueues") or []
    if not isinstance(queues, list):
        raise ValueError("DRAGEN cluster SlurmQueues must be a list.")
    queue_names = [str(queue.get("Name") or "") for queue in queues]
    expected_queue_names = [
        "dragen",
        "dragen-ondemand",
        "i192",
        "i128shm",
        "i192shm",
        "i384shm",
        "i192nvme",
    ]
    if queue_names != expected_queue_names:
        raise ValueError(
            "DRAGEN cluster must render exactly the dragen, dragen-ondemand, "
            "i192, i128shm, i192shm, i384shm, and i192nvme "
            f"queues; rendered queues were {queue_names}."
        )
    queues_by_name = {str(queue.get("Name") or ""): queue for queue in queues}
    for queue_name, capacity_type, resource_name in (
        ("dragen", "SPOT", "f26xlarge"),
        ("dragen-ondemand", "ONDEMAND", "f26xlargeod"),
    ):
        queue = queues_by_name[queue_name]
        if queue.get("CapacityType") != capacity_type:
            raise ValueError(f"DRAGEN queue {queue_name} must use {capacity_type} capacity.")
        queue_ami = ((queue.get("Image") or {}).get("CustomAmi") or "").strip()
        if queue_ami != inputs.backport.image_ami_id:
            raise ValueError(
                f"DRAGEN queue {queue_name} AMI does not match the qualified manifest image."
            )
        _validate_dragen_node_policy_and_action(
            queue,
            inputs,
            label=f"{queue_name} queue",
            expected_role="dragen",
        )

        resources = queue.get("ComputeResources") or []
        if not isinstance(resources, list) or len(resources) != 1:
            raise ValueError(f"DRAGEN queue {queue_name} must render exactly one compute resource.")
        resource = resources[0]
        if resource.get("Name") != resource_name:
            raise ValueError(
                f"DRAGEN queue {queue_name} must use compute resource {resource_name}."
            )
        instance_types = [
            str(item.get("InstanceType") or "") for item in resource.get("Instances") or []
        ]
        if instance_types != ["f2.6xlarge"]:
            raise ValueError(
                f"DRAGEN queue {queue_name} compute resource must contain only f2.6xlarge."
            )
        if resource.get("MinCount") != 0 or resource.get("MaxCount") != 1:
            raise ValueError(
                f"DRAGEN queue {queue_name} compute resource must set MinCount 0 and MaxCount 1."
            )
        if ((resource.get("Efa") or {}).get("Enabled")) is not False:
            raise ValueError(f"DRAGEN queue {queue_name} must keep EFA disabled.")
        if capacity_type == "ONDEMAND" and "SpotPrice" in resource:
            raise ValueError("DRAGEN on-demand compute resource must not define SpotPrice.")

    for queue_name, resource_name, instance_types in (
        ("i192", "mem192", ["m7i.48xlarge", "r7i.48xlarge"]),
        ("i192nvme", "mem192nvme", ["i7i.48xlarge", "i7ie.48xlarge"]),
    ):
        cpu_queue = queues_by_name[queue_name]
        if cpu_queue.get("CapacityType") != "SPOT":
            raise ValueError(f"DRAGEN CPU queue {queue_name} must use SPOT capacity.")
        cpu_ami = ((cpu_queue.get("Image") or {}).get("CustomAmi") or "").strip()
        if cpu_ami != inputs.backport.image_ami_id:
            raise ValueError(
                f"DRAGEN CPU queue {queue_name} AMI does not match the qualified image."
            )
        _validate_dragen_cpu_node(cpu_queue, inputs, label=f"{queue_name} queue")
        cpu_resources = cpu_queue.get("ComputeResources") or []
        if not isinstance(cpu_resources, list) or len(cpu_resources) != 1:
            raise ValueError(
                f"DRAGEN CPU queue {queue_name} must render exactly one compute resource."
            )
        cpu_resource = cpu_resources[0]
        if cpu_resource.get("Name") != resource_name:
            raise ValueError(
                f"DRAGEN CPU queue {queue_name} must use compute resource {resource_name}."
            )
        rendered_types = [
            str(item.get("InstanceType") or "") for item in cpu_resource.get("Instances") or []
        ]
        if rendered_types != instance_types:
            raise ValueError(
                f"DRAGEN CPU queue {queue_name} instance types must be {instance_types}."
            )
        if cpu_resource.get("MinCount") != 0:
            raise ValueError(f"DRAGEN CPU queue {queue_name} must set MinCount 0.")
        if not isinstance(cpu_resource.get("MaxCount"), int) or cpu_resource["MaxCount"] < 1:
            raise ValueError(f"DRAGEN CPU queue {queue_name} must set MaxCount at least 1.")
        if ((cpu_resource.get("Efa") or {}).get("Enabled")) is not False:
            raise ValueError(f"DRAGEN CPU queue {queue_name} must keep EFA disabled.")

    for queue_name, resource_name in (
        ("i128shm", "shm128"),
        ("i192shm", "shm192"),
        ("i384shm", "shm384"),
    ):
        queue = queues_by_name[queue_name]
        if queue.get("CapacityType") != "SPOT":
            raise ValueError(f"DRAGEN SHM queue {queue_name} must use SPOT capacity.")
        if queue.get("ComputeSettings"):
            raise ValueError(f"DRAGEN SHM queue {queue_name} must not mount local storage.")
        queue_ami = ((queue.get("Image") or {}).get("CustomAmi") or "").strip()
        if queue_ami != inputs.backport.image_ami_id:
            raise ValueError(
                f"DRAGEN SHM queue {queue_name} AMI does not match the qualified image."
            )
        _validate_dragen_cpu_node(queue, inputs, label=f"{queue_name} queue")
        resources = queue.get("ComputeResources") or []
        if not isinstance(resources, list) or len(resources) != 1:
            raise ValueError(
                f"DRAGEN SHM queue {queue_name} must render exactly one compute resource."
            )
        resource = resources[0]
        if resource.get("Name") != resource_name:
            raise ValueError(
                f"DRAGEN SHM queue {queue_name} must use compute resource {resource_name}."
            )
        if not resource.get("Instances"):
            raise ValueError(f"DRAGEN SHM queue {queue_name} must contain instance types.")
        if resource.get("MinCount") != 0:
            raise ValueError(f"DRAGEN SHM queue {queue_name} must set MinCount 0.")
        if not isinstance(resource.get("MaxCount"), int) or resource["MaxCount"] < 1:
            raise ValueError(f"DRAGEN SHM queue {queue_name} must set MaxCount at least 1.")
        if ((resource.get("Efa") or {}).get("Enabled")) is not False:
            raise ValueError(f"DRAGEN SHM queue {queue_name} must keep EFA disabled.")

    cookbook_uri = (
        (((payload.get("DevSettings") or {}).get("Cookbook") or {}).get("ChefCookbook")) or ""
    ).strip()
    if cookbook_uri != inputs.backport.cookbook_bundle_uri:
        raise ValueError("DRAGEN cluster cookbook does not match the pinned backport manifest.")


def _validate_dragen_node_policy_and_action(
    node: dict[str, Any],
    inputs: DragenCreateInputs,
    *,
    label: str,
    expected_role: str,
) -> None:
    policies = [
        str(item.get("Policy") or "")
        for item in ((node.get("Iam") or {}).get("AdditionalIamPolicies") or [])
    ]
    if policies.count(inputs.license_policy_arn) != 1:
        raise ValueError(f"{label} must attach the configured license policy exactly once.")

    action = (node.get("CustomActions") or {}).get("OnNodeConfigured") or {}
    script = str(action.get("Script") or "")
    if not script.endswith("/post_install_almalinux8_dragen.sh"):
        raise ValueError(f"{label} must use the AlmaLinux DRAGEN bootstrap wrapper.")
    args = [str(value) for value in action.get("Args") or []]
    if len(args) != 6 or args[-2] != inputs.license_secret_arn or args[-1] != expected_role:
        raise ValueError(
            f"{label} must pass the configured license secret ARN as arg 5 "
            f"and role {expected_role!r} as arg 6."
        )


def _validate_dragen_cpu_node(
    node: dict[str, Any],
    inputs: DragenCreateInputs,
    *,
    label: str,
) -> None:
    policies = [
        str(item.get("Policy") or "")
        for item in ((node.get("Iam") or {}).get("AdditionalIamPolicies") or [])
    ]
    if inputs.license_policy_arn in policies:
        raise ValueError(f"{label} must not attach the DRAGEN license policy.")

    action = (node.get("CustomActions") or {}).get("OnNodeConfigured") or {}
    script = str(action.get("Script") or "")
    if not script.endswith("/post_install_rhel8_dragen.sh"):
        raise ValueError(f"{label} must use the base AlmaLinux-compatible bootstrap.")
    args = [str(value) for value in action.get("Args") or []]
    if len(args) != 5 or args[-1] != "cpu":
        raise ValueError(f"{label} must pass explicit CPU role as arg 5.")


def _noop_heartbeat_result() -> Any:
    """Return a stub HeartbeatResult-like object for the no-op path."""
    from types import SimpleNamespace

    return SimpleNamespace(
        success=False,
        topic_arn="",
        schedule_name="",
        role_arn="",
        error="skipped",
    )


def _prompt_select(label: str, choices: List[str]) -> str:
    """Prompt the user to choose one value from *choices*."""
    typer.echo(f"Select {label}:")
    for idx, choice in enumerate(choices, start=1):
        typer.echo(f"  [{idx}] {choice}")

    while True:
        raw = typer.prompt("Enter selection number", default="1").strip()
        if not raw.isdigit():
            typer.echo("Invalid selection. Enter a number.")
            continue
        index = int(raw)
        if 1 <= index <= len(choices):
            return choices[index - 1]
        typer.echo("Invalid selection. Enter one of the listed numbers.")


FSX_PROMPT_OPTIONS = [
    "1200",
    "2400",
    "4800",
    "7200",
    "9600",
    "12000",
    "14400",
]
FSX_SIZE_RULE_TEXT = "1200 GiB, 2400 GiB, or any value >= 4800 GiB divisible by 2400 GiB"
FSX_DEPLOYMENT_TYPES = ("SCRATCH_2", "PERSISTENT_2")
FSX_PERSISTENT2_THROUGHPUT_TIERS = ("125", "250", "500", "1000")
DEFAULT_FSX_DEPLOYMENT_TYPE = "PERSISTENT_2"
DEFAULT_FSX_PERSISTENT2_THROUGHPUT_MBPS_PER_TIB = "1000"
FSX_CHOICE_DEFAULTS = {
    "fsx_deployment_type": DEFAULT_FSX_DEPLOYMENT_TYPE,
    "fsx_throughput_mbps_per_tib": DEFAULT_FSX_PERSISTENT2_THROUGHPUT_MBPS_PER_TIB,
}
APPROVED_HEADNODE_INSTANCE_TYPES = (
    "r7i.2xlarge",
    "r7i.4xlarge",
    "r7i.8xlarge",
    "r7i.16xlarge",
)
HEADNODE_INSTANCE_TYPE_RULE_TEXT = "one of the approved headnode instance types: " + ", ".join(
    APPROVED_HEADNODE_INSTANCE_TYPES
)


def _is_valid_fsx_size(value: str) -> bool:
    """Return True when *value* is a valid FSx Lustre storage capacity."""
    if not value or not value.isdigit():
        return False
    size = int(value)
    if size == 1200 or size == 2400:
        return True
    return size >= 4800 and size % 2400 == 0


def _resolve_fsx_size(cfg: Any, *, non_interactive: bool) -> str:
    """Resolve an explicit FSx size, prompting for interactive creates."""
    from daylily_ec.config.triplets import get_effective_default, resolve_value

    triplet = cfg.ephemeral_cluster.config.get("fsx_fs_size")
    configured = resolve_value(triplet) if triplet is not None else ""
    default_value = get_effective_default(cfg, "fsx_fs_size", "4800") or "4800"

    if configured:
        configured = configured.strip()
        if _is_valid_fsx_size(configured):
            return configured
        raise ValueError(
            f"Invalid FSx size '{configured}'. Allowed sizes are {FSX_SIZE_RULE_TEXT}."
        )

    if default_value:
        default_value = default_value.strip()
        if not _is_valid_fsx_size(default_value):
            raise ValueError(
                f"Invalid FSx size '{default_value}'. Allowed sizes are {FSX_SIZE_RULE_TEXT}."
            )

    if non_interactive:
        raise ValueError(
            "Non-interactive cluster creation requires an explicit fsx_fs_size set value."
        )

    typer.echo("Choose FSx Lustre file system size (GiB).")
    typer.echo("Smallest allowed sizes:")
    for idx, option in enumerate(FSX_PROMPT_OPTIONS, start=1):
        typer.echo(f"  [{idx}] {option}")

    while True:
        raw = typer.prompt(
            "Enter selection number or explicit size",
            default=default_value,
        ).strip()
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(FSX_PROMPT_OPTIONS):
                return FSX_PROMPT_OPTIONS[index - 1]
        if _is_valid_fsx_size(raw):
            return raw
        typer.echo(
            "Invalid FSx size. Enter one of the listed numbers or a value matching: "
            f"{FSX_SIZE_RULE_TEXT}."
        )


def _resolve_fsx_choice(
    cfg: Any,
    *,
    key: str,
    label: str,
    choices: tuple[str, ...],
    non_interactive: bool,
) -> str:
    """Resolve one explicit FSx choice or prompt from the allowed catalog."""
    from daylily_ec.config.triplets import get_effective_default, resolve_value

    triplet = cfg.ephemeral_cluster.config.get(key)
    configured = resolve_value(triplet).strip().upper() if triplet is not None else ""
    if configured:
        if configured not in choices:
            raise ValueError(f"Invalid {key} {configured!r}; expected one of {', '.join(choices)}.")
        return configured
    if non_interactive:
        raise ValueError(f"Non-interactive cluster creation requires an explicit {key} set value.")

    default_value = (
        get_effective_default(cfg, key, FSX_CHOICE_DEFAULTS.get(key, ""))
        .strip()
        .upper()
    )
    if default_value and default_value not in choices:
        raise ValueError(
            f"Invalid default {key} {default_value!r}; expected one of {', '.join(choices)}."
        )
    typer.echo(f"Choose {label}.")
    for index, choice in enumerate(choices, start=1):
        typer.echo(f"  [{index}] {choice}")
    default_index = str(choices.index(default_value) + 1) if default_value else None
    while True:
        raw = typer.prompt(
            "Enter selection number",
            default=default_index,
        ).strip()
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1]
        normalized = raw.upper()
        if normalized in choices:
            return normalized
        typer.echo("Invalid selection. Enter one of the listed numbers or values.")


def _resolve_fsx_deployment_type(cfg: Any, *, non_interactive: bool) -> str:
    return _resolve_fsx_choice(
        cfg,
        key="fsx_deployment_type",
        label="FSx for Lustre deployment type",
        choices=FSX_DEPLOYMENT_TYPES,
        non_interactive=non_interactive,
    )


def _resolve_fsx_persistent2_throughput(cfg: Any, *, non_interactive: bool) -> str:
    return _resolve_fsx_choice(
        cfg,
        key="fsx_throughput_mbps_per_tib",
        label="PERSISTENT_2 throughput (MB/s/TiB)",
        choices=FSX_PERSISTENT2_THROUGHPUT_TIERS,
        non_interactive=non_interactive,
    )


def _resolve_persistent2_config(
    cfg: Any,
    *,
    deployment_type: str,
    fsx_size: str,
    non_interactive: bool,
) -> Optional[dict[str, str]]:
    """Return the exact explicit P2 contract, or ``None`` for managed Scratch.

    Existing configs that omit the new deployment field retain their current
    managed Scratch behavior. Once PERSISTENT_2 is requested, every P2-specific
    value must be explicitly set; DYEC does not infer or downgrade any field.
    """

    if deployment_type == "SCRATCH_2":
        return None
    if deployment_type != "PERSISTENT_2":
        raise ValueError(
            "fsx_deployment_type must be SCRATCH_2 or the supported PERSISTENT_2 contract."
        )

    expected = {
        "fsx_lustre_version": "2.15",
        "fsx_metadata_mode": "AUTOMATIC",
        "fsx_encryption_mode": "AWS_MANAGED_FSX",
        "fsx_owner": "DYEC",
        "fsx_lifecycle": "CLUSTER_BOUND",
        "sweep_protection_tag": "dyec-preserve=true",
    }
    resolved: dict[str, str] = {"fsx_deployment_type": deployment_type}
    if not _is_valid_fsx_size(fsx_size):
        raise ValueError(
            "PERSISTENT_2 requires explicit fsx_fs_size matching: "
            f"{FSX_SIZE_RULE_TEXT}; received {fsx_size!r}."
        )
    resolved["fsx_fs_size"] = fsx_size

    throughput = _resolve_fsx_persistent2_throughput(
        cfg,
        non_interactive=non_interactive,
    )
    resolved["fsx_throughput_mbps_per_tib"] = throughput

    for key, required_value in expected.items():
        triplet = cfg.ephemeral_cluster.config.get(key)
        value = triplet.set_value.strip() if triplet is not None else ""
        if value != required_value:
            raise ValueError(
                f"PERSISTENT_2 requires explicit {key}={required_value}; received {value!r}."
            )
        resolved[key] = value
    return resolved


def _is_valid_headnode_instance_type(value: str) -> bool:
    """Return True when *value* is an approved headnode instance type."""
    return value in APPROVED_HEADNODE_INSTANCE_TYPES


def _format_idle_cost_summary(estimate: IdleClusterCostEstimate) -> str:
    """Render a compact configured-idle cost breakdown."""
    fsx_profile = estimate.fsx_deployment_type
    if estimate.fsx_throughput_mbps_per_tib:
        fsx_profile += f" {estimate.fsx_throughput_mbps_per_tib} MB/s/TiB"
    return (
        f"[bold]Idle total:[/]  ${estimate.total_hourly_usd:.4f}/hour\n"
        f"  Headnode {estimate.headnode_instance_type}: "
        f"${estimate.headnode_hourly_usd:.4f}/hour\n"
        f"  Root EBS {estimate.root_volume_type} {estimate.root_volume_gib} GiB: "
        f"${estimate.root_volume_hourly_usd:.4f}/hour\n"
        f"  FSx {fsx_profile} {estimate.fsx_capacity_gib} GiB: "
        f"${estimate.fsx_hourly_usd:.4f}/hour\n"
        f"  Public IPv4: ${estimate.public_ipv4_hourly_usd:.4f}/hour"
    )


def _read_headnode_root_volume_spec(template_yaml: str) -> tuple[str, int]:
    """Read the exact headnode root-volume type and size from a cluster template."""
    import yaml

    try:
        payload = yaml.safe_load(Path(template_yaml).read_text(encoding="utf-8"))
        root_volume = payload["HeadNode"]["LocalStorage"]["RootVolume"]
        volume_type = str(root_volume["VolumeType"]).strip().lower()
        size_gib = int(root_volume["Size"])
    except (FileNotFoundError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        raise ValueError(
            f"Could not resolve HeadNode.LocalStorage.RootVolume from {template_yaml}: {exc}"
        ) from exc
    if not volume_type:
        raise ValueError("Headnode root-volume type must not be empty.")
    if size_gib <= 0:
        raise ValueError("Headnode root-volume size must be positive.")
    extra_pricing_fields = sorted(
        key for key in ("Iops", "Throughput") if root_volume.get(key) is not None
    )
    if extra_pricing_fields:
        raise ValueError(
            "Idle-cost pricing does not support explicit headnode root-volume "
            f"{', '.join(extra_pricing_fields)} fields."
        )
    return volume_type, size_gib


def _resolve_headnode_instance_type(cfg: Any, *, non_interactive: bool) -> str:
    """Resolve the headnode instance type from the approved type menu."""
    from daylily_ec.config.triplets import get_effective_default, resolve_value

    triplet = cfg.ephemeral_cluster.config.get("headnode_instance_type")
    configured = resolve_value(triplet) if triplet is not None else ""
    default_value = (
        get_effective_default(cfg, "headnode_instance_type", APPROVED_HEADNODE_INSTANCE_TYPES[0])
        or APPROVED_HEADNODE_INSTANCE_TYPES[0]
    )

    if configured:
        configured = configured.strip()
        if _is_valid_headnode_instance_type(configured):
            return configured
        raise ValueError(
            f"Invalid headnode instance type '{configured}'. It must be "
            f"{HEADNODE_INSTANCE_TYPE_RULE_TEXT}."
        )

    if default_value:
        default_value = default_value.strip()
        if not _is_valid_headnode_instance_type(default_value):
            raise ValueError(
                f"Invalid headnode instance type '{default_value}'. It must be "
                f"{HEADNODE_INSTANCE_TYPE_RULE_TEXT}."
            )

    if non_interactive:
        return default_value

    typer.echo("Choose headnode instance type (approved types, smallest to largest).")
    for idx, option in enumerate(APPROVED_HEADNODE_INSTANCE_TYPES, start=1):
        default_suffix = " (default)" if option == default_value else ""
        typer.echo(f"  [{idx}] {option}{default_suffix}")

    while True:
        raw = typer.prompt(
            "Enter selection number or approved instance type",
            default=default_value,
        ).strip()
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(APPROVED_HEADNODE_INSTANCE_TYPES):
                return APPROVED_HEADNODE_INSTANCE_TYPES[index - 1]
        if _is_valid_headnode_instance_type(raw):
            return raw
        typer.echo(
            "Invalid headnode instance type. Enter one of the listed numbers or "
            f"{HEADNODE_INSTANCE_TYPE_RULE_TEXT}."
        )


def _resolve_config_value(
    cfg: Any,
    key: str,
    label: str,
    *,
    non_interactive: bool,
    default_fallback: str = "",
    required: bool = True,
    allow_empty: bool = False,
) -> str:
    """Resolve a triplet-backed config value, prompting when needed."""
    from daylily_ec.config.triplets import get_effective_default, resolve_value

    triplet = cfg.ephemeral_cluster.config.get(key)
    if triplet is not None:
        resolved = resolve_value(triplet)
        if resolved:
            return resolved

    default_value = get_effective_default(cfg, key, default_fallback)
    if non_interactive:
        return default_value

    if allow_empty and not required and not default_value:
        return typer.prompt(f"{label} (leave blank to skip)", default="").strip()

    prompt_default = default_value if default_value else None
    while True:
        value = typer.prompt(label, default=prompt_default).strip()
        if value:
            return value
        if allow_empty and not required:
            return ""
        typer.echo(f"{label} cannot be empty.")


def _resolve_nonprompt_config_value(cfg: Any, key: str, default_value: str = "") -> str:
    """Resolve a config value without adding an interactive prompt."""
    from daylily_ec.config.triplets import get_effective_default, resolve_value

    triplet = cfg.ephemeral_cluster.config.get(key)
    if triplet is not None:
        resolved = resolve_value(triplet)
        if resolved:
            return resolved.strip()
    return (get_effective_default(cfg, key, default_value) or "").strip()


def _resolve_derived_max_count(
    cfg: Any,
    key: str,
    parent_value: int,
) -> str:
    """Expand the prompted public family count to one template subtype."""
    from daylily_ec.config.triplets import resolve_derived_max_count

    return resolve_derived_max_count(cfg, key, parent_value)


def _resolve_nonprompt_bool_config(cfg: Any, key: str, default_value: str = "false") -> bool:
    """Resolve a non-interactive boolean config value with strict validation."""
    raw = _resolve_nonprompt_config_value(cfg, key, default_value).strip().lower()
    if raw in ("1", "true", "yes", "y", "on"):
        return True
    if raw in ("0", "false", "no", "n", "off", ""):
        return False
    raise ValueError(f"{key} must be true or false, got '{raw}'.")


def _prompt_s3_role_choice(label: str, candidates: List[str], *, default_value: str = "") -> str:
    typer.echo(f"{label} candidates:")
    for index, candidate in enumerate(candidates, start=1):
        typer.echo(f"  {index}. {candidate}")
    typer.echo("Enter a selection number, or enter an explicit s3:// URI.")

    prompt_default = default_value if default_value else None
    while True:
        raw = typer.prompt(f"{label} selection or URI", default=prompt_default).strip()
        if raw.isdigit():
            selected = int(raw)
            if 1 <= selected <= len(candidates):
                return candidates[selected - 1]
            typer.echo(f"Selection must be between 1 and {len(candidates)}.")
            continue
        if raw:
            return raw
        typer.echo(f"{label} cannot be empty.")


def _resolve_s3_role_config_value(
    cfg: Any,
    key: str,
    label: str,
    *,
    role: str,
    aws_ctx: Any,
    non_interactive: bool,
) -> str:
    """Resolve an S3 role URI, using interactive discovery only for prompts."""
    from daylily_ec.aws.s3 import list_role_candidate_uris
    from daylily_ec.config.triplets import (
        get_effective_default,
        is_auto_select_disabled,
        resolve_value,
    )

    triplet = cfg.ephemeral_cluster.config.get(key)
    if triplet is not None:
        resolved = resolve_value(triplet)
        if resolved:
            return resolved

    default_value = get_effective_default(cfg, key, "")
    if non_interactive:
        return default_value

    candidates = list_role_candidate_uris(aws_ctx, role=role)
    if len(candidates) == 1 and not is_auto_select_disabled():
        typer.echo(f"{label}: auto-selected only valid candidate {candidates[0]}")
        return candidates[0]
    if candidates:
        return _prompt_s3_role_choice(label, candidates, default_value=default_value)

    typer.echo(f"No valid {label} candidates found. Enter an explicit S3 URI instead.")
    prompt_default = default_value if default_value else None
    while True:
        value = typer.prompt(label, default=prompt_default).strip()
        if value:
            return value
        typer.echo(f"{label} cannot be empty.")


def validate_cluster_name(cluster_name: str) -> str:
    """Validate the Daylily-supported ParallelCluster cluster name contract."""
    value = (cluster_name or "").strip()
    if not value:
        raise ValueError(f"Cluster name is required. It must be {CLUSTER_NAME_RULE_TEXT}.")
    if len(value) < CLUSTER_NAME_MIN_LENGTH or len(value) > CLUSTER_NAME_MAX_LENGTH:
        raise ValueError(f"Invalid cluster name '{value}'. It must be {CLUSTER_NAME_RULE_TEXT}.")
    if not CLUSTER_NAME_PATTERN.fullmatch(value):
        raise ValueError(
            f"Invalid cluster name '{value}'. It must be {CLUSTER_NAME_RULE_TEXT}. "
            "Numbers are allowed after the first character."
        )
    return value


def normalize_enforce_budget(value: str) -> str:
    text = str(value or "").strip().strip('"').strip("'").lower()
    if text in {"true", "1", "yes", "enforce", "enforced"}:
        return "true"
    if text in {"skip", "false", "0", "no"}:
        return "skip"
    raise ValueError(f"enforce_budget must be one of true, enforce, skip, or false; got {value!r}")


def _validate_cluster_name(cluster_name: str) -> str:
    return validate_cluster_name(cluster_name)


def _default_cluster_name() -> str:
    user = _os.environ.get("USER", "").strip()
    return f"{user}-clu" if user else ""


def _resolve_cluster_name(cfg: Any, *, non_interactive: bool) -> str:
    """Resolve and validate the cluster name before any AWS work begins."""
    from daylily_ec.config.triplets import get_effective_default, resolve_value

    triplet = cfg.ephemeral_cluster.config.get("cluster_name")
    if triplet is not None:
        resolved = resolve_value(triplet)
        if resolved:
            try:
                return _validate_cluster_name(resolved)
            except ValueError as exc:
                if non_interactive:
                    raise
                typer.echo(str(exc))

    environment_default = _default_cluster_name()
    default_value = (
        get_effective_default(cfg, "cluster_name", environment_default) or environment_default
    )
    if non_interactive:
        return _validate_cluster_name(default_value)

    prompt_default = default_value if default_value else None
    while True:
        value = typer.prompt("Cluster name", default=prompt_default).strip()
        try:
            return _validate_cluster_name(value)
        except ValueError as exc:
            typer.echo(str(exc))


def _require_values(values: Dict[str, str]) -> Optional[str]:
    """Return an error message if any required values are blank."""
    missing = [label for label, value in values.items() if not value]
    if not missing:
        return None
    return "Missing required values: " + ", ".join(missing)


def _resolve_explicit_subnet_id(
    ec2_client: Any,
    cfg: Any,
    key: str,
    *,
    label: str,
    region_az: str,
) -> str:
    """Return an explicit configured subnet after live EC2/AZ validation."""
    from daylily_ec.config.triplets import resolve_value

    triplet = cfg.ephemeral_cluster.config.get(key)
    configured = resolve_value(triplet) if triplet is not None else ""
    configured = configured.strip()
    if not configured:
        return ""

    try:
        response = ec2_client.describe_subnets(SubnetIds=[configured])
    except Exception as exc:
        raise ValueError(
            f"Configured {label} does not exist or is inaccessible: {configured}"
        ) from exc

    subnets = response.get("Subnets", [])
    if not subnets:
        raise ValueError(f"Configured {label} does not exist: {configured}")
    subnet = subnets[0]
    actual_az = str(subnet.get("AvailabilityZone", ""))
    if actual_az != region_az:
        raise ValueError(
            f"Configured {label} {configured} is in {actual_az}, expected {region_az}."
        )
    state = str(subnet.get("State", ""))
    if state != "available":
        raise ValueError(f"Configured {label} {configured} is {state}, expected available.")
    return configured


def _resolve_subnet_vpc_id(ec2_client: Any, subnet_id: str, *, label: str) -> str:
    """Return the VPC that owns a resolved subnet."""
    subnet_id = subnet_id.strip()
    if not subnet_id:
        return ""
    try:
        response = ec2_client.describe_subnets(SubnetIds=[subnet_id])
    except Exception as exc:
        raise ValueError(f"Unable to resolve VPC for {label} {subnet_id}.") from exc
    subnets = response.get("Subnets", [])
    if not subnets:
        raise ValueError(f"Unable to resolve VPC for {label} {subnet_id}: subnet not found.")
    vpc_id = str(subnets[0].get("VpcId", "")).strip()
    if not vpc_id:
        raise ValueError(f"Unable to resolve VPC for {label} {subnet_id}: missing VpcId.")
    return vpc_id


def _subnet_has_public_default_route(ec2_client: Any, subnet_id: str, *, label: str) -> bool:
    """Return whether a subnet's active default route targets an internet gateway."""
    subnet_id = subnet_id.strip()
    if not subnet_id:
        return False
    try:
        subnet_response = ec2_client.describe_subnets(SubnetIds=[subnet_id])
    except Exception as exc:
        raise ValueError(f"Unable to inspect route table for {label} {subnet_id}.") from exc
    subnets = subnet_response.get("Subnets", [])
    if not subnets:
        raise ValueError(
            f"Unable to inspect route table for {label} {subnet_id}: subnet not found."
        )
    vpc_id = str(subnets[0].get("VpcId", "")).strip()
    if not vpc_id:
        raise ValueError(f"Unable to inspect route table for {label} {subnet_id}: missing VpcId.")

    try:
        associated = ec2_client.describe_route_tables(
            Filters=[{"Name": "association.subnet-id", "Values": [subnet_id]}]
        ).get("RouteTables", [])
        route_tables = associated
        if not route_tables:
            vpc_tables = ec2_client.describe_route_tables(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            ).get("RouteTables", [])
            route_tables = [
                table
                for table in vpc_tables
                if any(assoc.get("Main") for assoc in table.get("Associations", []) or [])
            ]
    except Exception as exc:
        raise ValueError(f"Unable to inspect route table for {label} {subnet_id}.") from exc

    for table in route_tables:
        for route in table.get("Routes", []) or []:
            if str(route.get("State", "")) != "active":
                continue
            destination = str(route.get("DestinationCidrBlock", ""))
            gateway = str(route.get("GatewayId", ""))
            if destination == "0.0.0.0/0" and gateway.startswith("igw-"):
                return True
    return False


@dataclass(frozen=True)
class _PostCreateInputs:
    enforce_budget: str
    budget_email: str
    budget_amount: str
    global_budget_amount: str
    allowed_budget_users: str
    cost_center_name: str
    cost_center_monthly_cap_usd: str
    cost_center_allowed_users: str
    heartbeat_email: str
    heartbeat_schedule: str
    heartbeat_scheduler_role_arn: str


def _default_budget_email() -> str:
    return _os.environ.get("DAY_CONTACT_EMAIL") or DEFAULT_BUDGET_EMAIL


def _resolve_post_create_inputs(
    cfg: Any,
    *,
    non_interactive: bool,
    budget_email_default: str,
    allowed_budget_users_default: str,
    cluster_name: str,
    disable_budget_enforcement: bool,
    slurm_accounting: str,
    heartbeat_email_default: Optional[str] = None,
) -> _PostCreateInputs:
    """Resolve budget and heartbeat inputs once before the create phase."""
    if disable_budget_enforcement:
        enforce_budget = "skip"
    else:
        enforce_budget = normalize_enforce_budget(
            _resolve_config_value(
                cfg,
                "enforce_budget",
                "Enforce budget",
                non_interactive=non_interactive,
                default_fallback="true",
            )
            or "true"
        )
    budget_email = (
        _resolve_config_value(
            cfg,
            "budget_email",
            "Budget email",
            non_interactive=non_interactive,
            default_fallback=budget_email_default,
        )
        or budget_email_default
    )
    configured_budget_email = _resolve_nonprompt_config_value(cfg, "budget_email", "")
    budget_amount = (
        _resolve_config_value(
            cfg,
            "budget_amount",
            "Budget amount",
            non_interactive=non_interactive,
            default_fallback="200",
        )
        or "200"
    )
    global_budget_amount = (
        _resolve_config_value(
            cfg,
            "global_budget_amount",
            "Global budget amount",
            non_interactive=non_interactive,
            default_fallback="1000",
        )
        or "1000"
    )
    allowed_budget_users = (
        _resolve_config_value(
            cfg,
            "allowed_budget_users",
            "Allowed budget users",
            non_interactive=non_interactive,
            default_fallback=allowed_budget_users_default,
        )
        or allowed_budget_users_default
    )
    cost_center_name = ""
    cost_center_monthly_cap_usd = ""
    cost_center_allowed_users = ""
    if slurm_accounting == "on":
        cost_center_name = _resolve_config_value(
            cfg,
            "cost_center_name",
            "Cost center name",
            non_interactive=non_interactive,
            default_fallback=f"{cluster_name}-ccenter",
        )
        cost_center_monthly_cap_usd = _resolve_config_value(
            cfg,
            "cost_center_monthly_cap_usd",
            "Cost center monthly cap (USD)",
            non_interactive=non_interactive,
            default_fallback=DEFAULT_COST_CENTER_MONTHLY_CAP_USD,
        )
        cost_center_allowed_users = _resolve_config_value(
            cfg,
            "cost_center_allowed_users",
            "Cost center allowed users (comma-separated)",
            non_interactive=non_interactive,
            default_fallback=allowed_budget_users_default,
        )
        try:
            from daylily_ec.aws.cost_centers import CostCenterError, validate_cost_center_name

            validate_cost_center_name(cost_center_name)
            cap = Decimal(cost_center_monthly_cap_usd)
            if cap <= 0:
                raise ValueError("cost_center_monthly_cap_usd must be greater than zero.")
            allowed_users = tuple(
                value.strip() for value in cost_center_allowed_users.split(",") if value.strip()
            )
            if not allowed_users:
                raise ValueError("cost_center_allowed_users must name at least one user.")
            if any(any(character.isspace() for character in value) for value in allowed_users):
                raise ValueError("cost_center_allowed_users entries must not contain whitespace.")
        except (CostCenterError, InvalidOperation, ValueError) as exc:
            raise ValueError(f"Invalid cost-center input: {exc}") from exc
    heartbeat_default = (
        budget_email
        if configured_budget_email
        else (heartbeat_email_default or budget_email)
    )
    heartbeat_email = (
        _resolve_config_value(
            cfg,
            "heartbeat_email",
            "Heartbeat email",
            non_interactive=non_interactive,
            default_fallback=heartbeat_default,
            required=False,
            allow_empty=True,
        )
        or heartbeat_default
    )
    heartbeat_schedule = (
        _resolve_config_value(
            cfg,
            "heartbeat_schedule",
            "Heartbeat schedule",
            non_interactive=non_interactive,
            default_fallback="rate(6 hours)",
            required=False,
        )
        or "rate(6 hours)"
    )
    heartbeat_scheduler_role_arn = (
        _resolve_config_value(
            cfg,
            "heartbeat_scheduler_role_arn",
            "Heartbeat scheduler role ARN",
            non_interactive=non_interactive,
            required=False,
            allow_empty=True,
        )
        or ""
    )

    return _PostCreateInputs(
        enforce_budget=enforce_budget,
        budget_email=budget_email,
        budget_amount=budget_amount,
        global_budget_amount=global_budget_amount,
        allowed_budget_users=allowed_budget_users,
        cost_center_name=cost_center_name,
        cost_center_monthly_cap_usd=cost_center_monthly_cap_usd,
        cost_center_allowed_users=cost_center_allowed_users,
        heartbeat_email=heartbeat_email,
        heartbeat_schedule=heartbeat_schedule,
        heartbeat_scheduler_role_arn=heartbeat_scheduler_role_arn,
    )


def _build_connection_command(
    cluster_name: str,
    *,
    region: str,
    profile: str,
) -> str:
    """Return the final connection/help command shown after create completes."""
    return (
        "daylily-ssh-into-headnode "
        f"--profile {shlex.quote(profile)} "
        f"--region {shlex.quote(region)} "
        f"--cluster {shlex.quote(cluster_name)}"
    )


def _maybe_say_onward() -> None:
    """Play the optional completion cue when macOS `say` is available."""
    try:
        detect_result = subprocess.run(
            ["/bin/sh", "-lc", "command -v say >/dev/null 2>&1"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        if detect_result.returncode == 0:
            subprocess.run(
                ["say", "Onward to daylily!"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
    except Exception:
        logger.debug("Optional speech cue failed.", exc_info=True)


# ---------------------------------------------------------------------------
# Full create workflow (CP-017)
# ---------------------------------------------------------------------------


def run_create_workflow(
    region_az: str,
    *,
    profile: Optional[str] = None,
    config_path: Optional[str] = None,
    cluster_type: str = DEFAULT_CREATE_CLUSTER_TYPE,
    pass_on_warn: bool = False,
    debug: bool = False,
    non_interactive: bool = False,
    disable_budget_enforcement: bool = False,
    budget_project: Optional[str] = None,
    global_spot_max_cost: float = DEFAULT_GLOBAL_SPOT_MAX_COST,
    spot_cost_limit_pct: float = DEFAULT_SPOT_COST_LIMIT_PCT,
    write_spot_pricing_warn_threshold: float = DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
    repo_overrides: Optional[Dict[str, str]] = None,
    regional_cluster_cap: Optional[int] = None,
    acknowledge_regional_cap_increase: bool = False,
    acknowledge_regional_cap_risk: bool = False,
    slurm_accounting: str = "on",
    create_slurm_accounting_if_missing: bool = False,
    acknowledge_slurm_accounting_create_cost: bool = False,
    budget_email_override: Optional[str] = None,
    budget_email_fallback: Optional[str] = None,
) -> int:
    """End-to-end cluster creation: preflight → create → post-create.

    Returns one of the ``EXIT_*`` constants.
    """
    from daylily_ec.aws.budgets import ensure_cluster_budget, ensure_global_budget
    from daylily_ec.aws.cost_centers import (
        DEFAULT_COST_CENTER_HOME_REGION,
        DEFAULT_COST_CENTER_TABLE,
        DEFAULT_COST_CENTER_USAGE_TABLE,
        ensure_active_cost_center,
    )
    from daylily_ec.aws.cloudformation import (
        StackOutputs,
        derive_stack_name,
        ensure_pcluster_env_stack,
    )
    from daylily_ec.aws.context import AWSContext
    from daylily_ec.aws.ec2 import (
        list_pcluster_tags_budget_policies,
        list_private_subnets,
        list_public_subnets,
        select_policy_arn,
        select_subnet,
    )
    from daylily_ec.aws.heartbeat import ensure_heartbeat
    from daylily_ec.aws.iam import (
        make_iam_preflight_step,
        resolve_scheduler_role,
    )
    from daylily_ec.aws.quotas import make_quota_preflight_step
    from daylily_ec.aws.s3 import (
        ROLE_CONTROL_DATA,
        ROLE_EXPORT_DESTINATION,
        ROLE_REFERENCE,
        ROLE_STAGING,
        make_s3_bucket_preflight_step,
    )
    from daylily_ec.aws.slurm_accounting import (
        empty_slurm_accounting_render_blocks,
    )
    from daylily_ec.aws.ssm import wait_for_ssm_online
    from daylily_ec.aws.spot_pricing import apply_spot_prices
    from daylily_ec.config.triplets import (
        DERIVED_MAX_COUNT_KEYS,
        load_config,
        write_next_run_template,
    )
    from daylily_ec.pcluster.monitor import wait_for_creation
    from daylily_ec.pcluster.runner import (
        create_cluster as pcluster_create,
        dry_run_create,
        list_clusters as pcluster_list_clusters,
        should_break_after_dry_run,
    )
    from daylily_ec.resources import resource_path
    from daylily_ec.render.renderer import CONFIG_DIR, write_init_artifacts
    from daylily_ec.workflow.postcreate_slurm_accounting import (
        validate_postcreate_slurm_accounting_options,
    )

    if debug:
        logging.getLogger("daylily_ec").setLevel(logging.DEBUG)
    try:
        validate_postcreate_slurm_accounting_options(
            slurm_accounting=slurm_accounting,
            create_slurm_accounting_if_missing=create_slurm_accounting_if_missing,
            acknowledge_slurm_accounting_create_cost=(acknowledge_slurm_accounting_create_cost),
        )
    except ValueError as exc:
        logger.error("Slurm accounting option validation failed: %s", exc)
        ui.fail(str(exc))
        return EXIT_VALIDATION_FAILURE
    try:
        cluster_type = normalize_create_cluster_type(cluster_type)
        validate_create_cluster_type_region(cluster_type, region_az)
    except ValueError as exc:
        logger.error("Cluster type validation failed: %s", exc)
        ui.fail(str(exc))
        return EXIT_VALIDATION_FAILURE
    try:
        effective_regional_cluster_cap = validate_regional_cluster_cap_options(
            regional_cluster_cap,
            acknowledge_regional_cap_increase=acknowledge_regional_cap_increase,
            acknowledge_regional_cap_risk=acknowledge_regional_cap_risk,
        )
    except ValueError as exc:
        logger.error("Regional cluster cap option validation failed: %s", exc)
        ui.fail(str(exc))
        return EXIT_VALIDATION_FAILURE
    if budget_project:
        logger.error("--budget-project is retired; cluster budgets are named by cluster name.")
        ui.fail("--budget-project is retired; cluster budgets are named by cluster name.")
        return EXIT_VALIDATION_FAILURE
    try:
        (
            global_spot_max_cost,
            spot_cost_limit_pct,
            write_spot_pricing_warn_threshold,
        ) = validate_spot_pricing_limits(
            global_spot_max_cost=global_spot_max_cost,
            spot_cost_limit_pct=spot_cost_limit_pct,
            write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
        )
    except ValueError as exc:
        logger.error("Spot pricing validation failed: %s", exc)
        ui.fail(str(exc))
        return EXIT_VALIDATION_FAILURE

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # -- 0. Load config -------------------------------------------------------
    effective_config = config_path or "config/daylily_ephemeral_cluster_template.yaml"
    if config_path is None and not Path(effective_config).is_file():
        effective_config = str(resource_path(effective_config))
    cfg = load_config(effective_config)
    ec = cfg.ephemeral_cluster
    legacy_derived_max_counts = sorted(DERIVED_MAX_COUNT_KEYS.intersection(ec.config))
    if legacy_derived_max_counts:
        ui.warn(
            "Ignoring legacy unprompted subtype max-count keys; the five prompted "
            "family max-count values are authoritative: " + ", ".join(legacy_derived_max_counts)
        )

    try:
        dragen_inputs = resolve_dragen_create_inputs(
            cfg,
            cluster_type=cluster_type,
            region_az=region_az,
        )
    except ValueError as exc:
        logger.error("DRAGEN create input validation failed: %s", exc)
        ui.fail(f"DRAGEN create inputs: {exc}")
        return EXIT_VALIDATION_FAILURE
    pcluster_executable = (
        str(dragen_inputs.backport.cli_executable) if dragen_inputs else "pcluster"
    )

    try:
        cluster_name = _resolve_cluster_name(cfg, non_interactive=non_interactive)
    except ValueError as exc:
        logger.error("Cluster name validation failed: %s", exc)
        ui.fail(str(exc))
        return EXIT_VALIDATION_FAILURE

    ui.phase("CREATE INPUTS")
    try:
        post_create_inputs = _resolve_post_create_inputs(
            cfg,
            non_interactive=non_interactive,
            budget_email_default=(budget_email_fallback or _default_budget_email()),
            heartbeat_email_default=_default_budget_email(),
            allowed_budget_users_default="ubuntu",
            cluster_name=cluster_name,
            disable_budget_enforcement=disable_budget_enforcement,
            slurm_accounting=slurm_accounting,
        )
        if (budget_email_override or "").strip():
            post_create_inputs = replace(
                post_create_inputs,
                budget_email=budget_email_override.strip(),
            )
    except ValueError as exc:
        logger.error("Create input validation failed: %s", exc)
        ui.fail(str(exc))
        return EXIT_VALIDATION_FAILURE

    try:
        fsx_deployment_type = _resolve_fsx_deployment_type(
            cfg,
            non_interactive=non_interactive,
        )
        fsx_size = _resolve_fsx_size(
            cfg,
            non_interactive=non_interactive,
        )
        persistent2_config = _resolve_persistent2_config(
            cfg,
            deployment_type=fsx_deployment_type,
            fsx_size=fsx_size,
            non_interactive=non_interactive,
        )
        headnode_instance_type = _resolve_headnode_instance_type(
            cfg,
            non_interactive=non_interactive,
        )
        enable_detailed_monitoring = (
            _resolve_config_value(
                cfg,
                "enable_detailed_monitoring",
                "Enable detailed monitoring",
                non_interactive=non_interactive,
                default_fallback="false",
            )
            or "false"
        )
        delete_local_root = (
            _resolve_config_value(
                cfg,
                "delete_local_root",
                "Delete local root",
                non_interactive=non_interactive,
                default_fallback="false",
            )
            or "false"
        )
        spot_instance_allocation_strategy = (
            _resolve_config_value(
                cfg,
                "spot_instance_allocation_strategy",
                "Spot allocation strategy",
                non_interactive=non_interactive,
                default_fallback="price-capacity-optimized",
            )
            or "price-capacity-optimized"
        )
        template_yaml = resolve_cluster_template_yaml(
            cfg,
            region_az=region_az,
            cluster_type=cluster_type,
            resource_path_fn=resource_path,
        )
        root_volume_type, root_volume_gib = _read_headnode_root_volume_spec(template_yaml)
    except ValueError as exc:
        logger.error("Cluster resource selection validation failed: %s", exc)
        ui.fail(f"Cluster resource selection: {exc}")
        return EXIT_VALIDATION_FAILURE
    except FileNotFoundError as exc:
        logger.error("Cluster template resolution failed: %s", exc)
        ui.fail(f"Cluster template YAML: {exc}")
        return EXIT_VALIDATION_FAILURE

    ui.phase(f"INIT · {cluster_name}")
    ui.detail("Headnode", headnode_instance_type)
    ui.detail("FSx deployment type", fsx_deployment_type)
    ui.detail("FSx capacity", f"{fsx_size} GiB")
    if persistent2_config is not None:
        ui.detail(
            "FSx throughput",
            f"{persistent2_config['fsx_throughput_mbps_per_tib']} MB/s/TiB",
        )
        ui.detail("FSx lifecycle", "Dedicated DYEC-owned CLUSTER_BOUND filesystem")
    else:
        ui.detail("FSx lifecycle", "Dedicated ParallelCluster-managed filesystem")
    ui.info("FSx is writable cluster workspace; S3 output export is explicit, not automatic.")

    # -- 1. AWS Context -------------------------------------------------------
    try:
        aws_ctx = AWSContext.build(region_az, profile=profile)
    except RuntimeError as exc:
        logger.error("AWS context failed: %s", exc)
        ui.fail(f"AWS context: {exc}")
        return EXIT_AWS_FAILURE

    logger.info(
        "AWS context: account=%s user=%s region=%s",
        aws_ctx.account_id,
        aws_ctx.iam_username,
        aws_ctx.region,
    )
    ui.detail("Account", aws_ctx.account_id)
    ui.detail("User", aws_ctx.iam_username)
    ui.detail("Region", f"{aws_ctx.region} ({region_az})")
    ui.detail("Cluster type", cluster_type)

    try:
        idle_cost = estimate_idle_cluster_cost(
            aws_ctx.client("pricing", region_name="us-east-1"),
            region=aws_ctx.region,
            headnode_instance_type=headnode_instance_type,
            root_volume_type=root_volume_type,
            root_volume_gib=root_volume_gib,
            fsx_deployment_type=fsx_deployment_type,
            fsx_capacity_gib=int(fsx_size),
            fsx_throughput_mbps_per_tib=(
                persistent2_config["fsx_throughput_mbps_per_tib"]
                if persistent2_config is not None
                else ""
            ),
        )
    except IdleCostPricingError as exc:
        logger.error("Idle-cost pricing failed closed: %s", exc)
        ui.fail(f"Idle-cost pricing: {exc}. No create-side mutations were attempted.")
        return EXIT_AWS_FAILURE
    ui.detail("Configured idle estimate", f"${idle_cost.total_hourly_usd:.4f}/hour")

    cluster_inventory = pcluster_list_clusters(
        aws_ctx.region,
        profile=aws_ctx.profile,
        executable=pcluster_executable,
    )
    if not cluster_inventory.success:
        detail = cluster_inventory.message or (
            f"pcluster list-clusters failed with exit code {cluster_inventory.returncode}"
        )
        logger.error("Regional ParallelCluster cap check failed closed: %s", detail)
        ui.fail(
            f"Regional ParallelCluster cap check failed closed in {aws_ctx.region}: "
            f"{detail}. No create-side mutations were attempted."
        )
        return EXIT_AWS_FAILURE

    try:
        cap_decision = evaluate_regional_cluster_cap(
            cluster_name=cluster_name,
            records=cluster_inventory.json_body.get("clusters"),
            effective_cap=effective_regional_cluster_cap,
        )
    except ValueError as exc:
        logger.error("Regional ParallelCluster inventory validation failed: %s", exc)
        ui.fail(
            f"Regional ParallelCluster cap check failed closed in {aws_ctx.region}: "
            f"{exc}. No create-side mutations were attempted."
        )
        return EXIT_AWS_FAILURE

    ui.detail(
        "Regional cluster cap",
        (
            f"current={cap_decision.current_count}, "
            f"projected={cap_decision.projected_count}, "
            f"cap={cap_decision.effective_cap}"
        ),
    )
    if cap_decision.projected_count > cap_decision.effective_cap:
        record_evidence = (
            ", ".join(f"{name}={status}" for name, status in cap_decision.counted_records) or "none"
        )
        logger.error(
            "Regional ParallelCluster cap exceeded in %s: current=%d projected=%d cap=%d",
            aws_ctx.region,
            cap_decision.current_count,
            cap_decision.projected_count,
            cap_decision.effective_cap,
        )
        ui.fail(
            f"Regional ParallelCluster cap exceeded in {aws_ctx.region}: "
            f"current non-deleted records={cap_decision.current_count}, "
            f"requested cluster={cluster_name!r}, "
            f"projected={cap_decision.projected_count}, "
            f"cap={cap_decision.effective_cap}. "
            f"Counted records: {record_evidence}."
        )
        return EXIT_VALIDATION_FAILURE

    try:
        dyec_deploy_key_inputs = resolve_dyec_deploy_key_inputs(
            cfg,
            region_az=region_az,
            account_id=aws_ctx.account_id,
            non_interactive=non_interactive,
        )
        dayoa_deploy_key_inputs = resolve_dayoa_deploy_key_inputs(
            cfg,
            region_az=region_az,
            account_id=aws_ctx.account_id,
            non_interactive=non_interactive,
        )
    except ValueError as exc:
        logger.error("Repository deploy-key input validation failed: %s", exc)
        ui.fail(f"Repository deploy-key inputs: {exc}")
        return EXIT_VALIDATION_FAILURE
    ui.detail("DYEC deploy-key secret", "validated")
    ui.detail("DYEC deploy-key policy", dyec_deploy_key_inputs.policy_arn)
    ui.detail("DayOA deploy-key secret", "validated")
    ui.detail("DayOA deploy-key policy", dayoa_deploy_key_inputs.policy_arn)
    try:
        dyec_repo_spec = resolve_configured_headnode_repo_spec(deploy_key_auth=True)
    except RuntimeError as exc:
        logger.error("DYEC repository pinning failed: %s", exc)
        ui.fail(f"DYEC repository source: {exc}")
        return EXIT_VALIDATION_FAILURE
    ui.detail("DYEC repository", dyec_repo_spec.url)
    ui.detail("DYEC ref", dyec_repo_spec.ref)
    if dragen_inputs:
        secret_account = dragen_inputs.license_secret_arn.split(":", 5)[4]
        policy_account = dragen_inputs.license_policy_arn.split(":", 5)[4]
        if secret_account != aws_ctx.account_id or policy_account != aws_ctx.account_id:
            logger.error("DRAGEN secret/policy account does not match the active AWS account.")
            ui.fail("DRAGEN secret and policy ARNs must belong to the active AWS account.")
            return EXIT_VALIDATION_FAILURE
        ui.detail("PCluster backport", dragen_inputs.backport.parallelcluster_version)
        ui.detail("Qualified image", dragen_inputs.backport.image_ami_id)

    # -- 2. PREFLIGHT (Phase 1) -----------------------------------------------
    ui.phase("PREFLIGHT")
    report = PreflightReport(
        run_id=ts,
        cluster_name=cluster_name,
        region=aws_ctx.region,
        region_az=region_az,
        aws_profile=aws_ctx.profile,
        account_id=aws_ctx.account_id,
        caller_arn=aws_ctx.caller_arn,
    )

    # Build preflight steps in §10.5 order
    max_8i = int(
        _resolve_config_value(
            cfg,
            "max_count_8I",
            "Max 8xlarge count",
            non_interactive=non_interactive,
            default_fallback="1",
        )
        or "1"
    )
    max_96i_nvme_text = _resolve_config_value(
        cfg,
        "max_count_96I_NVME",
        "Max 96-vCPU local-NVMe count",
        non_interactive=non_interactive,
    )
    if not max_96i_nvme_text:
        logger.error("Missing required max_count_96I_NVME configuration value.")
        ui.fail("max_count_96I_NVME must be configured explicitly.")
        return EXIT_VALIDATION_FAILURE
    max_96i_nvme = int(max_96i_nvme_text)
    max_128i = int(
        _resolve_config_value(
            cfg,
            "max_count_128I",
            "Max 128xlarge count",
            non_interactive=non_interactive,
            default_fallback="1",
        )
        or "1"
    )
    max_192i = int(
        _resolve_config_value(
            cfg,
            "max_count_192I",
            "Max 192xlarge count",
            non_interactive=non_interactive,
            default_fallback="1",
        )
        or "1"
    )
    max_384i = int(
        _resolve_config_value(
            cfg,
            "max_count_384I",
            "Max 384xlarge count",
            non_interactive=non_interactive,
            default_fallback="1",
        )
        or "1"
    )
    max_count_values: Dict[str, str] = {
        "max_count_8I": str(max_8i),
        "max_count_96I_NVME": str(max_96i_nvme),
        "max_count_128I": str(max_128i),
        "max_count_192I": str(max_192i),
        "max_count_384I": str(max_384i),
        "max_count_128I_C": _resolve_derived_max_count(cfg, "max_count_128I_C", max_128i),
        "max_count_128I_M": _resolve_derived_max_count(cfg, "max_count_128I_M", max_128i),
        "max_count_128I_R": _resolve_derived_max_count(cfg, "max_count_128I_R", max_128i),
        "max_count_128I_NVME": _resolve_derived_max_count(cfg, "max_count_128I_NVME", max_128i),
        "max_count_192I_C": _resolve_derived_max_count(cfg, "max_count_192I_C", max_192i),
        "max_count_192I_M": _resolve_derived_max_count(cfg, "max_count_192I_M", max_192i),
        "max_count_192I_R": _resolve_derived_max_count(cfg, "max_count_192I_R", max_192i),
        "max_count_192I_NVME_C": _resolve_derived_max_count(cfg, "max_count_192I_NVME_C", max_192i),
        "max_count_192I_NVME_M": _resolve_derived_max_count(cfg, "max_count_192I_NVME_M", max_192i),
        "max_count_192I_NVME_R": _resolve_derived_max_count(cfg, "max_count_192I_NVME_R", max_192i),
        "max_count_192I_HUGENVME": _resolve_derived_max_count(
            cfg, "max_count_192I_HUGENVME", max_192i
        ),
        "max_count_384I_NVME_C": _resolve_derived_max_count(cfg, "max_count_384I_NVME_C", max_384i),
        "max_count_384I_NVME_M": _resolve_derived_max_count(cfg, "max_count_384I_NVME_M", max_384i),
        "max_count_384I_NVME_R": _resolve_derived_max_count(cfg, "max_count_384I_NVME_R", max_384i),
    }

    reference_s3_uri = _resolve_s3_role_config_value(
        cfg,
        "reference_s3_uri",
        "Reference S3 URI",
        role=ROLE_REFERENCE,
        aws_ctx=aws_ctx,
        non_interactive=non_interactive,
    )
    control_data_s3_uri = _resolve_s3_role_config_value(
        cfg,
        "control_data_s3_uri",
        "Control-data S3 URI",
        role=ROLE_CONTROL_DATA,
        aws_ctx=aws_ctx,
        non_interactive=non_interactive,
    )
    stage_s3_uri = _resolve_s3_role_config_value(
        cfg,
        "stage_s3_uri",
        "Stage S3 URI",
        role=ROLE_STAGING,
        aws_ctx=aws_ctx,
        non_interactive=non_interactive,
    )
    export_destination_s3_uri = _resolve_s3_role_config_value(
        cfg,
        "export_destination_s3_uri",
        "Export destination S3 URI",
        role=ROLE_EXPORT_DESTINATION,
        aws_ctx=aws_ctx,
        non_interactive=non_interactive,
    )

    preflight_steps: List[PreflightStep] = [
        # 1-2: ToolchainValidator + AWS Identity — implicit via AWSContext.build
        # 3: IAM Permission Validator
        make_iam_preflight_step(aws_ctx, interactive=not non_interactive),
        # 4: ConfigValidator — config load already succeeded above; validate
        # the repository catalog before any AWS mutation because headnode
        # configuration consumes it through day-clone.
        make_repository_catalog_preflight_step(),
        # 5: QuotaValidator
        make_quota_preflight_step(
            aws_ctx,
            max_count_8i=max_8i,
            max_count_96i_nvme=max_96i_nvme,
            max_count_128i=max_128i,
            max_count_192i=max_192i,
            max_count_384i=max_384i,
            non_interactive=non_interactive,
        ),
        # 6: S3 Role Validator
        make_s3_bucket_preflight_step(
            aws_ctx,
            reference_s3_uri=reference_s3_uri,
            control_data_s3_uri=control_data_s3_uri,
            stage_s3_uri=stage_s3_uri,
            export_destination_s3_uri=export_destination_s3_uri,
            profile=aws_ctx.profile,
            interactive=not non_interactive,
        ),
    ]
    from daylily_ec.aws.github_deploy_key import make_github_deploy_key_preflight_step

    preflight_steps.insert(
        1,
        make_github_deploy_key_preflight_step(
            secretsmanager_client=aws_ctx.client("secretsmanager"),
            iam_client=aws_ctx.client("iam"),
            secret_arn=dayoa_deploy_key_inputs.secret_arn,
            policy_arn=dayoa_deploy_key_inputs.policy_arn,
        ),
    )
    preflight_steps.insert(
        1,
        make_github_deploy_key_preflight_step(
            secretsmanager_client=aws_ctx.client("secretsmanager"),
            iam_client=aws_ctx.client("iam"),
            secret_arn=dyec_deploy_key_inputs.secret_arn,
            policy_arn=dyec_deploy_key_inputs.policy_arn,
            check_id="iam.dyec_deploy_key_secret_policy",
            display_name="DYEC",
        ),
    )
    if dragen_inputs:
        from daylily_ec.aws.dragen_license import make_dragen_license_preflight_step
        from daylily_ec.pcluster.backport import (
            make_operational_backport_preflight_step,
        )

        preflight_steps.insert(
            1,
            make_dragen_license_preflight_step(
                secretsmanager_client=aws_ctx.client("secretsmanager"),
                iam_client=aws_ctx.client("iam"),
                secret_arn=dragen_inputs.license_secret_arn,
                policy_arn=dragen_inputs.license_policy_arn,
            ),
        )
        preflight_steps.insert(
            1,
            make_operational_backport_preflight_step(
                s3_client=aws_ctx.client("s3"),
                ec2_client=aws_ctx.client("ec2"),
                backport=dragen_inputs.backport,
            ),
        )

    report = run_preflight(
        report,
        pass_on_warn=pass_on_warn,
        steps=preflight_steps,
    )

    if should_abort(report, pass_on_warn=pass_on_warn):
        logger.error("Preflight aborted — exiting.")
        ui.fail("Preflight aborted — exiting.")
        return exit_code_for(report)

    # -- 3. RESOURCE RESOLUTION -----------------------------------------------
    ui.phase("RESOURCE RESOLUTION")

    # Extract normalized S3 role bindings from preflight report.
    s3_roles = _extract_s3_roles(report)
    reference_s3_uri = _role_uri(s3_roles, "reference")
    control_data_s3_uri = _role_uri(s3_roles, "control_data")
    stage_s3_uri = _role_uri(s3_roles, "staging")
    reference_storage_bucket_name = _role_bucket(s3_roles, "reference")
    from daylily_ec.aws.s3 import normalize_role_s3_uri

    export_destination_s3_uri = _role_uri(s3_roles, "export_destination")
    export_destination_spec = normalize_role_s3_uri(
        export_destination_s3_uri,
        role="export_destination",
    )

    cluster_boot_s3_base_uri = _s3_uri_join(
        reference_s3_uri,
        "runtime_assets",
        "cluster_boot_config",
    )

    explicit_core_resources = all(
        _has_explicit_set_value(cfg, key)
        for key in ("public_subnet_id", "private_subnet_id", "iam_policy_arn")
    )

    # 3a. Resolve the only live-resource choice that can remain interactive.
    # When an account has multiple matching policies, collect that selection
    # before waiting for the baseline stack.
    iam_client = aws_ctx.client("iam")
    policy_arns = list_pcluster_tags_budget_policies(iam_client)
    iam_t = ec.config.get("iam_policy_arn")
    policy_arn = select_policy_arn(
        policy_arns,
        cfg_action=iam_t.action if iam_t else "",
        cfg_set_value=iam_t.set_value if iam_t else "",
        cfg_fallback="",
    )
    if not policy_arn and iam_t and _has_explicit_set_value(cfg, "iam_policy_arn"):
        policy_arn = iam_t.set_value.strip()
    if not policy_arn and not non_interactive and policy_arns:
        policy_arn = _prompt_select("IAM policy ARN", policy_arns)

    ui.ok("Create inputs resolved; provisioning can now run unattended")

    # 3b. Baseline CFN stack (first long-running provisioning step)
    stack_name = derive_stack_name(region_az)
    if explicit_core_resources:
        cfn_outputs = StackOutputs()
        ui.step("Skipping baseline CFN stack; explicit subnet and IAM policy config present.")
        ui.ok("Baseline CFN stack not required")
    else:
        ui.step("Ensuring baseline CFN stack ...")
        try:
            cfn_outputs = ensure_pcluster_env_stack(aws_ctx, region_az)
        except (FileNotFoundError, RuntimeError) as exc:
            logger.error("CFN stack ensure failed: %s", exc)
            ui.fail(f"CFN stack: {exc}")
            return EXIT_AWS_FAILURE
        ui.ok("CFN stack ready")

    # 3c. Subnet resolution is deterministic once baseline outputs exist.
    ec2 = aws_ctx.client("ec2")
    pub_list = list_public_subnets(ec2, region_az)
    priv_list = list_private_subnets(ec2, region_az)

    pub_t = ec.config.get("public_subnet_id")
    priv_t = ec.config.get("private_subnet_id")

    public_subnet = (
        select_subnet(
            pub_list,
            cfg_action=pub_t.action if pub_t else "",
            cfg_set_value=pub_t.set_value if pub_t else "",
            cfg_fallback=cfn_outputs.public_subnet_id,
        )
        or cfn_outputs.public_subnet_id
    )
    try:
        explicit_public_subnet = _resolve_explicit_subnet_id(
            ec2,
            cfg,
            "public_subnet_id",
            label="public subnet",
            region_az=region_az,
        )
        if explicit_public_subnet:
            public_subnet = explicit_public_subnet
    except ValueError as exc:
        logger.error("Public subnet validation failed: %s", exc)
        ui.fail(str(exc))
        return EXIT_VALIDATION_FAILURE

    private_subnet = (
        select_subnet(
            priv_list,
            cfg_action=priv_t.action if priv_t else "",
            cfg_set_value=priv_t.set_value if priv_t else "",
            cfg_fallback=cfn_outputs.private_subnet_id,
        )
        or cfn_outputs.private_subnet_id
    )
    try:
        explicit_private_subnet = _resolve_explicit_subnet_id(
            ec2,
            cfg,
            "private_subnet_id",
            label="private subnet",
            region_az=region_az,
        )
        if explicit_private_subnet:
            private_subnet = explicit_private_subnet
    except ValueError as exc:
        logger.error("Private subnet validation failed: %s", exc)
        ui.fail(str(exc))
        return EXIT_VALIDATION_FAILURE

    policy_arn = policy_arn or cfn_outputs.policy_arn

    missing_resources = _require_values(
        {
            "reference S3 URI": reference_s3_uri,
            "control-data S3 URI": control_data_s3_uri,
            "stage S3 URI": stage_s3_uri,
            "export destination S3 URI": export_destination_s3_uri,
            "public subnet": public_subnet,
            "private subnet": private_subnet,
            "IAM policy ARN": policy_arn,
        }
    )
    if missing_resources:
        logger.error("Resource resolution failed: %s", missing_resources)
        ui.fail(missing_resources)
        return EXIT_VALIDATION_FAILURE

    logger.info(
        "Resources: reference=%s control_data=%s staging=%s export=%s pub=%s priv=%s policy=%s",
        reference_s3_uri,
        control_data_s3_uri,
        stage_s3_uri,
        export_destination_s3_uri,
        public_subnet,
        private_subnet,
        policy_arn,
    )
    ui.ok("Resources resolved")
    ui.detail("Reference", reference_s3_uri)
    ui.detail("Control data", control_data_s3_uri)
    ui.detail("Runtime assets", _s3_uri_join(reference_s3_uri, "runtime_assets"))
    ui.detail("Staging", stage_s3_uri)
    ui.detail("Export destination", export_destination_s3_uri)
    ui.detail("Subnets", f"pub={public_subnet}  priv={private_subnet}")
    ui.detail("Policy", policy_arn)

    accounting_render_blocks = empty_slurm_accounting_render_blocks()
    ui.step("Publishing cluster boot config to runtime assets ...")
    try:
        cluster_boot_source_dir = resource_path("config/day_cluster")
        cluster_boot_s3_uri = cluster_boot_config_release_uri(
            base_uri=cluster_boot_s3_base_uri,
            source_dir=cluster_boot_source_dir,
        )
        uploaded_boot_config = publish_cluster_boot_config(
            aws_ctx.client("s3"),
            cluster_boot_s3_uri=cluster_boot_s3_uri,
            source_dir=cluster_boot_source_dir,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        logger.error("Cluster boot config publish failed: %s", exc)
        ui.fail(f"Cluster boot config publish: {exc}")
        return EXIT_VALIDATION_FAILURE
    except Exception as exc:
        logger.error("Cluster boot config publish failed: %s", exc)
        ui.fail(f"Cluster boot config publish: {exc}")
        return EXIT_AWS_FAILURE
    ui.ok(f"Cluster boot config published: {cluster_boot_s3_uri}")
    for uploaded_uri in uploaded_boot_config:
        ui.detail("Boot config", uploaded_uri)

    # Budget resources and the cost-center registry must exist before Slurm can
    # accept a workflow submission on the new cluster.
    ui.phase("PRE-CREATE: BUDGETS & COST CENTER")
    budgets_client = aws_ctx.client("budgets")
    s3_client = aws_ctx.client("s3")
    global_budget = ""
    cluster_budget = ""
    ui.step("Ensuring budgets and project allow-list ...")
    try:
        global_budget = ensure_global_budget(
            budgets_client,
            s3_client,
            aws_ctx.account_id,
            amount=post_create_inputs.global_budget_amount,
            cluster_name=cluster_name,
            email=post_create_inputs.budget_email,
            region=aws_ctx.region,
            region_az=region_az,
            bucket_name=reference_storage_bucket_name,
            allowed_users=post_create_inputs.allowed_budget_users,
        )
        cluster_budget = ensure_cluster_budget(
            budgets_client,
            s3_client,
            aws_ctx.account_id,
            amount=post_create_inputs.budget_amount,
            cluster_name=cluster_name,
            email=post_create_inputs.budget_email,
            region=aws_ctx.region,
            region_az=region_az,
            bucket_name=reference_storage_bucket_name,
            allowed_users=post_create_inputs.allowed_budget_users,
        )
        logger.info("Budgets: global=%s project=%s", global_budget, cluster_budget)
        ui.ok(f"Budgets: global={global_budget}, project={cluster_budget}")
    except Exception as exc:
        logger.error("Budget setup failed: %s", exc)
        ui.fail(f"Budget setup failed: {exc}")
        return EXIT_AWS_FAILURE

    if slurm_accounting == "on":
        ui.step("Ensuring active Slurm cost center ...")
        try:
            cost_center, was_created = ensure_active_cost_center(
                aws_ctx.client("dynamodb", region_name=DEFAULT_COST_CENTER_HOME_REGION),
                post_create_inputs.cost_center_name,
                monthly_cap_usd=post_create_inputs.cost_center_monthly_cap_usd,
                allowed_users=tuple(
                    value.strip()
                    for value in post_create_inputs.cost_center_allowed_users.split(",")
                    if value.strip()
                ),
                notes=f"Provisioned by dyec create for cluster {cluster_name}.",
                actor_arn=aws_ctx.caller_arn,
                table_name=DEFAULT_COST_CENTER_TABLE,
                usage_table_name=DEFAULT_COST_CENTER_USAGE_TABLE,
            )
            cost_center_state = "created" if was_created else "verified"
            ui.ok(f"Cost center {cost_center_state}: {cost_center.name}")
        except Exception as exc:
            logger.error("Cost-center setup failed: %s", exc)
            ui.fail(f"Cost-center setup failed: {exc}")
            return EXIT_AWS_FAILURE

    # -- 5. RENDER YAML (Phase 2a) -------------------------------------------
    ui.phase("RENDER CLUSTER YAML")

    ui.detail("Cluster template", template_yaml)

    substitutions: Dict[str, str] = {
        "REGSUB_REGION": aws_ctx.region,
        "REGSUB_PUB_SUBNET": public_subnet,
        "REGSUB_S3_BUCKET_INIT": cluster_boot_s3_uri,
        "REGSUB_S3_IAM_POLICY": policy_arn,
        "REGSUB_PRIVATE_SUBNET": private_subnet,
        "REGSUB_S3_REFERENCE_BUCKET": _role_bucket(s3_roles, "reference"),
        "REGSUB_S3_CONTROL_DATA_BUCKET": _role_bucket(s3_roles, "control_data"),
        "REGSUB_S3_STAGE_BUCKET": _role_bucket(s3_roles, "staging"),
        "REGSUB_S3_EXPORT_BUCKET": export_destination_spec.bucket,
        "REGSUB_S3_REFERENCE_URI": reference_s3_uri.rstrip("/"),
        "REGSUB_S3_CONTROL_DATA_URI": control_data_s3_uri.rstrip("/"),
        "REGSUB_S3_STAGE_URI": stage_s3_uri.rstrip("/"),
        "REGSUB_FSX_SIZE": fsx_size,
        "REGSUB_DETAILED_MONITORING": enable_detailed_monitoring,
        "REGSUB_CLUSTER_NAME": cluster_name,
        "REGSUB_USERNAME": f"{_os.environ.get('USER', 'unknown')}-{aws_ctx.iam_username}",
        "REGSUB_PROJECT": cluster_name,
        "REGSUB_DELETE_LOCAL_ROOT": delete_local_root,
        "REGSUB_DRAGEN_PCLUSTER_AMI": (
            dragen_inputs.backport.image_ami_id if dragen_inputs else ""
        ),
        "REGSUB_DRAGEN_LICENSE_POLICY_ARN": (
            dragen_inputs.license_policy_arn if dragen_inputs else ""
        ),
        "REGSUB_DRAGEN_LICENSE_SECRET_ARN": (
            dragen_inputs.license_secret_arn if dragen_inputs else ""
        ),
        "REGSUB_PCLUSTER_COOKBOOK_URI": (
            dragen_inputs.backport.cookbook_bundle_uri if dragen_inputs else ""
        ),
        # Every create owns one cluster-bound filesystem. Retained FSx is not
        # a supported mode, so the ParallelCluster-managed Scratch path is
        # always deleted with its stack.
        "REGSUB_SAVE_FSX": "Delete",
        # Tag values must be quoted strings, not bare YAML booleans.
        "REGSUB_ENFORCE_BUDGET": '"' + post_create_inputs.enforce_budget + '"',
        "REGSUB_COST_CENTER_REGION": DEFAULT_COST_CENTER_HOME_REGION,
        "REGSUB_COST_CENTER_TABLE": DEFAULT_COST_CENTER_TABLE,
        "REGSUB_COST_CENTER_USAGE_TABLE": DEFAULT_COST_CENTER_USAGE_TABLE,
        "REGSUB_AWS_ACCOUNT_ID": f"aws_profile-{aws_ctx.profile}",
        "REGSUB_ALLOCATION_STRATEGY": spot_instance_allocation_strategy,
        # Tag value must be non-empty (AWS min length = 1).
        "REGSUB_DAYLILY_GIT_DEETS": "none",
        "REGSUB_MAX_COUNT_8I": max_count_values["max_count_8I"],
        "REGSUB_MAX_COUNT_96I_NVME": max_count_values["max_count_96I_NVME"],
        "REGSUB_MAX_COUNT_128I": max_count_values["max_count_128I"],
        "REGSUB_MAX_COUNT_192I": max_count_values["max_count_192I"],
        "REGSUB_MAX_COUNT_384I": max_count_values["max_count_384I"],
        "REGSUB_MAX_COUNT_128I_C": max_count_values["max_count_128I_C"],
        "REGSUB_MAX_COUNT_128I_M": max_count_values["max_count_128I_M"],
        "REGSUB_MAX_COUNT_128I_R": max_count_values["max_count_128I_R"],
        "REGSUB_MAX_COUNT_128I_NVME": max_count_values["max_count_128I_NVME"],
        "REGSUB_MAX_COUNT_192I_C": max_count_values["max_count_192I_C"],
        "REGSUB_MAX_COUNT_192I_M": max_count_values["max_count_192I_M"],
        "REGSUB_MAX_COUNT_192I_R": max_count_values["max_count_192I_R"],
        "REGSUB_MAX_COUNT_192I_NVME_C": max_count_values["max_count_192I_NVME_C"],
        "REGSUB_MAX_COUNT_192I_NVME_M": max_count_values["max_count_192I_NVME_M"],
        "REGSUB_MAX_COUNT_192I_NVME_R": max_count_values["max_count_192I_NVME_R"],
        "REGSUB_MAX_COUNT_192I_HUGENVME": max_count_values["max_count_192I_HUGENVME"],
        "REGSUB_MAX_COUNT_384I_NVME_C": max_count_values["max_count_384I_NVME_C"],
        "REGSUB_MAX_COUNT_384I_NVME_M": max_count_values["max_count_384I_NVME_M"],
        "REGSUB_MAX_COUNT_384I_NVME_R": max_count_values["max_count_384I_NVME_R"],
        "REGSUB_HEADNODE_INSTANCE_TYPE": headnode_instance_type,
        "REGSUB_HEARTBEAT_EMAIL": post_create_inputs.heartbeat_email,
        "REGSUB_HEARTBEAT_SCHEDULE": post_create_inputs.heartbeat_schedule,
        "REGSUB_HEARTBEAT_SCHEDULER_ROLE_ARN": (post_create_inputs.heartbeat_scheduler_role_arn),
        # ParallelCluster CustomActions Args must be strings. The template places
        # this token in YAML lists, so quote it before text substitution.
        "REGSUB_SPOT_PRICE_WARN_THRESHOLD": json.dumps(f"{write_spot_pricing_warn_threshold:.2f}"),
        **accounting_render_blocks,
    }

    ui.step("Rendering YAML template ...")
    try:
        _yaml_init, init_template_path = write_init_artifacts(
            cluster_name,
            ts,
            template_yaml,
            substitutions,
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("YAML render failed: %s", exc)
        ui.fail(f"YAML render: {exc}")
        return EXIT_VALIDATION_FAILURE

    # 4b. Apply spot prices
    cluster_yaml_path = str(CONFIG_DIR / f"{cluster_name}_cluster_{ts}.yaml")
    spot_price_summary_path = str(CONFIG_DIR / f"{cluster_name}_spot_price_summary_{ts}.json")
    spot_price_summary_table_path = CONFIG_DIR / f"{cluster_name}-{ts}.md"
    ui.step("Applying spot prices ...")
    try:
        spot_price_summary = apply_spot_prices(
            init_template_path,
            cluster_yaml_path,
            region_az,
            ec2_client=ec2,
            global_spot_max_cost=global_spot_max_cost,
            spot_cost_limit_pct=spot_cost_limit_pct,
            write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
            summary_output_path=spot_price_summary_path,
        )
    except Exception as exc:
        logger.error("Spot price application failed: %s", exc)
        ui.fail(f"Spot pricing: {exc}")
        return EXIT_AWS_FAILURE

    try:
        attach_headnode_managed_policy(
            cluster_yaml_path,
            dayoa_deploy_key_inputs.policy_arn,
        )
        attach_headnode_managed_policy(
            cluster_yaml_path,
            dyec_deploy_key_inputs.policy_arn,
        )
    except ValueError as exc:
        logger.error("Repository deploy-key headnode policy attachment failed: %s", exc)
        ui.fail(f"Repository deploy-key headnode policy: {exc}")
        return EXIT_VALIDATION_FAILURE

    persistent2_resources = None
    fsx_resource_receipt_path = ""
    if persistent2_config is not None:
        from daylily_ec.aws.fsx_persistent2 import (
            Persistent2Spec,
            ensure_persistent2_resources,
            render_external_mount,
            validate_external_mount,
        )

        ui.phase("LIVE AWS STORAGE PROVISIONING")
        ui.step(
            "Creating or resuming this cluster's DYEC-owned P2 filesystem, "
            "client security group, and reference DRA ..."
        )

        def _report_persistent2_status(message: str) -> None:
            logger.info("PERSISTENT_2 provisioning: %s", message)
            ui.info(message)

        persistent2_spec = Persistent2Spec(
            cluster_name=cluster_name,
            region=aws_ctx.region,
            region_az=region_az,
            subnet_id=private_subnet,
            storage_capacity_gib=int(persistent2_config["fsx_fs_size"]),
            throughput_mbps_per_tib=int(persistent2_config["fsx_throughput_mbps_per_tib"]),
            reference_s3_uri=reference_s3_uri,
            username_tag=f"{_os.environ.get('USER', 'unknown')}-{aws_ctx.iam_username}",
            account_profile_tag=f"aws_profile-{aws_ctx.profile}",
            enforce_budget_tag=post_create_inputs.enforce_budget,
            cost_center_region=DEFAULT_COST_CENTER_HOME_REGION,
            cost_center_table=DEFAULT_COST_CENTER_TABLE,
            cost_center_usage_table=DEFAULT_COST_CENTER_USAGE_TABLE,
            lustre_version=persistent2_config["fsx_lustre_version"],
            metadata_mode=persistent2_config["fsx_metadata_mode"],
            encryption_mode=persistent2_config["fsx_encryption_mode"],
            owner=persistent2_config["fsx_owner"],
            lifecycle=persistent2_config["fsx_lifecycle"],
            sweep_preserve=(persistent2_config["sweep_protection_tag"] == "dyec-preserve=true"),
        )
        try:
            persistent2_resources = ensure_persistent2_resources(
                ec2,
                aws_ctx.client("fsx"),
                persistent2_spec,
                status_callback=_report_persistent2_status,
            )
            render_external_mount(cluster_yaml_path, persistent2_resources)
            validate_external_mount(cluster_yaml_path, persistent2_resources)
            fsx_resource_receipt_path = str(
                write_resource_receipt(
                    cluster_name=cluster_name,
                    run_id=ts,
                    resource_type="fsx-persistent2",
                    payload={
                        "schema": "daylily.fsx_persistent2_resource_receipt/1.0",
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                        "spec": asdict(persistent2_spec),
                        "resources": asdict(persistent2_resources),
                    },
                )
            )
        except ValueError as exc:
            logger.error("PERSISTENT_2 render/contract failed: %s", exc)
            ui.fail(f"PERSISTENT_2 contract: {exc}")
            return EXIT_VALIDATION_FAILURE
        except Exception as exc:
            logger.error("PERSISTENT_2 resource ensure failed: %s", exc)
            ui.fail(f"PERSISTENT_2 resource ensure: {exc}")
            return EXIT_AWS_FAILURE
        ui.ok(f"P2 FSx ready: {persistent2_resources.file_system_id}")
        ui.detail("P2 client security group", persistent2_resources.security_group_id)
        ui.detail(
            "P2 reference DRA",
            persistent2_resources.data_repository_association_id,
        )
        ui.detail("P2 resource receipt", fsx_resource_receipt_path)

    logger.info("Cluster YAML ready: %s", cluster_yaml_path)
    ui.ok(f"Cluster YAML ready: {cluster_yaml_path}")
    logger.info("Spot price summary ready: %s", spot_price_summary_path)
    ui.ok(f"Spot price summary ready: {spot_price_summary_path}")
    try:
        _emit_spot_price_partition_table(
            spot_price_summary,
            cluster_name=cluster_name,
            markdown_output_path=spot_price_summary_table_path,
        )
    except RuntimeError as exc:
        logger.error("Spot price table export failed: %s", exc)
        ui.fail(f"Spot price table: {exc}")
        return EXIT_VALIDATION_FAILURE
    try:
        validate_startup_dra_contract(cluster_yaml_path)
    except ValueError as exc:
        logger.error("Startup DRA contract failed: %s", exc)
        ui.fail(f"Startup DRA contract: {exc}")
        return EXIT_VALIDATION_FAILURE
    try:
        validate_cpu_only_slurm_contract(cluster_yaml_path)
    except ValueError as exc:
        logger.error("CPU-only Slurm contract failed: %s", exc)
        ui.fail(f"CPU-only Slurm contract: {exc}")
        return EXIT_VALIDATION_FAILURE
    if dragen_inputs:
        try:
            validate_dragen_cluster_contract(cluster_yaml_path, dragen_inputs)
        except ValueError as exc:
            logger.error("DRAGEN cluster contract failed: %s", exc)
            ui.fail(f"DRAGEN cluster contract: {exc}")
            return EXIT_VALIDATION_FAILURE
    if cluster_type == SENTIEON_SINGLE_CLUSTER_TYPE:
        try:
            validate_sentieon_single_cluster_contract(cluster_yaml_path)
        except ValueError as exc:
            logger.error("Sentieon single cluster contract failed: %s", exc)
            ui.fail(f"Sentieon single cluster contract: {exc}")
            return EXIT_VALIDATION_FAILURE

    # -- 6. DRY-RUN (Phase 2b) ------------------------------------------------
    ui.phase("DRY-RUN VALIDATION")
    ui.step("Running pcluster dry-run ...")
    dry_result = dry_run_create(
        cluster_name,
        cluster_yaml_path,
        aws_ctx.region,
        profile=aws_ctx.profile,
        executable=pcluster_executable,
    )
    if not dry_result.success:
        logger.error("Dry-run failed: %s", dry_result.message or dry_result.stderr)
        ui.fail(f"Dry-run failed: {dry_result.message or dry_result.stderr}")
        return EXIT_AWS_FAILURE
    ui.ok("Dry-run passed")

    if should_break_after_dry_run():
        logger.info("DAY_BREAK=1 — stopping after dry-run.")
        ui.info("DAY_BREAK=1 — stopping after dry-run.")
        return EXIT_SUCCESS

    # -- 7. CREATE (Phase 2c) -------------------------------------------------
    ui.phase("CREATE CLUSTER")
    ui.step(f"Submitting cluster creation: {cluster_name} ...")
    create_result = pcluster_create(
        cluster_name,
        cluster_yaml_path,
        aws_ctx.region,
        profile=aws_ctx.profile,
        executable=pcluster_executable,
    )
    if not create_result.success:
        logger.error(
            "Cluster creation failed (rc=%d): %s",
            create_result.returncode,
            create_result.stderr or create_result.message,
        )
        ui.fail(f"Creation failed (rc={create_result.returncode})")
        return EXIT_AWS_FAILURE
    ui.ok("Cluster creation submitted")

    # -- 8. MONITOR (Phase 2d) ------------------------------------------------
    ui.phase("MONITOR")
    ui.step("Waiting for CREATE_COMPLETE ...")
    monitor_result = wait_for_creation(
        cluster_name,
        aws_ctx.region,
        profile=aws_ctx.profile,
        executable=pcluster_executable,
    )
    if not monitor_result.success:
        logger.error(
            "Cluster did not reach CREATE_COMPLETE: status=%s error=%s",
            monitor_result.final_status,
            monitor_result.error,
        )
        ui.fail(
            f"Did not reach CREATE_COMPLETE: {monitor_result.final_status}. {monitor_result.error}"
        )
        return EXIT_AWS_FAILURE

    logger.info(
        "Cluster %s created in %.0fs.",
        cluster_name,
        monitor_result.elapsed_seconds,
    )
    ui.ok(f"Cluster created in {ui.elapsed_str(monitor_result.elapsed_seconds)}")

    # -- 8b. HEADNODE CONFIGURATION -------------------------------------------
    ui.phase("HEADNODE CONFIGURATION")
    if not monitor_result.head_node_instance_id:
        logger.error("Head node instance id unavailable — cannot continue with SSM bootstrap.")
        ui.fail("Head node instance id unavailable — cannot continue with SSM bootstrap")
        return EXIT_AWS_FAILURE

    ui.step("Waiting for headnode SSM registration ...")
    try:
        wait_for_ssm_online(
            monitor_result.head_node_instance_id,
            aws_ctx.region,
            profile=aws_ctx.profile,
        )
    except Exception as exc:
        logger.error("Head node did not become SSM-managed: %s", exc)
        ui.fail(f"Head node did not become SSM-managed: {exc}")
        return EXIT_AWS_FAILURE

    ui.step("Configuring headnode ...")
    headnode_ok = configure_headnode(
        cluster_name=cluster_name,
        head_node_instance_id=monitor_result.head_node_instance_id,
        region=aws_ctx.region,
        profile=aws_ctx.profile,
        dyec_deploy_key_secret_arn=dyec_deploy_key_inputs.secret_arn,
        dyec_deploy_key_region=dyec_deploy_key_inputs.region,
        dyec_repo_url=dyec_repo_spec.url,
        dyec_repo_ref=dyec_repo_spec.ref,
        dayoa_deploy_key_secret_arn=dayoa_deploy_key_inputs.secret_arn,
        dayoa_deploy_key_region=dayoa_deploy_key_inputs.region,
        repo_overrides=repo_overrides,
    )
    if not headnode_ok:
        logger.error("Headnode configuration failed.")
        ui.fail("Headnode configuration failed")
        return EXIT_AWS_FAILURE
    logger.info("Headnode configuration succeeded.")
    ui.ok("Headnode configured")

    # -- 9. POST-CREATE: Heartbeat --------------------------------------------
    ui.phase("POST-CREATE: HEARTBEAT")
    scheduler_role_arn, role_source = resolve_scheduler_role(
        iam_client,
        preconfigured=post_create_inputs.heartbeat_scheduler_role_arn,
        region=aws_ctx.region,
        profile=aws_ctx.profile,
    )

    hb_result = _noop_heartbeat_result()
    if scheduler_role_arn and post_create_inputs.heartbeat_email:
        ui.step("Configuring heartbeat ...")
        sns_client = aws_ctx.client("sns")
        scheduler_client = aws_ctx.client("scheduler")
        hb_result = ensure_heartbeat(
            sns_client,
            scheduler_client,
            cluster_name=cluster_name,
            region=aws_ctx.region,
            account_id=aws_ctx.account_id,
            email=post_create_inputs.heartbeat_email,
            schedule_expression=post_create_inputs.heartbeat_schedule,
            role_arn=scheduler_role_arn,
        )
        if hb_result.success:
            logger.info("Heartbeat configured (source=%s).", role_source)
            ui.ok(f"Heartbeat configured (source={role_source})")
        else:
            logger.warning("Heartbeat failed (non-fatal): %s", hb_result.error)
            ui.warn(f"Heartbeat failed (non-fatal): {hb_result.error}")
    else:
        logger.info(
            "Heartbeat skipped: role=%s email=%s",
            scheduler_role_arn or "(none)",
            post_create_inputs.heartbeat_email or "(none)",
        )
        ui.info(f"Heartbeat skipped: role={scheduler_role_arn or '(none)'}")

    # -- 11. STATE SNAPSHOT ---------------------------------------------------
    ui.phase("STATE SNAPSHOT")
    ui.step("Writing state record ...")
    # Write next-run template
    final_values: Dict[str, str] = {
        "cluster_name": cluster_name,
        "reference_s3_uri": reference_s3_uri,
        "control_data_s3_uri": control_data_s3_uri,
        "stage_s3_uri": stage_s3_uri,
        "export_destination_s3_uri": export_destination_s3_uri,
        "public_subnet_id": public_subnet,
        "private_subnet_id": private_subnet,
        "iam_policy_arn": policy_arn,
        "enforce_budget": post_create_inputs.enforce_budget,
        "budget_email": post_create_inputs.budget_email,
        "budget_amount": post_create_inputs.budget_amount,
        "global_budget_amount": post_create_inputs.global_budget_amount,
        "allowed_budget_users": post_create_inputs.allowed_budget_users,
        "cost_center_name": post_create_inputs.cost_center_name,
        "cost_center_monthly_cap_usd": post_create_inputs.cost_center_monthly_cap_usd,
        "cost_center_allowed_users": post_create_inputs.cost_center_allowed_users,
        "heartbeat_email": post_create_inputs.heartbeat_email,
        "heartbeat_schedule": post_create_inputs.heartbeat_schedule,
        "heartbeat_scheduler_role_arn": (post_create_inputs.heartbeat_scheduler_role_arn),
        "dyec_deploy_key_secret_arn": dyec_deploy_key_inputs.secret_arn,
        "dyec_deploy_key_policy_arn": dyec_deploy_key_inputs.policy_arn,
        "dayoa_deploy_key_secret_arn": dayoa_deploy_key_inputs.secret_arn,
        "dayoa_deploy_key_policy_arn": dayoa_deploy_key_inputs.policy_arn,
        "fsx_deployment_type": fsx_deployment_type,
        "fsx_fs_size": fsx_size,
        "fsx_throughput_mbps_per_tib": (
            persistent2_config["fsx_throughput_mbps_per_tib"]
            if persistent2_config is not None
            else ""
        ),
        **(persistent2_config or {}),
        **max_count_values,
    }
    next_run_path = CONFIG_DIR / f"{cluster_name}_next_run_{ts}.yaml"
    write_next_run_template(cfg, final_values, next_run_path)

    state = StateRecord(
        run_id=ts,
        cluster_name=cluster_name,
        region=aws_ctx.region,
        region_az=region_az,
        aws_profile=aws_ctx.profile,
        account_id=aws_ctx.account_id,
        bucket=reference_storage_bucket_name,
        reference_s3_uri=reference_s3_uri,
        control_data_s3_uri=control_data_s3_uri,
        stage_s3_uri=stage_s3_uri,
        export_destination_s3_uri=export_destination_s3_uri,
        keypair="",
        public_subnet_id=public_subnet,
        private_subnet_id=private_subnet,
        policy_arn=policy_arn,
        fsx_owner=(persistent2_resources.owner if persistent2_resources else ""),
        fsx_lifecycle=(persistent2_resources.lifecycle if persistent2_resources else ""),
        fsx_deployment_type=fsx_deployment_type,
        fsx_file_system_id=(persistent2_resources.file_system_id if persistent2_resources else ""),
        fsx_security_group_id=(
            persistent2_resources.security_group_id if persistent2_resources else ""
        ),
        fsx_data_repository_association_id=(
            persistent2_resources.data_repository_association_id if persistent2_resources else ""
        ),
        fsx_resource_receipt_path=fsx_resource_receipt_path,
        global_budget_name=global_budget,
        cluster_budget_name=cluster_budget,
        heartbeat_topic_arn=hb_result.topic_arn if hb_result.success else "",
        heartbeat_schedule_name=hb_result.schedule_name if hb_result.success else "",
        heartbeat_role_arn=hb_result.role_arn if hb_result.success else "",
        heartbeat_email=post_create_inputs.heartbeat_email,
        heartbeat_schedule_expression=post_create_inputs.heartbeat_schedule,
        init_template_path=init_template_path,
        cluster_yaml_path=cluster_yaml_path,
        resolved_cli_config_path=str(next_run_path),
        cfn_stack_name=stack_name,
        slurm_accounting_requested_mode=cast(Literal["on", "off"], slurm_accounting),
        spot_price_summary_path=spot_price_summary_path,
        spot_price_partitions=spot_price_summary.get("partitions", []),
    )
    state_path = write_state_record(state)
    logger.info("State written: %s", state_path)
    ui.ok(f"State written: {state_path}")

    # The successful accounting-free base state above is intentionally durable
    # before any service discovery, creation, or compute-fleet mutation.
    ui.phase("POST-CREATE: SLURM ACCOUNTING")
    from daylily_ec.state.models import SlurmAccountingOutcome, SlurmAccountingStage
    from daylily_ec.state.slurm_accounting import (
        apply_receipt_to_state,
        status_message,
        warning_message,
    )
    from daylily_ec.state.store import write_slurm_accounting_receipt
    from daylily_ec.workflow.postcreate_slurm_accounting import (
        run_postcreate_slurm_accounting,
    )

    def _configure_replacement_headnode(instance_id: str) -> bool:
        return configure_headnode(
            cluster_name=cluster_name,
            head_node_instance_id=instance_id,
            region=aws_ctx.region,
            profile=aws_ctx.profile,
            dyec_deploy_key_secret_arn=dyec_deploy_key_inputs.secret_arn,
            dyec_deploy_key_region=dyec_deploy_key_inputs.region,
            dyec_repo_url=dyec_repo_spec.url,
            dyec_repo_ref=dyec_repo_spec.ref,
            dayoa_deploy_key_secret_arn=dayoa_deploy_key_inputs.secret_arn,
            dayoa_deploy_key_region=dayoa_deploy_key_inputs.region,
            repo_overrides=repo_overrides,
        )

    accounting_result = run_postcreate_slurm_accounting(
        cluster_name=cluster_name,
        region=aws_ctx.region,
        region_az=region_az,
        profile=aws_ctx.profile,
        cluster_configuration=Path(cluster_yaml_path),
        initial_headnode_instance_id=monitor_result.head_node_instance_id,
        slurm_accounting=slurm_accounting,
        non_interactive=non_interactive,
        create_slurm_accounting_if_missing=create_slurm_accounting_if_missing,
        acknowledge_slurm_accounting_create_cost=(acknowledge_slurm_accounting_create_cost),
        pcluster_executable=pcluster_executable,
        configure_replacement_headnode=_configure_replacement_headnode,
    )
    accounting_receipt = accounting_result.to_receipt()
    accounting_receipt_path = write_slurm_accounting_receipt(
        accounting_receipt,
        cluster_name=cluster_name,
        run_id=ts,
    )
    state = apply_receipt_to_state(state, accounting_receipt, accounting_receipt_path)
    state_path = write_state_record(state)
    accounting_outcome = SlurmAccountingOutcome(accounting_result.outcome)
    if accounting_outcome in {
        SlurmAccountingOutcome.WARNING,
        SlurmAccountingOutcome.RECOVERY_REQUIRED,
    }:
        ui.warn(
            warning_message(
                accounting_receipt.error_stage or SlurmAccountingStage.SERVICE_PREPARATION,
                accounting_receipt.recovery_required,
            )
        )
    else:
        ui.ok(status_message(accounting_outcome))
    ui.detail("Slurm accounting receipt", str(accounting_receipt_path))

    accounting_failed = slurm_accounting == "on" and not accounting_result.succeeded
    if accounting_failed:
        logger.error(
            "Cluster %s base creation completed, but requested Slurm accounting failed.",
            cluster_name,
        )
    else:
        logger.info("✅ Cluster %s creation complete.", cluster_name)
    elapsed_total = monitor_result.elapsed_seconds
    final_body = (
        f"[bold]Cluster:[/]  {cluster_name}\n"
        f"[bold]Region:[/]   {aws_ctx.region} ({region_az})\n"
        f"[bold]Elapsed:[/]  {ui.elapsed_str(elapsed_total)}\n"
        f"[bold]Accounting:[/] {accounting_outcome.value}\n"
        f"{_format_idle_cost_summary(idle_cost)}"
    )
    if accounting_failed:
        ui.error_panel(
            "CLUSTER BASE CREATED · SLURM ACCOUNTING FAILED",
            final_body,
        )
    else:
        ui.success_panel("CLUSTER CREATION COMPLETE", final_body)
    typer.echo(
        _build_connection_command(
            cluster_name,
            region=aws_ctx.region,
            profile=aws_ctx.profile,
        )
    )
    typer.echo(f"Idle cluster hourly estimate: ${idle_cost.total_hourly_usd:.4f}/hour")
    if accounting_failed:
        typer.echo("Cluster base creation completed, but requested Slurm accounting did not.")
    else:
        typer.echo("...fin!")
        _maybe_say_onward()
    if accounting_failed:
        return EXIT_AWS_FAILURE
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Headnode configuration (SSM-backed)
# ---------------------------------------------------------------------------


def configure_headnode(
    cluster_name: str,
    head_node_instance_id: str,
    region: str,
    profile: str,
    *,
    dyec_repo_url: str = "",
    dyec_repo_ref: str = "",
    dyec_deploy_key_secret_arn: str = "",
    dyec_deploy_key_region: str = "",
    dayoa_deploy_key_secret_arn: str = "",
    dayoa_deploy_key_region: str = "",
    github_token_secret_arn: str = "",
    github_token_region: str = "",
    repo_overrides: Optional[Dict[str, str]] = None,
    remote_user: str = "ubuntu",
    force: bool = False,
) -> bool:
    """Configure the headnode after a successful cluster creation."""
    import yaml

    from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell, write_remote_text
    from daylily_ec.resources import resource_path
    from daylily_ec.versioning import get_release_version

    repo_name = "daylily-ephemeral-cluster"
    try:
        expected_dyec_version = get_release_version()
    except RuntimeError as exc:
        logger.error("  ✗ Cannot configure a headnode from this DYEC installation: %s", exc)
        return False
    repo_url_input = dyec_repo_url.strip()
    repo_ref = dyec_repo_ref.strip()
    if bool(repo_url_input) != bool(repo_ref):
        logger.error("  ✗ DYEC repository URL and release ref must be provided together")
        return False
    if not repo_url_input:
        try:
            repo_spec = resolve_configured_headnode_repo_spec(
                deploy_key_auth=bool(dyec_deploy_key_secret_arn)
            )
        except RuntimeError as exc:
            logger.error("  ✗ Could not resolve the running DYEC release: %s", exc)
            return False
        repo_url_input = repo_spec.url
        repo_ref = repo_spec.ref
    if repo_ref != expected_dyec_version:
        logger.error(
            "  ✗ DYEC repository ref must match the running DYEC version: expected=%s actual=%s",
            expected_dyec_version,
            repo_ref,
        )
        return False
    if dyec_deploy_key_secret_arn and not dyec_deploy_key_region:
        logger.error("  ✗ DYEC deploy-key region is required with the secret ARN")
        return False
    if dayoa_deploy_key_secret_arn and not dayoa_deploy_key_region:
        logger.error("  ✗ DayOA deploy-key region is required with the secret ARN")
        return False
    if not CLUSTER_NAME_PATTERN.fullmatch(cluster_name):
        logger.error("  ✗ Invalid cluster name for the DayOA cache namespace: %s", cluster_name)
        return False
    if bool(github_token_secret_arn) != bool(github_token_region):
        logger.error("  ✗ GitHub token secret ARN and region must be provided together")
        return False
    try:
        repo_url = _normalize_headnode_repo_url(
            repo_url_input,
            deploy_key_auth=bool(dyec_deploy_key_secret_arn),
        )
    except RuntimeError as exc:
        logger.error("  ✗ Invalid DYEC repository URL: %s", exc)
        return False
    logger.info(
        "  ▸ Headnode repository source: %s @ %s",
        repo_url,
        repo_ref,
    )

    dayoa_repo_spec: Optional[HeadnodeRepoSpec] = None
    if remote_user == "ubuntu":
        try:
            dayoa_repo_spec = resolve_configured_headnode_dayoa_repo_spec(
                deploy_key_auth=bool(dayoa_deploy_key_secret_arn),
                repo_overrides=repo_overrides,
            )
        except RuntimeError as exc:
            logger.error("  ✗ Could not resolve the pinned DayOA release: %s", exc)
            return False
        logger.info(
            "  ▸ Pinned DayOA bootstrap source: %s @ %s",
            dayoa_repo_spec.url,
            dayoa_repo_spec.ref,
        )

    active_controller_guard = (
        "active_controllers=\"$(pgrep -u \"$(id -u)\" -af "
        "'([b]in/day_run|[s]nakemake .*--profile([= ]|$))' || true)\"; "
        "if [ -n \"$active_controllers\" ]; then "
        "echo 'Refusing headnode configuration while a DayOA controller is active:' >&2; "
        "printf '%s\\n' \"$active_controllers\" >&2; "
        "exit 1; "
        "fi"
    )
    logger.info("  ▸ Verifying no DayOA controller is active ...")
    try:
        run_shell(
            head_node_instance_id,
            region,
            active_controller_guard,
            profile=profile,
            as_user=remote_user,
            require_startup_success=False,
            comment="Verify no active DayOA controller",
        )
        logger.info("  ✓ No active DayOA controller detected")
    except (SsmCommandFailedError, TimeoutError, RuntimeError) as exc:
        logger.error("  ✗ Headnode configuration safety check failed: %s", exc)
        return False

    deploy_keys: dict[str, dict[str, str]] = {}
    if dyec_deploy_key_secret_arn:
        deploy_keys["daylily-ephemeral-cluster"] = {
            "region": dyec_deploy_key_region,
            "secret_arn": dyec_deploy_key_secret_arn,
        }
        known_hosts_path = resource_path("config/github_known_hosts")
        logger.info("  ▸ Deploying pinned GitHub host keys ...")
        try:
            write_remote_text(
                head_node_instance_id,
                region,
                "~/.config/daylily/github_known_hosts",
                known_hosts_path.read_text(encoding="utf-8"),
                profile=profile,
                as_user=remote_user,
                require_startup_success=False,
            )
            logger.info("  ✓ Pinned GitHub host keys deployed")
        except Exception as exc:
            logger.error("  ✗ GitHub host-key deployment failed: %s", exc)
            return False
    if dayoa_deploy_key_secret_arn:
        deploy_keys["daylily-omics-analysis"] = {
            "region": dayoa_deploy_key_region,
            "secret_arn": dayoa_deploy_key_secret_arn,
        }
    if deploy_keys:
        deploy_key_config = {
            "config_version": 1,
            "deploy_keys": deploy_keys,
        }
        logger.info("  ▸ Deploying repository deploy-key references ...")
        try:
            write_remote_text(
                head_node_instance_id,
                region,
                "~/.config/daylily/github_deploy_keys.yaml",
                yaml.safe_dump(deploy_key_config, default_flow_style=False, sort_keys=False),
                profile=profile,
                as_user=remote_user,
                require_startup_success=False,
            )
            logger.info("  ✓ Repository deploy-key references deployed")
        except Exception as exc:
            logger.error("  ✗ Repository deploy-key reference deployment failed: %s", exc)
            return False

    if github_token_secret_arn:
        github_token_helper = resource_path("bin/headnode_utils/daylily-github-credential")
        github_token_config = {
            "config_version": 1,
            "region": github_token_region,
            "secret_arn": github_token_secret_arn,
        }
        logger.info("  ▸ Deploying managed GitHub token credential helper ...")
        try:
            write_remote_text(
                head_node_instance_id,
                region,
                "~/.config/daylily/daylily-github-credential.py",
                github_token_helper.read_text(encoding="utf-8"),
                profile=profile,
                as_user=remote_user,
                require_startup_success=False,
            )
            write_remote_text(
                head_node_instance_id,
                region,
                "~/.config/daylily/github_token.json",
                json.dumps(github_token_config, sort_keys=True) + "\n",
                profile=profile,
                as_user=remote_user,
                require_startup_success=False,
            )
            run_shell(
                head_node_instance_id,
                region,
                _build_headnode_github_token_setup_command(),
                profile=profile,
                as_user=remote_user,
                require_startup_success=False,
                comment="Configure managed GitHub token credential helper",
            )
            logger.info("  ✓ Managed GitHub token credential helper deployed")
        except Exception as exc:
            logger.error("  ✗ Managed GitHub token credential helper deployment failed: %s", exc)
            return False

    cluster_name_q = shlex.quote(cluster_name)
    steps = [
        (
            "Configure cluster-scoped DayOA cache namespace",
            (
                f"cluster_name={cluster_name_q}; "
                f"stack_id=\"$(aws cloudformation describe-stacks --region {shlex.quote(region)} "
                "--stack-name \"$cluster_name\" --query 'Stacks[0].StackId' --output text)\"; "
                "case \"$stack_id\" in "
                "arn:aws*:cloudformation:*:*:stack/\"$cluster_name\"/*) ;; "
                "*) echo \"Unable to resolve immutable CloudFormation stack generation: $stack_id\" >&2; exit 1;; "
                "esac; "
                "stack_generation=\"${stack_id##*/}\"; "
                "cluster_cache_namespace=\"$cluster_name-$stack_generation\"; "
                "case \"$cluster_cache_namespace\" in "
                "*[!a-z0-9-]*|'') echo 'Invalid DayOA cluster cache namespace' >&2; exit 1;; "
                "esac; "
                "for cache_user in ubuntu daylily ec2-user; do "
                "sudo install -d -m 1777 "
                "\"/fsx/resources/environments/conda/$cache_user/$cluster_cache_namespace\" "
                "\"/fsx/resources/environments/containers/$cache_user/$cluster_cache_namespace\"; "
                "if find \"/fsx/resources/environments/conda/$cache_user/$cluster_cache_namespace\" "
                "-mindepth 1 -maxdepth 1 -type l -print -quit | grep -q .; then "
                "echo 'Legacy linked Conda environments are forbidden in the cluster-scoped cache' >&2; "
                "exit 1; "
                "fi; "
                "done; "
                "namespace_profile=\"$(mktemp /tmp/daylily-cluster-cache-namespace.XXXXXX)\"; "
                "trap 'rm -f \"$namespace_profile\"' EXIT; "
                "printf '%s\\n' '# Managed by DYEC headnode configure.' "
                "\"export DAYOA_CLUSTER_CACHE_NAMESPACE=\\\"$cluster_cache_namespace\\\"\" "
                " > \"$namespace_profile\"; "
                "sudo install -o root -g root -m 0644 \"$namespace_profile\" "
                "/etc/profile.d/daylily-cluster-cache-namespace.sh"
            ),
            None,
        ),
        (
            "Clone repository to headnode",
            _build_headnode_repo_sync_command(
                repo_name,
                repo_url,
                repo_ref,
                deploy_key_secret_arn=dyec_deploy_key_secret_arn,
                deploy_key_region=dyec_deploy_key_region,
            ),
            None,
        ),
        (
            "Install Miniconda",
            (
                f"cd ~/projects/{repo_name} && "
                "{ [ -d ~/miniconda3 ] && echo 'miniconda already installed'; } || "
                "./bin/install_miniconda"
            ),
            None,
        ),
        (
            "Configure Ubuntu Conda non-interactive policy and Terms of Service",
            (
                "~/miniconda3/bin/conda config --set always_yes true && "
                "~/miniconda3/bin/conda config --set plugins.auto_accept_tos true && "
                "~/miniconda3/bin/conda tos accept --user "
                "--override-channels --channel https://repo.anaconda.com/pkgs/main "
                "--channel https://repo.anaconda.com/pkgs/r"
            ),
            None,
        ),
    ]
    if force:
        steps.append(
            (
                "Remove requested DAYOA and DAY-EC environments",
                _build_headnode_conda_environment_reset_command(),
                None,
            )
        )
    steps.append(
        (
            "Rebuild DAY-EC and install headnode tools",
            _build_headnode_dayec_install_command(repo_name),
            None,
        )
    )
    if dayoa_repo_spec is not None:
        steps.extend(
            (
                (
                    "Install DYEC YAML configuration",
                    _build_headnode_config_yaml_sync_command(repo_name),
                    None,
                ),
                (
                    "Clone pinned DayOA repository to headnode",
                    _build_headnode_repo_sync_command(
                        "daylily-omics-analysis",
                        dayoa_repo_spec.url,
                        dayoa_repo_spec.ref,
                        deploy_key_secret_arn=dayoa_deploy_key_secret_arn,
                        deploy_key_region=dayoa_deploy_key_region,
                    ),
                    None,
                ),
                (
                    "Bootstrap pinned DayOA in Ubuntu interactive login shell",
                    _build_headnode_dayoa_bootstrap_command(
                        cluster_name=cluster_name,
                        dayoa_ref=dayoa_repo_spec.ref,
                        dyec_version=expected_dyec_version,
                    ),
                    3600,
                ),
            )
        )

    for label, remote_cmd, timeout in steps:
        logger.info("  ▸ %s ...", label)
        try:
            run_shell(
                head_node_instance_id,
                region,
                remote_cmd,
                profile=profile,
                as_user=remote_user,
                timeout=timeout,
                require_startup_success=False,
                comment=label,
            )
            logger.info("  ✓ %s", label)
        except (SsmCommandFailedError, TimeoutError, RuntimeError) as exc:
            logger.error("  ✗ %s failed: %s", label, exc)
            return False

    expected_version_line = f"Daylily Ephemeral Cluster {expected_dyec_version}"
    verify_version_command = (
        f"expected={shlex.quote(expected_version_line)}; "
        'actual="$(dyec --version)"; '
        'if [ "$actual" != "$expected" ]; then '
        'echo "Installed DYEC version mismatch: expected=$expected actual=$actual" >&2; '
        "exit 1; "
        "fi"
    )
    logger.info("  ▸ Verifying installed DYEC version %s ...", expected_dyec_version)
    try:
        run_shell(
            head_node_instance_id,
            region,
            verify_version_command,
            profile=profile,
            as_user=remote_user,
            require_startup_success=False,
            comment="Verify installed DYEC version",
        )
        logger.info("  ✓ Installed DYEC version matches %s", expected_dyec_version)
    except (SsmCommandFailedError, TimeoutError, RuntimeError) as exc:
        logger.error("  ✗ Installed DYEC version verification failed: %s", exc)
        return False

    if repo_overrides:
        logger.info("  ▸ Deploying repository overrides ...")
        user_avail = Path.home() / ".config" / "daylily" / "daylily_pipeline_command_catalog.yaml"
        avail_repos_path = (
            user_avail
            if user_avail.exists()
            else (
                Path("config/daylily_pipeline_command_catalog.yaml")
                if Path("config/daylily_pipeline_command_catalog.yaml").exists()
                else resource_path("config/daylily_pipeline_command_catalog.yaml")
            )
        )
        if avail_repos_path.exists():
            with open(avail_repos_path, encoding="utf-8") as fh:
                repos_cfg = yaml.safe_load(fh) or {}

            configured_repositories = repos_cfg.get("repositories", {}) or {}
            unknown_repositories = sorted(set(repo_overrides) - set(configured_repositories))
            if unknown_repositories:
                logger.error(
                    "  ✗ Repository override keys are absent from the command catalog: %s",
                    ", ".join(unknown_repositories),
                )
                return False
            for repo_key, git_ref in repo_overrides.items():
                configured_repositories[repo_key]["default_ref"] = git_ref
                logger.info("    Override: %s → %s", repo_key, git_ref)

            try:
                write_remote_text(
                    head_node_instance_id,
                    region,
                    "~/.config/daylily/daylily_pipeline_command_catalog.yaml",
                    yaml.safe_dump(repos_cfg, default_flow_style=False, sort_keys=False),
                    profile=profile,
                    as_user=remote_user,
                )
                logger.info("  ✓ Repository overrides deployed")
            except Exception as exc:
                logger.error("  ✗ Repository override deployment failed: %s", exc)
                return False
        else:
            logger.error("  ✗ Available repos config not found: %s", avail_repos_path)
            return False

    logger.info("  ▸ Validating DAY-EC headnode readiness ...")
    try:
        validate_headnode_readiness(
            head_node_instance_id,
            region,
            profile=profile,
            timeout=120,
            comment="Validate DAY-EC headnode readiness",
            repo_name=repo_name,
            remote_user=remote_user,
        )
        logger.info("  ✓ DAY-EC headnode readiness validated")
    except (SsmCommandFailedError, TimeoutError, RuntimeError) as exc:
        logger.error("  ✗ DAY-EC headnode readiness validation failed: %s", exc)
        return False

    logger.info(
        "Headnode configuration complete for %s @ %s",
        cluster_name,
        head_node_instance_id,
    )
    return True


# ---------------------------------------------------------------------------
# Preflight-only workflow (CP-017)
# ---------------------------------------------------------------------------


def run_preflight_only(
    region_az: str,
    *,
    profile: Optional[str] = None,
    config_path: Optional[str] = None,
    pass_on_warn: bool = False,
    debug: bool = False,
    non_interactive: bool = False,
) -> int:
    """Run preflight validation only — no cluster creation.

    Returns ``EXIT_SUCCESS`` (0) if all checks pass (or warn + pass_on_warn),
    ``EXIT_VALIDATION_FAILURE`` (1) otherwise.
    """
    from daylily_ec.aws.context import AWSContext
    from daylily_ec.aws.iam import make_iam_preflight_step
    from daylily_ec.aws.quotas import make_quota_preflight_step
    from daylily_ec.aws.s3 import (
        ROLE_CONTROL_DATA,
        ROLE_EXPORT_DESTINATION,
        ROLE_REFERENCE,
        ROLE_STAGING,
        make_s3_bucket_preflight_step,
    )
    from daylily_ec.config.triplets import DERIVED_MAX_COUNT_KEYS, load_config

    if debug:
        logging.getLogger("daylily_ec").setLevel(logging.DEBUG)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # Load config
    effective_config = config_path or "config/daylily_ephemeral_cluster_template.yaml"
    if config_path is None and not Path(effective_config).is_file():
        from daylily_ec.resources import resource_path

        effective_config = str(resource_path(effective_config))
    cfg = load_config(effective_config)
    legacy_derived_max_counts = sorted(
        DERIVED_MAX_COUNT_KEYS.intersection(cfg.ephemeral_cluster.config)
    )
    if legacy_derived_max_counts:
        ui.warn(
            "Ignoring legacy unprompted subtype max-count keys; the five prompted "
            "family max-count values are authoritative: " + ", ".join(legacy_derived_max_counts)
        )

    try:
        fsx_deployment_type = _resolve_fsx_deployment_type(
            cfg,
            non_interactive=non_interactive,
        )
        fsx_size = _resolve_fsx_size(
            cfg,
            non_interactive=non_interactive,
        )
        _resolve_persistent2_config(
            cfg,
            deployment_type=fsx_deployment_type,
            fsx_size=fsx_size,
            non_interactive=non_interactive,
        )
    except ValueError as exc:
        logger.error("FSx selection validation failed: %s", exc)
        ui.fail(f"FSx selection: {exc}")
        return EXIT_VALIDATION_FAILURE

    try:
        cluster_name = _resolve_cluster_name(cfg, non_interactive=True)
    except ValueError as exc:
        logger.error("Cluster name validation failed: %s", exc)
        ui.fail(str(exc))
        return EXIT_VALIDATION_FAILURE

    # AWS Context
    try:
        aws_ctx = AWSContext.build(region_az, profile=profile)
    except RuntimeError as exc:
        logger.error("AWS context failed: %s", exc)
        return EXIT_AWS_FAILURE

    # Build preflight report
    report = PreflightReport(
        run_id=ts,
        cluster_name=cluster_name,
        region=aws_ctx.region,
        region_az=region_az,
        aws_profile=aws_ctx.profile,
        account_id=aws_ctx.account_id,
        caller_arn=aws_ctx.caller_arn,
    )

    max_8i = int(
        _resolve_config_value(
            cfg,
            "max_count_8I",
            "Max 8xlarge count",
            non_interactive=non_interactive,
            default_fallback="1",
        )
        or "1"
    )
    max_96i_nvme_text = _resolve_config_value(
        cfg,
        "max_count_96I_NVME",
        "Max 96-vCPU local-NVMe count",
        non_interactive=non_interactive,
    )
    if not max_96i_nvme_text:
        logger.error("Missing required max_count_96I_NVME configuration value.")
        ui.fail("max_count_96I_NVME must be configured explicitly.")
        return EXIT_VALIDATION_FAILURE
    max_96i_nvme = int(max_96i_nvme_text)
    max_128i = int(
        _resolve_config_value(
            cfg,
            "max_count_128I",
            "Max 128xlarge count",
            non_interactive=non_interactive,
            default_fallback="1",
        )
        or "1"
    )
    max_192i = int(
        _resolve_config_value(
            cfg,
            "max_count_192I",
            "Max 192xlarge count",
            non_interactive=non_interactive,
            default_fallback="1",
        )
        or "1"
    )
    max_384i = int(
        _resolve_config_value(
            cfg,
            "max_count_384I",
            "Max 384xlarge count",
            non_interactive=non_interactive,
            default_fallback="1",
        )
        or "1"
    )
    reference_s3_uri = _resolve_s3_role_config_value(
        cfg,
        "reference_s3_uri",
        "Reference S3 URI",
        role=ROLE_REFERENCE,
        aws_ctx=aws_ctx,
        non_interactive=non_interactive,
    )
    control_data_s3_uri = _resolve_s3_role_config_value(
        cfg,
        "control_data_s3_uri",
        "Control-data S3 URI",
        role=ROLE_CONTROL_DATA,
        aws_ctx=aws_ctx,
        non_interactive=non_interactive,
    )
    stage_s3_uri = _resolve_s3_role_config_value(
        cfg,
        "stage_s3_uri",
        "Stage S3 URI",
        role=ROLE_STAGING,
        aws_ctx=aws_ctx,
        non_interactive=non_interactive,
    )
    export_destination_s3_uri = _resolve_s3_role_config_value(
        cfg,
        "export_destination_s3_uri",
        "Export destination S3 URI",
        role=ROLE_EXPORT_DESTINATION,
        aws_ctx=aws_ctx,
        non_interactive=non_interactive,
    )

    preflight_steps: List[PreflightStep] = [
        make_iam_preflight_step(aws_ctx, interactive=not non_interactive),
        make_repository_catalog_preflight_step(),
        make_quota_preflight_step(
            aws_ctx,
            max_count_8i=max_8i,
            max_count_96i_nvme=max_96i_nvme,
            max_count_128i=max_128i,
            max_count_192i=max_192i,
            max_count_384i=max_384i,
            non_interactive=non_interactive,
        ),
        make_s3_bucket_preflight_step(
            aws_ctx,
            reference_s3_uri=reference_s3_uri,
            control_data_s3_uri=control_data_s3_uri,
            stage_s3_uri=stage_s3_uri,
            export_destination_s3_uri=export_destination_s3_uri,
            profile=aws_ctx.profile,
            interactive=not non_interactive,
        ),
    ]

    report = run_preflight(
        report,
        pass_on_warn=pass_on_warn,
        steps=preflight_steps,
    )

    # Always write the report
    write_preflight_report(report)

    if should_abort(report, pass_on_warn=pass_on_warn):
        logger.error("Preflight failed.")
        return exit_code_for(report)

    logger.info("Preflight passed.")
    return EXIT_SUCCESS
