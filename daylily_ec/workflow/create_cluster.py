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

import logging
import os as _os
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import typer

from daylily_ec import ui
from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport, StateRecord
from daylily_ec.state.store import write_preflight_report, write_state_record

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
PreflightStep = Callable[[PreflightReport], PreflightReport]

# Ordered list — filled by register_preflight_step or directly in wire_workflow
_PREFLIGHT_STEPS: List[PreflightStep] = []


@dataclass(frozen=True)
class HeadnodeRepoSpec:
    url: str
    ref: str


def register_preflight_step(step: PreflightStep) -> None:
    """Append a validator to the global preflight pipeline.

    Steps execute in registration order, which **must** match §10.5.
    """
    _PREFLIGHT_STEPS.append(step)


def clear_preflight_steps() -> None:
    """Reset the pipeline (used in tests)."""
    _PREFLIGHT_STEPS.clear()


def _git_stdout(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed"
        raise RuntimeError(detail)
    return proc.stdout.strip()


def _normalize_headnode_repo_url(repo_url: str) -> str:
    """Return a headnode-safe clone URL for the Daylily control repo."""
    if repo_url.startswith("git@github.com:"):
        repo_path = repo_url.removeprefix("git@github.com:")
        if "/" not in repo_path:
            raise RuntimeError(f"Unsupported GitHub SSH repository URL: {repo_url}")
        return f"https://github.com/{repo_path}"

    if repo_url.startswith("ssh://git@github.com/"):
        repo_path = repo_url.removeprefix("ssh://git@github.com/")
        if "/" not in repo_path:
            raise RuntimeError(f"Unsupported GitHub SSH repository URL: {repo_url}")
        return f"https://github.com/{repo_path}"

    if repo_url.startswith("git@") or repo_url.startswith("ssh://"):
        raise RuntimeError(
            "Headnode repository clone requires HTTPS or a supported GitHub SSH remote; "
            f"got {repo_url}"
        )

    return repo_url


def _resolve_headnode_repo_spec(default_url: str, default_ref: str) -> HeadnodeRepoSpec:
    repo_root_env = _os.environ.get("DAYLILY_EC_REPO_ROOT", "").strip()
    if not repo_root_env:
        return HeadnodeRepoSpec(url=_normalize_headnode_repo_url(default_url), ref=default_ref)

    repo_root = Path(repo_root_env).expanduser().resolve()
    if not repo_root.exists():
        raise RuntimeError(f"DAYLILY_EC_REPO_ROOT does not exist: {repo_root}")

    repo_url = _normalize_headnode_repo_url(
        _git_stdout(repo_root, "config", "--get", "remote.origin.url")
    )
    repo_ref = _git_stdout(repo_root, "symbolic-ref", "--short", "HEAD")
    published = subprocess.run(
        ["git", "-C", str(repo_root), "ls-remote", "--exit-code", "--heads", "origin", repo_ref],
        check=False,
        capture_output=True,
        text=True,
    )
    if published.returncode != 0:
        detail = (
            published.stderr.strip() or published.stdout.strip() or "branch not published on origin"
        )
        raise RuntimeError(
            f"Current checkout branch is not available on origin: {repo_ref} ({detail})"
        )

    return HeadnodeRepoSpec(url=repo_url, ref=repo_ref)


def _build_headnode_repo_sync_command(repo_name: str, repo_url: str, repo_ref: str) -> str:
    repo_name_q = shlex.quote(repo_name)
    repo_url_q = shlex.quote(repo_url)
    repo_ref_q = shlex.quote(repo_ref)
    origin_ref_q = shlex.quote(f"refs/remotes/origin/{repo_ref}")
    origin_checkout_q = shlex.quote(f"origin/{repo_ref}")
    repo_error_q = shlex.quote(f"Expected ~/projects/{repo_name} to be a git checkout")

    return (
        "mkdir -p ~/projects && cd ~/projects && "
        f"if [ -e {repo_name_q} ] && [ ! -d {repo_name_q}/.git ]; then "
        f"echo {repo_error_q} >&2; exit 1; "
        "fi && "
        f"if [ ! -d {repo_name_q}/.git ]; then git clone {repo_url_q} {repo_name_q}; fi && "
        f"cd {repo_name_q} && "
        "git fetch origin --tags --prune && "
        "git reset --hard HEAD && "
        "git clean -fdx && "
        f"if git show-ref --verify --quiet {origin_ref_q}; then "
        f"git checkout -B daylily-managed {origin_checkout_q}; "
        "else "
        f"git checkout --detach {repo_ref_q}; "
        "fi"
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
    local_catalog = Path("config/daylily_available_repositories.yaml")
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


def _is_valid_fsx_size(value: str) -> bool:
    """Return True when *value* is a valid FSx Lustre storage capacity."""
    if not value or not value.isdigit():
        return False
    size = int(value)
    if size == 1200 or size == 2400:
        return True
    return size >= 4800 and size % 2400 == 0


def _resolve_fsx_size(cfg: Any, *, non_interactive: bool) -> str:
    """Resolve the FSx size, prompting from the smallest valid options."""
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
        return default_value

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


def _require_values(values: Dict[str, str]) -> Optional[str]:
    """Return an error message if any required values are blank."""
    missing = [label for label, value in values.items() if not value]
    if not missing:
        return None
    return "Missing required values: " + ", ".join(missing)


@dataclass(frozen=True)
class _PostCreateInputs:
    budget_email: str
    budget_amount: str
    global_budget_amount: str
    allowed_budget_users: str
    heartbeat_email: str
    heartbeat_schedule: str
    heartbeat_scheduler_role_arn: str


def _resolve_post_create_inputs(
    cfg: Any,
    *,
    non_interactive: bool,
    budget_email_default: str,
    allowed_budget_users_default: str,
) -> _PostCreateInputs:
    """Resolve budget and heartbeat inputs once before the create phase."""
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
    heartbeat_email = (
        _resolve_config_value(
            cfg,
            "heartbeat_email",
            "Heartbeat email",
            non_interactive=non_interactive,
            default_fallback=budget_email,
            required=False,
            allow_empty=True,
        )
        or budget_email
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
        budget_email=budget_email,
        budget_amount=budget_amount,
        global_budget_amount=global_budget_amount,
        allowed_budget_users=allowed_budget_users,
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
    pass_on_warn: bool = False,
    debug: bool = False,
    non_interactive: bool = False,
) -> int:
    """End-to-end cluster creation: preflight → create → post-create.

    Returns one of the ``EXIT_*`` constants.
    """
    from daylily_ec.aws.budgets import ensure_cluster_budget, ensure_global_budget
    from daylily_ec.aws.cloudformation import (
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
    from daylily_ec.aws.s3 import make_s3_bucket_preflight_step
    from daylily_ec.aws.ssm import wait_for_ssm_online
    from daylily_ec.aws.spot_pricing import apply_spot_prices
    from daylily_ec.config.triplets import (
        get_effective_default,
        load_config,
        resolve_value,
        write_next_run_template,
    )
    from daylily_ec.pcluster.monitor import wait_for_creation
    from daylily_ec.pcluster.runner import (
        create_cluster as pcluster_create,
        dry_run_create,
        should_break_after_dry_run,
    )
    from daylily_ec.resources import resource_path
    from daylily_ec.render.renderer import CONFIG_DIR, write_init_artifacts

    if debug:
        logging.getLogger("daylily_ec").setLevel(logging.DEBUG)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # -- 0. Load config -------------------------------------------------------
    effective_config = config_path or "config/daylily_ephemeral_cluster_template.yaml"
    if config_path is None and not Path(effective_config).is_file():
        effective_config = str(resource_path(effective_config))
    cfg = load_config(effective_config)
    ec = cfg.ephemeral_cluster

    cluster_name = (
        _resolve_config_value(
            cfg,
            "cluster_name",
            "Cluster name",
            non_interactive=non_interactive,
            default_fallback="prod",
        )
        or "prod"
    )

    ui.phase(f"INIT · {cluster_name}")

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

    s3_triplet = ec.config.get("s3_bucket_name")
    s3_cfg_action = s3_triplet.action if s3_triplet else ""
    s3_cfg_set = s3_triplet.set_value if s3_triplet else ""
    s3_cfg_bucket_name = get_effective_default(cfg, "s3_bucket_name", "")
    if s3_triplet is not None:
        resolved_s3_value = resolve_value(s3_triplet)
        if resolved_s3_value:
            s3_cfg_bucket_name = resolved_s3_value

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
            max_count_128i=max_128i,
            max_count_192i=max_192i,
            non_interactive=non_interactive,
        ),
        # 6: S3 Bucket Selector + Validator
        make_s3_bucket_preflight_step(
            aws_ctx,
            cfg_action=s3_cfg_action,
            cfg_set_value=s3_cfg_set,
            cfg_bucket_name=s3_cfg_bucket_name,
            profile=aws_ctx.profile,
            interactive=not non_interactive,
        ),
    ]

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

    # Extract selected bucket from preflight report
    bucket_name = _extract_selected(report, "s3.bucket_select", "selected")

    # 3a. Baseline CFN stack
    ui.step("Ensuring baseline CFN stack ...")
    try:
        cfn_outputs = ensure_pcluster_env_stack(aws_ctx, region_az)
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error("CFN stack ensure failed: %s", exc)
        ui.fail(f"CFN stack: {exc}")
        return EXIT_AWS_FAILURE
    ui.ok("CFN stack ready")

    stack_name = derive_stack_name(region_az)

    # 3b. Subnet selection (from live EC2)
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
    if not public_subnet and not non_interactive and pub_list:
        public_subnet = _prompt_select(
            "public subnet",
            [subnet.subnet_id for subnet in pub_list],
        )

    private_subnet = (
        select_subnet(
            priv_list,
            cfg_action=priv_t.action if priv_t else "",
            cfg_set_value=priv_t.set_value if priv_t else "",
            cfg_fallback=cfn_outputs.private_subnet_id,
        )
        or cfn_outputs.private_subnet_id
    )
    if not private_subnet and not non_interactive and priv_list:
        private_subnet = _prompt_select(
            "private subnet",
            [subnet.subnet_id for subnet in priv_list],
        )

    # 3c. Policy ARN selection
    iam_client = aws_ctx.client("iam")
    policy_arns = list_pcluster_tags_budget_policies(iam_client)
    iam_t = ec.config.get("iam_policy_arn")
    policy_arn = (
        select_policy_arn(
            policy_arns,
            cfg_action=iam_t.action if iam_t else "",
            cfg_set_value=iam_t.set_value if iam_t else "",
            cfg_fallback=cfn_outputs.policy_arn,
        )
        or cfn_outputs.policy_arn
    )
    if not policy_arn and not non_interactive and policy_arns:
        policy_arn = _prompt_select("IAM policy ARN", policy_arns)

    missing_resources = _require_values(
        {
            "bucket": bucket_name,
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
        "Resources: bucket=%s pub=%s priv=%s policy=%s",
        bucket_name,
        public_subnet,
        private_subnet,
        policy_arn,
    )
    ui.ok("Resources resolved")
    ui.detail("Bucket", bucket_name)
    ui.detail("Subnets", f"pub={public_subnet}  priv={private_subnet}")
    ui.detail("Policy", policy_arn)

    # -- 4. PRE-CREATE: Prompt-only operational inputs -----------------------
    ui.phase("PRE-CREATE: BUDGETS & HEARTBEAT")
    post_create_inputs = _resolve_post_create_inputs(
        cfg,
        non_interactive=non_interactive,
        budget_email_default=_os.environ.get("DAY_CONTACT_EMAIL", ""),
        allowed_budget_users_default=aws_ctx.iam_username,
    )

    # -- 5. RENDER YAML (Phase 2a) -------------------------------------------
    ui.phase("RENDER CLUSTER YAML")

    bucket_url = f"s3://{bucket_name}" if bucket_name else ""
    template_yaml = (
        _resolve_config_value(
            cfg,
            "cluster_template_yaml",
            "Cluster template YAML",
            non_interactive=non_interactive,
            default_fallback="config/day_cluster/prod_cluster.yaml",
        )
        or "config/day_cluster/prod_cluster.yaml"
    )
    if not Path(template_yaml).is_file():
        template_yaml = str(resource_path(template_yaml))

    substitutions: Dict[str, str] = {
        "REGSUB_REGION": aws_ctx.region,
        "REGSUB_PUB_SUBNET": public_subnet,
        "REGSUB_S3_BUCKET_INIT": bucket_url,
        "REGSUB_S3_BUCKET_NAME": bucket_name,
        "REGSUB_S3_IAM_POLICY": policy_arn,
        "REGSUB_PRIVATE_SUBNET": private_subnet,
        "REGSUB_S3_BUCKET_REF": bucket_url,
        "REGSUB_FSX_SIZE": _resolve_fsx_size(
            cfg,
            non_interactive=non_interactive,
        ),
        "REGSUB_DETAILED_MONITORING": _resolve_config_value(
            cfg,
            "enable_detailed_monitoring",
            "Enable detailed monitoring",
            non_interactive=non_interactive,
            default_fallback="false",
        )
        or "false",
        "REGSUB_CLUSTER_NAME": cluster_name,
        "REGSUB_USERNAME": f"{_os.environ.get('USER', 'unknown')}-{aws_ctx.iam_username}",
        "REGSUB_PROJECT": cluster_name,
        "REGSUB_DELETE_LOCAL_ROOT": _resolve_config_value(
            cfg,
            "delete_local_root",
            "Delete local root",
            non_interactive=non_interactive,
            default_fallback="false",
        )
        or "false",
        # DeletionPolicy requires "Retain" or "Delete", not bool.
        "REGSUB_SAVE_FSX": (
            "Delete"
            if (
                _resolve_config_value(
                    cfg,
                    "auto_delete_fsx",
                    "Auto delete FSx",
                    non_interactive=non_interactive,
                    default_fallback="Delete",
                )
                or "false"
            ).lower()
            in ("true", "1", "yes", "delete")
            else "Retain"
        ),
        # Tag values must be quoted strings, not bare YAML booleans.
        "REGSUB_ENFORCE_BUDGET": '"'
        + (
            _resolve_config_value(
                cfg,
                "enforce_budget",
                "Enforce budget",
                non_interactive=non_interactive,
                default_fallback="true",
            )
            or "true"
        )
        + '"',
        "REGSUB_AWS_ACCOUNT_ID": f"aws_profile-{aws_ctx.profile}",
        "REGSUB_ALLOCATION_STRATEGY": _resolve_config_value(
            cfg,
            "spot_instance_allocation_strategy",
            "Spot allocation strategy",
            non_interactive=non_interactive,
            default_fallback="capacity-optimized",
        )
        or "capacity-optimized",
        # Tag value must be non-empty (AWS min length = 1).
        "REGSUB_DAYLILY_GIT_DEETS": "none",
        "REGSUB_MAX_COUNT_8I": str(max_8i),
        "REGSUB_MAX_COUNT_128I": str(max_128i),
        "REGSUB_MAX_COUNT_192I": str(max_192i),
        "REGSUB_HEADNODE_INSTANCE_TYPE": _resolve_config_value(
            cfg,
            "headnode_instance_type",
            "Headnode instance type",
            non_interactive=non_interactive,
            default_fallback="m5.xlarge",
        )
        or "m5.xlarge",
        "REGSUB_HEARTBEAT_EMAIL": post_create_inputs.heartbeat_email,
        "REGSUB_HEARTBEAT_SCHEDULE": post_create_inputs.heartbeat_schedule,
        "REGSUB_HEARTBEAT_SCHEDULER_ROLE_ARN": (post_create_inputs.heartbeat_scheduler_role_arn),
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
    ui.step("Applying spot prices ...")
    try:
        apply_spot_prices(
            init_template_path,
            cluster_yaml_path,
            region_az,
            ec2_client=ec2,
        )
    except Exception as exc:
        logger.error("Spot price application failed: %s", exc)
        ui.fail(f"Spot pricing: {exc}")
        return EXIT_AWS_FAILURE

    logger.info("Cluster YAML ready: %s", cluster_yaml_path)
    ui.ok(f"Cluster YAML ready: {cluster_yaml_path}")

    # -- 6. DRY-RUN (Phase 2b) ------------------------------------------------
    ui.phase("DRY-RUN VALIDATION")
    ui.step("Running pcluster dry-run ...")
    dry_result = dry_run_create(
        cluster_name,
        cluster_yaml_path,
        aws_ctx.region,
        profile=aws_ctx.profile,
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
    )
    if not monitor_result.success:
        logger.error(
            "Cluster did not reach CREATE_COMPLETE: status=%s error=%s",
            monitor_result.final_status,
            monitor_result.error,
        )
        ui.fail(f"Did not reach CREATE_COMPLETE: {monitor_result.final_status}")
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
        repo_overrides=None,  # TODO: wire from config if needed
    )
    if not headnode_ok:
        logger.error("Headnode configuration failed.")
        ui.fail("Headnode configuration failed")
        return EXIT_AWS_FAILURE
    logger.info("Headnode configuration succeeded.")
    ui.ok("Headnode configured")

    # -- 9. POST-CREATE: Budgets (Phase 3a) -----------------------------------
    ui.phase("POST-CREATE: BUDGETS")

    budgets_client = aws_ctx.client("budgets")
    s3_client = aws_ctx.client("s3")

    global_budget = ""
    cluster_budget = ""
    ui.step("Ensuring budgets ...")
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
            bucket_name=bucket_name,
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
            bucket_name=bucket_name,
            allowed_users=post_create_inputs.allowed_budget_users,
        )
        logger.info("Budgets: global=%s cluster=%s", global_budget, cluster_budget)
        ui.ok(f"Budgets: global={global_budget}, cluster={cluster_budget}")
    except Exception as exc:
        logger.warning("Budget setup failed (non-fatal): %s", exc)
        ui.warn(f"Budget setup failed (non-fatal): {exc}")

    # -- 10. POST-CREATE: Heartbeat (Phase 3b) --------------------------------
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
        "s3_bucket_name": bucket_name,
        "public_subnet_id": public_subnet,
        "private_subnet_id": private_subnet,
        "iam_policy_arn": policy_arn,
        "budget_email": post_create_inputs.budget_email,
        "budget_amount": post_create_inputs.budget_amount,
        "global_budget_amount": post_create_inputs.global_budget_amount,
        "allowed_budget_users": post_create_inputs.allowed_budget_users,
        "heartbeat_email": post_create_inputs.heartbeat_email,
        "heartbeat_schedule": post_create_inputs.heartbeat_schedule,
        "heartbeat_scheduler_role_arn": (post_create_inputs.heartbeat_scheduler_role_arn),
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
        bucket=bucket_name,
        keypair="",
        public_subnet_id=public_subnet,
        private_subnet_id=private_subnet,
        policy_arn=policy_arn,
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
    )
    state_path = write_state_record(state)
    logger.info("State written: %s", state_path)
    ui.ok(f"State written: {state_path}")

    logger.info("✅ Cluster %s creation complete.", cluster_name)
    elapsed_total = monitor_result.elapsed_seconds
    ui.success_panel(
        "CLUSTER CREATION COMPLETE",
        f"[bold]Cluster:[/]  {cluster_name}\n"
        f"[bold]Region:[/]   {aws_ctx.region} ({region_az})\n"
        f"[bold]Elapsed:[/]  {ui.elapsed_str(elapsed_total)}",
    )
    typer.echo(
        _build_connection_command(
            cluster_name,
            region=aws_ctx.region,
            profile=aws_ctx.profile,
        )
    )
    typer.echo("...fin!")
    _maybe_say_onward()
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
    repo_overrides: Optional[Dict[str, str]] = None,
) -> bool:
    """Configure the headnode after a successful cluster creation."""
    import yaml

    from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell, write_remote_text
    from daylily_ec.resources import resource_path

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
    repo_ref = daylily.get("git_ephemeral_cluster_repo_tag", "main")
    repo_url = daylily.get(
        "git_ephemeral_cluster_repo",
        "https://github.com/Daylily-Informatics/daylily-ephemeral-cluster.git",
    )
    repo_name = "daylily-ephemeral-cluster"
    try:
        repo_spec = _resolve_headnode_repo_spec(repo_url, repo_ref)
    except RuntimeError as exc:
        logger.error("  ✗ Could not resolve headnode repository source: %s", exc)
        return False

    repo_url = repo_spec.url
    repo_ref = repo_spec.ref
    logger.info("  ▸ Headnode repository source: %s @ %s", repo_url, repo_ref)

    steps = [
        (
            "Clone repository to headnode",
            _build_headnode_repo_sync_command(repo_name, repo_url, repo_ref),
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
            "Accept Conda Terms of Service",
            (
                "~/miniconda3/bin/conda tos accept --override-channels "
                "--channel https://repo.anaconda.com/pkgs/main && "
                "~/miniconda3/bin/conda tos accept --override-channels "
                "--channel https://repo.anaconda.com/pkgs/r"
            ),
            None,
        ),
        (
            "Install headnode tools",
            (
                f"cd ~/projects/{repo_name} && "
                f"source ~/projects/{repo_name}/activate && "
                f"./bin/install-daylily-headnode-tools"
            ),
            None,
        ),
    ]

    for label, remote_cmd, timeout in steps:
        logger.info("  ▸ %s ...", label)
        try:
            run_shell(
                head_node_instance_id,
                region,
                remote_cmd,
                profile=profile,
                timeout=timeout,
                comment=label,
            )
            logger.info("  ✓ %s", label)
        except (SsmCommandFailedError, TimeoutError, RuntimeError) as exc:
            logger.error("  ✗ %s failed: %s", label, exc)
            return False

    if repo_overrides:
        logger.info("  ▸ Deploying repository overrides ...")
        user_avail = Path.home() / ".config" / "daylily" / "daylily_available_repositories.yaml"
        avail_repos_path = (
            user_avail
            if user_avail.exists()
            else (
                Path("config/daylily_available_repositories.yaml")
                if Path("config/daylily_available_repositories.yaml").exists()
                else resource_path("config/daylily_available_repositories.yaml")
            )
        )
        if avail_repos_path.exists():
            with open(avail_repos_path, encoding="utf-8") as fh:
                repos_cfg = yaml.safe_load(fh) or {}

            for repo_key, git_ref in repo_overrides.items():
                if repo_key in repos_cfg.get("repositories", {}):
                    repos_cfg["repositories"][repo_key]["default_ref"] = git_ref
                    logger.info("    Override: %s → %s", repo_key, git_ref)

            try:
                write_remote_text(
                    head_node_instance_id,
                    region,
                    "~/.config/daylily/daylily_available_repositories.yaml",
                    yaml.safe_dump(repos_cfg, default_flow_style=False, sort_keys=False),
                    profile=profile,
                )
                logger.info("  ✓ Repository overrides deployed")
            except Exception as exc:
                logger.error("  ✗ Repository override deployment failed: %s", exc)
                return False
        else:
            logger.error("  ✗ Available repos config not found: %s", avail_repos_path)
            return False

    logger.info("  ▸ Validating fresh ubuntu login shell ...")
    try:
        run_shell(
            head_node_instance_id,
            region,
            (
                f"cd ~/projects/{repo_name} && "
                "bash -lc '"
                "set -euo pipefail; "
                'test "$(whoami)" = ubuntu; '
                'test "${DAYLILY_EC_HEADNODE_BOOTSTRAPPED:-0}" = 1; '
                'test "${CONDA_DEFAULT_ENV:-}" = DAY-EC; '
                "command -v daylily-ec >/dev/null 2>&1; "
                "command -v day-clone >/dev/null 2>&1; "
                "day-clone --list >/dev/null'"
            ),
            profile=profile,
            timeout=None,
            comment="Validate fresh ubuntu login shell",
        )
        logger.info("  ✓ Fresh ubuntu login shell validated")
    except (SsmCommandFailedError, TimeoutError, RuntimeError) as exc:
        logger.error("  ✗ Fresh ubuntu login shell validation failed: %s", exc)
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
    from daylily_ec.aws.s3 import make_s3_bucket_preflight_step
    from daylily_ec.config.triplets import get_effective_default, load_config

    if debug:
        logging.getLogger("daylily_ec").setLevel(logging.DEBUG)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # Load config
    effective_config = config_path or "config/daylily_ephemeral_cluster_template.yaml"
    if config_path is None and not Path(effective_config).is_file():
        from daylily_ec.resources import resource_path

        effective_config = str(resource_path(effective_config))
    cfg = load_config(effective_config)
    ec = cfg.ephemeral_cluster

    cluster_name = get_effective_default(cfg, "cluster_name", "prod") or "prod"

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

    max_8i = int(get_effective_default(cfg, "max_count_8I", "1") or "1")
    max_128i = int(get_effective_default(cfg, "max_count_128I", "1") or "1")
    max_192i = int(get_effective_default(cfg, "max_count_192I", "1") or "1")

    s3_triplet = ec.config.get("s3_bucket_name")
    s3_cfg_action = s3_triplet.action if s3_triplet else ""
    s3_cfg_set = s3_triplet.set_value if s3_triplet else ""

    preflight_steps: List[PreflightStep] = [
        make_iam_preflight_step(aws_ctx, interactive=not non_interactive),
        make_repository_catalog_preflight_step(),
        make_quota_preflight_step(
            aws_ctx,
            max_count_8i=max_8i,
            max_count_128i=max_128i,
            max_count_192i=max_192i,
            non_interactive=non_interactive,
        ),
        make_s3_bucket_preflight_step(
            aws_ctx,
            cfg_action=s3_cfg_action,
            cfg_set_value=s3_cfg_set,
            cfg_bucket_name=get_effective_default(cfg, "s3_bucket_name", ""),
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
