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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from daylily_ec import ui
from daylily_ec.state.models import PreflightReport, StateRecord
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


def register_preflight_step(step: PreflightStep) -> None:
    """Append a validator to the global preflight pipeline.

    Steps execute in registration order, which **must** match §10.5.
    """
    _PREFLIGHT_STEPS.append(step)


def clear_preflight_steps() -> None:
    """Reset the pipeline (used in tests)."""
    _PREFLIGHT_STEPS.clear()


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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_selected(
    report: PreflightReport, check_id: str, detail_key: str,
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
        success=False, topic_arn="", schedule_name="", role_arn="", error="skipped",
    )


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
    from daylily_ec.aws.spot_pricing import apply_spot_prices
    from daylily_ec.config.triplets import (
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
    from daylily_ec.render.renderer import CONFIG_DIR, write_init_artifacts

    if debug:
        logging.getLogger("daylily_ec").setLevel(logging.DEBUG)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # -- 0. Load config -------------------------------------------------------
    effective_config = config_path or "config/daylily_ephemeral_cluster_template.yaml"
    cfg = load_config(effective_config)
    ec = cfg.ephemeral_cluster

    def _val(key: str) -> str:
        """Resolve a config triplet value."""
        t = ec.config.get(key)
        if t is None:
            return ""
        return resolve_value(t)

    cluster_name = _val("cluster_name") or "prod"

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
    max_8i = int(_val("max_count_8I") or "1")
    max_128i = int(_val("max_count_128I") or "1")
    max_192i = int(_val("max_count_192I") or "1")

    s3_triplet = ec.config.get("s3_bucket_name")
    s3_cfg_action = s3_triplet.action if s3_triplet else ""
    s3_cfg_set = s3_triplet.set_value if s3_triplet else ""

    preflight_steps: List[PreflightStep] = [
        # 1-2: ToolchainValidator + AWS Identity — implicit via AWSContext.build
        # 3: IAM Permission Validator
        make_iam_preflight_step(aws_ctx, interactive=not non_interactive),
        # 4: ConfigValidator — config load already succeeded above
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
            cfg_bucket_name=_val("s3_bucket_name"),
            profile=aws_ctx.profile,
        ),
    ]

    report = run_preflight(
        report, pass_on_warn=pass_on_warn, steps=preflight_steps,
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

    public_subnet = select_subnet(
        pub_list,
        cfg_action=pub_t.action if pub_t else "",
        cfg_set_value=pub_t.set_value if pub_t else "",
        cfg_fallback=cfn_outputs.public_subnet_id,
    ) or cfn_outputs.public_subnet_id

    private_subnet = select_subnet(
        priv_list,
        cfg_action=priv_t.action if priv_t else "",
        cfg_set_value=priv_t.set_value if priv_t else "",
        cfg_fallback=cfn_outputs.private_subnet_id,
    ) or cfn_outputs.private_subnet_id

    # 3c. Policy ARN selection
    iam_client = aws_ctx.client("iam")
    policy_arns = list_pcluster_tags_budget_policies(iam_client)
    iam_t = ec.config.get("iam_policy_arn")
    policy_arn = select_policy_arn(
        policy_arns,
        cfg_action=iam_t.action if iam_t else "",
        cfg_set_value=iam_t.set_value if iam_t else "",
        cfg_fallback=cfn_outputs.policy_arn,
    ) or cfn_outputs.policy_arn

    keypair = _val("ssh_key_name")
    logger.info(
        "Resources: bucket=%s pub=%s priv=%s policy=%s key=%s",
        bucket_name, public_subnet, private_subnet, policy_arn, keypair,
    )
    ui.ok("Resources resolved")
    ui.detail("Bucket", bucket_name)
    ui.detail("Subnets", f"pub={public_subnet}  priv={private_subnet}")
    ui.detail("Policy", policy_arn)
    ui.detail("Keypair", keypair)

    # -- 4. RENDER YAML (Phase 2a) -------------------------------------------
    ui.phase("RENDER CLUSTER YAML")

    bucket_url = f"s3://{bucket_name}" if bucket_name else ""
    template_yaml = _val("cluster_template_yaml") or "config/day_cluster/prod_cluster.yaml"

    substitutions: Dict[str, str] = {
        "REGSUB_REGION": aws_ctx.region,
        "REGSUB_PUB_SUBNET": public_subnet,
        "REGSUB_KEYNAME": keypair,
        "REGSUB_S3_BUCKET_INIT": bucket_url,
        "REGSUB_S3_BUCKET_NAME": bucket_name,
        "REGSUB_S3_IAM_POLICY": policy_arn,
        "REGSUB_PRIVATE_SUBNET": private_subnet,
        "REGSUB_S3_BUCKET_REF": bucket_url,
        "REGSUB_XMR_MINE": "false",
        # Empty args must render as '""' (YAML empty string) not null.
        "REGSUB_XMR_POOL_URL": '""',
        "REGSUB_XMR_WALLET": '""',
        "REGSUB_FSX_SIZE": _val("fsx_fs_size") or "1200",
        "REGSUB_DETAILED_MONITORING": _val("enable_detailed_monitoring") or "false",
        "REGSUB_CLUSTER_NAME": cluster_name,
        "REGSUB_USERNAME": f"{_os.environ.get('USER', 'unknown')}-{aws_ctx.iam_username}",
        "REGSUB_PROJECT": cluster_name,
        "REGSUB_DELETE_LOCAL_ROOT": _val("delete_local_root") or "false",
        # DeletionPolicy requires "Retain" or "Delete", not bool.
        "REGSUB_SAVE_FSX": (
            "Delete"
            if (_val("auto_delete_fsx") or "false").lower() in ("true", "1", "yes")
            else "Retain"
        ),
        # Tag values must be quoted strings, not bare YAML booleans.
        "REGSUB_ENFORCE_BUDGET": '"' + (_val("enforce_budget") or "true") + '"',
        "REGSUB_AWS_ACCOUNT_ID": f"aws_profile-{aws_ctx.profile}",
        "REGSUB_ALLOCATION_STRATEGY": _val("spot_instance_allocation_strategy") or "capacity-optimized",
        # Tag value must be non-empty (AWS min length = 1).
        "REGSUB_DAYLILY_GIT_DEETS": "none",
        "REGSUB_MAX_COUNT_8I": str(max_8i),
        "REGSUB_MAX_COUNT_128I": str(max_128i),
        "REGSUB_MAX_COUNT_192I": str(max_192i),
        "REGSUB_HEADNODE_INSTANCE_TYPE": _val("headnode_instance_type") or "m5.xlarge",
        "REGSUB_HEARTBEAT_EMAIL": _val("heartbeat_email") or _os.environ.get("DAY_CONTACT_EMAIL", ""),
        "REGSUB_HEARTBEAT_SCHEDULE": _val("heartbeat_schedule") or "rate(6 hours)",
        "REGSUB_HEARTBEAT_SCHEDULER_ROLE_ARN": _val("heartbeat_scheduler_role_arn") or "",
    }

    ui.step("Rendering YAML template ...")
    try:
        _yaml_init, init_template_path = write_init_artifacts(
            cluster_name, ts, template_yaml, substitutions,
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("YAML render failed: %s", exc)
        ui.fail(f"YAML render: {exc}")
        return EXIT_VALIDATION_FAILURE

    # 4b. Apply spot prices
    cluster_yaml_path = str(
        CONFIG_DIR / f"{cluster_name}_cluster_{ts}.yaml"
    )
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

    # -- 5. DRY-RUN (Phase 2b) ------------------------------------------------
    ui.phase("DRY-RUN VALIDATION")
    ui.step("Running pcluster dry-run ...")
    dry_result = dry_run_create(
        cluster_name, cluster_yaml_path, aws_ctx.region,
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

    # -- 6. CREATE (Phase 2c) -------------------------------------------------
    ui.phase("CREATE CLUSTER")
    ui.step(f"Submitting cluster creation: {cluster_name} ...")
    create_result = pcluster_create(
        cluster_name, cluster_yaml_path, aws_ctx.region,
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

    # -- 7. MONITOR (Phase 2d) ------------------------------------------------
    ui.phase("MONITOR")
    ui.step("Waiting for CREATE_COMPLETE ...")
    monitor_result = wait_for_creation(
        cluster_name, aws_ctx.region, profile=aws_ctx.profile,
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

    # -- SSH connection banner ------------------------------------------------
    _print_ssh_banner(
        cluster_name,
        head_node_ip=monitor_result.head_node_ip,
        keypair=keypair,
        region_az=region_az,
    )

    # -- 7b. HEADNODE CONFIGURATION -------------------------------------------
    ui.phase("HEADNODE CONFIGURATION")
    if monitor_result.head_node_ip:
        ui.step("Configuring headnode ...")
        headnode_ok = configure_headnode(
            cluster_name=cluster_name,
            head_node_ip=monitor_result.head_node_ip,
            keypair=keypair,
            region=aws_ctx.region,
            profile=aws_ctx.profile,
            repo_overrides=None,  # TODO: wire from config if needed
        )
        if headnode_ok:
            logger.info("Headnode configuration succeeded.")
            ui.ok("Headnode configured")
        else:
            logger.warning("Headnode configuration failed (non-fatal).")
            ui.warn("Headnode configuration failed (non-fatal)")
    else:
        logger.warning("Head node IP unavailable — skipping headnode configuration.")
        ui.warn("Head node IP unavailable — skipping headnode config")

    # -- 8. POST-CREATE: Budgets (Phase 3a) -----------------------------------
    ui.phase("POST-CREATE: BUDGETS")
    budget_email = _val("budget_email") or _os.environ.get("DAY_CONTACT_EMAIL", "")
    budget_amount = _val("budget_amount") or "200"
    global_budget_amount = _val("global_budget_amount") or "1000"
    allowed_users = _val("allowed_budget_users") or aws_ctx.iam_username

    budgets_client = aws_ctx.client("budgets")
    s3_client = aws_ctx.client("s3")

    global_budget = ""
    cluster_budget = ""
    ui.step("Ensuring budgets ...")
    try:
        global_budget = ensure_global_budget(
            budgets_client, s3_client, aws_ctx.account_id,
            amount=global_budget_amount,
            cluster_name=cluster_name,
            email=budget_email,
            region=aws_ctx.region,
            region_az=region_az,
            bucket_name=bucket_name,
            allowed_users=allowed_users,
        )
        cluster_budget = ensure_cluster_budget(
            budgets_client, s3_client, aws_ctx.account_id,
            amount=budget_amount,
            cluster_name=cluster_name,
            email=budget_email,
            region=aws_ctx.region,
            region_az=region_az,
            bucket_name=bucket_name,
            allowed_users=allowed_users,
        )
        logger.info("Budgets: global=%s cluster=%s", global_budget, cluster_budget)
        ui.ok(f"Budgets: global={global_budget}, cluster={cluster_budget}")
    except Exception as exc:
        logger.warning("Budget setup failed (non-fatal): %s", exc)
        ui.warn(f"Budget setup failed (non-fatal): {exc}")

    # -- 9. POST-CREATE: Heartbeat (Phase 3b) ---------------------------------
    ui.phase("POST-CREATE: HEARTBEAT")
    heartbeat_email = _val("heartbeat_email") or budget_email
    schedule_expr = _val("heartbeat_schedule") or "rate(6 hours)"

    scheduler_role_arn, role_source = resolve_scheduler_role(
        iam_client,
        preconfigured=_val("heartbeat_scheduler_role_arn"),
        region=aws_ctx.region,
        profile=aws_ctx.profile,
    )

    hb_result = _noop_heartbeat_result()
    if scheduler_role_arn and heartbeat_email:
        ui.step("Configuring heartbeat ...")
        sns_client = aws_ctx.client("sns")
        scheduler_client = aws_ctx.client("scheduler")
        hb_result = ensure_heartbeat(
            sns_client, scheduler_client,
            cluster_name=cluster_name,
            region=aws_ctx.region,
            account_id=aws_ctx.account_id,
            email=heartbeat_email,
            schedule_expression=schedule_expr,
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
            scheduler_role_arn or "(none)", heartbeat_email or "(none)",
        )
        ui.info(f"Heartbeat skipped: role={scheduler_role_arn or '(none)'}")

    # -- 10. STATE SNAPSHOT ---------------------------------------------------
    ui.phase("STATE SNAPSHOT")
    ui.step("Writing state record ...")
    # Write next-run template
    final_values: Dict[str, str] = {
        "cluster_name": cluster_name,
        "s3_bucket_name": bucket_name,
        "ssh_key_name": keypair,
        "public_subnet_id": public_subnet,
        "private_subnet_id": private_subnet,
        "iam_policy_arn": policy_arn,
        "budget_email": budget_email,
        "budget_amount": budget_amount,
        "global_budget_amount": global_budget_amount,
        "allowed_budget_users": allowed_users,
        "heartbeat_email": heartbeat_email,
        "heartbeat_schedule": schedule_expr,
        "heartbeat_scheduler_role_arn": scheduler_role_arn or "",
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
        keypair=keypair,
        public_subnet_id=public_subnet,
        private_subnet_id=private_subnet,
        policy_arn=policy_arn,
        global_budget_name=global_budget,
        cluster_budget_name=cluster_budget,
        heartbeat_topic_arn=hb_result.topic_arn if hb_result.success else "",
        heartbeat_schedule_name=hb_result.schedule_name if hb_result.success else "",
        heartbeat_role_arn=hb_result.role_arn if hb_result.success else "",
        heartbeat_email=heartbeat_email,
        heartbeat_schedule_expression=schedule_expr,
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
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# SSH banner helper
# ---------------------------------------------------------------------------


def _print_ssh_banner(
    cluster_name: str,
    *,
    head_node_ip: str | None,
    keypair: str,
    region_az: str,
) -> None:
    """Print a prominent SSH connection message after successful creation."""
    if head_node_ip:
        body = (
            f"[bold]Cluster:[/]   {cluster_name}\n"
            f"[bold]Region/AZ:[/] {region_az}\n"
            f"[bold]Head Node:[/] {head_node_ip}\n"
            f"[bold]SSH Key:[/]   {keypair}\n\n"
            f"[bold cyan]Connect:[/]\n"
            f"  [dim]ssh -i ~/.ssh/{keypair}.pem ubuntu@{head_node_ip}[/]"
        )
        ui.success_panel("SSH CONNECTION", body)
    else:
        body = (
            f"[bold]Cluster:[/]   {cluster_name}\n"
            f"[bold]Region/AZ:[/] {region_az}\n\n"
            f"[yellow]Head node IP not yet available.[/]\n"
            f"Run: [dim]pcluster describe-cluster -n {cluster_name}"
            f" --region {region_az[:-1]}[/]"
        )
        ui.success_panel("SSH CONNECTION", body)


# ---------------------------------------------------------------------------
# Headnode configuration (wraps bin/daylily-cfg-headnode logic)
# ---------------------------------------------------------------------------

# SSH options reused across all remote commands
_SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null"]


def _ssh_cmd(
    pem_path: str,
    ip: str,
    remote_cmd: str,
    *,
    timeout: int = 300,
) -> subprocess.CompletedProcess:
    """Run a single command on the headnode via SSH.

    Returns the CompletedProcess; caller decides what to do with failures.
    """
    cmd = [
        "ssh", "-i", pem_path, *_SSH_OPTS,
        f"ubuntu@{ip}",
        remote_cmd,
    ]
    logger.debug("SSH → %s", remote_cmd)
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _scp_to(
    pem_path: str,
    ip: str,
    local_path: str,
    remote_path: str,
    *,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    """Copy a local file to the headnode via SCP."""
    cmd = [
        "scp", "-i", pem_path, *_SSH_OPTS,
        local_path,
        f"ubuntu@{ip}:{remote_path}",
    ]
    logger.debug("SCP %s → %s:%s", local_path, ip, remote_path)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)  # noqa: S603


def configure_headnode(
    cluster_name: str,
    head_node_ip: str,
    keypair: str,
    region: str,
    profile: str,
    *,
    repo_overrides: Optional[Dict[str, str]] = None,
) -> bool:
    """Configure headnode after successful cluster creation.

    Performs (mirrors ``bin/daylily-cfg-headnode``):

    1. SSH key generation on headnode
    2. Repository cloning to ``~/projects/daylily-ephemeral-cluster``
    3. Miniconda installation
    4. DAY-EC environment initialization
    5. Headnode tooling installation (day-clone, config files)
    6. Optional repository override deployment

    Args:
        cluster_name: Name of the cluster (for logging).
        head_node_ip: Public IP of the head node.
        keypair: SSH key-pair name (looked up in ``~/.ssh/{keypair}.pem``).
        region: AWS region (e.g. ``us-west-2``).
        profile: AWS profile name.
        repo_overrides: Optional mapping of repo-key → git-ref overrides.

    Returns:
        *True* on success, *False* on failure (non-fatal to the workflow).
    """
    import tempfile

    import yaml

    pem_path = str(Path.home() / ".ssh" / f"{keypair}.pem")
    if not Path(pem_path).exists():
        logger.error("PEM file not found: %s", pem_path)
        return False

    # Read repo tag + URL from global config
    cfg_path = Path("config/daylily_cli_global.yaml")
    if not cfg_path.exists():
        logger.error("Global config not found: %s", cfg_path)
        return False

    with open(cfg_path) as fh:
        cli_cfg = yaml.safe_load(fh)

    daylily = cli_cfg.get("daylily", {})
    repo_tag = daylily.get("git_ephemeral_cluster_repo_tag", "main")
    repo_url = daylily.get(
        "git_ephemeral_cluster_repo",
        "https://github.com/Daylily-Informatics/daylily-ephemeral-cluster.git",
    )
    repo_name = "daylily-ephemeral-cluster"

    steps = [
        (
            "Generate SSH key on headnode",
            "ssh-keygen -q -t rsa -f ~/.ssh/id_rsa -N '' <<< $'\\ny' 2>/dev/null || true",
            60,
        ),
        (
            "Clone repository to headnode",
            (
                f"mkdir -p ~/projects && cd ~/projects && "
                f"{{ [ -d {repo_name} ] && echo 'repo already cloned'; }} || "
                f"git clone -b {shlex.quote(repo_tag)} {shlex.quote(repo_url)} {repo_name}"
            ),
            120,
        ),
        (
            "Install Miniconda",
            (
                f"cd ~/projects/{repo_name} && "
                "{ [ -d ~/miniconda3 ] && echo 'miniconda already installed'; } || "
                "./bin/install_miniconda"
            ),
            180,
        ),
        (
            "Initialize DAY-EC environment",
            (
                f"source ~/miniconda3/etc/profile.d/conda.sh && "
                f"cd ~/projects/{repo_name} && ./bin/init_dayec"
            ),
            300,
        ),
        (
            "Install headnode tools",
            (
                f"source ~/miniconda3/etc/profile.d/conda.sh && conda activate DAY-EC && "
                f"cd ~/projects/{repo_name} && ./bin/install-daylily-headnode-tools"
            ),
            120,
        ),
    ]

    for label, remote_cmd, timeout in steps:
        logger.info("  ▸ %s ...", label)
        try:
            result = _ssh_cmd(pem_path, head_node_ip, remote_cmd, timeout=timeout)
            if result.returncode != 0:
                logger.warning(
                    "  ⚠ %s returned rc=%d: %s",
                    label, result.returncode, result.stderr.strip()[:200],
                )
                # Non-fatal for individual steps; continue trying remaining steps
            else:
                logger.info("  ✓ %s", label)
        except subprocess.TimeoutExpired:
            logger.warning("  ⚠ %s timed out after %ds", label, timeout)
        except Exception as exc:
            logger.warning("  ⚠ %s failed: %s", label, exc)

    # Optional: deploy repository overrides
    if repo_overrides:
        logger.info("  ▸ Deploying repository overrides ...")
        avail_repos_path = Path("config/daylily_available_repositories.yaml")
        if avail_repos_path.exists():
            with open(avail_repos_path) as fh:
                repos_cfg = yaml.safe_load(fh)

            for repo_key, git_ref in repo_overrides.items():
                if repo_key in repos_cfg.get("repositories", {}):
                    repos_cfg["repositories"][repo_key]["default_ref"] = git_ref
                    logger.info("    Override: %s → %s", repo_key, git_ref)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False,
            ) as tmp:
                yaml.safe_dump(repos_cfg, tmp, default_flow_style=False)
                tmp_path = tmp.name

            try:
                scp_result = _scp_to(
                    pem_path, head_node_ip, tmp_path,
                    "~/.config/daylily/daylily_available_repositories.yaml",
                )
                if scp_result.returncode == 0:
                    logger.info("  ✓ Repository overrides deployed")
                else:
                    logger.warning(
                        "  ⚠ SCP overrides failed: %s", scp_result.stderr.strip()[:200],
                    )
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        else:
            logger.warning("  ⚠ Available repos config not found: %s", avail_repos_path)

    # Verify day-clone works
    logger.info("  ▸ Verifying day-clone ...")
    try:
        verify = _ssh_cmd(
            pem_path, head_node_ip,
            "source ~/miniconda3/etc/profile.d/conda.sh && conda activate DAY-EC && day-clone --list",
            timeout=30,
        )
        if verify.returncode == 0 and "repositories" in verify.stdout.lower():
            logger.info("  ✓ day-clone verified")
        else:
            logger.warning("  ⚠ day-clone verification inconclusive (rc=%d)", verify.returncode)
    except Exception as exc:
        logger.warning("  ⚠ day-clone verification failed: %s", exc)

    logger.info("Headnode configuration complete for %s @ %s", cluster_name, head_node_ip)
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
    from daylily_ec.config.triplets import load_config, resolve_value

    if debug:
        logging.getLogger("daylily_ec").setLevel(logging.DEBUG)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # Load config
    effective_config = config_path or "config/daylily_ephemeral_cluster_template.yaml"
    cfg = load_config(effective_config)
    ec = cfg.ephemeral_cluster

    def _val(key: str) -> str:
        t = ec.config.get(key)
        if t is None:
            return ""
        return resolve_value(t)

    cluster_name = _val("cluster_name") or "prod"

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

    max_8i = int(_val("max_count_8I") or "1")
    max_128i = int(_val("max_count_128I") or "1")
    max_192i = int(_val("max_count_192I") or "1")

    s3_triplet = ec.config.get("s3_bucket_name")
    s3_cfg_action = s3_triplet.action if s3_triplet else ""
    s3_cfg_set = s3_triplet.set_value if s3_triplet else ""

    preflight_steps: List[PreflightStep] = [
        make_iam_preflight_step(aws_ctx, interactive=not non_interactive),
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
            cfg_bucket_name=_val("s3_bucket_name"),
            profile=aws_ctx.profile,
        ),
    ]

    report = run_preflight(
        report, pass_on_warn=pass_on_warn, steps=preflight_steps,
    )

    # Always write the report
    write_preflight_report(report)

    if should_abort(report, pass_on_warn=pass_on_warn):
        logger.error("Preflight failed.")
        return exit_code_for(report)

    logger.info("Preflight passed.")
    return EXIT_SUCCESS