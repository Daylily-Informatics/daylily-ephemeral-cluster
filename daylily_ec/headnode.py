"""Headnode bootstrap helpers for the Daylily control plane."""

from __future__ import annotations

import getpass
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import boto3

from daylily_ec.aws.budgets import (
    CLUSTER_THRESHOLDS,
    GLOBAL_BUDGET_NAME,
    GLOBAL_THRESHOLDS,
    budget_exists,
    create_budget,
    create_notifications,
    update_tags_file,
)

DEFAULT_CONTACT_EMAIL = "john@daylilyinformatics.com"
CFNCONFIG_PATH = Path("/etc/parallelcluster/cfnconfig")
CLUSTER_CONFIG_PATH = Path("/opt/parallelcluster/shared/cluster-config.yaml")
BUDGET_TAGS_PATH = Path("/fsx/data/budget_tags/pcluster-project-budget-tags.tsv")
SQUEUE_FORMAT = "%i  %P  %C  %t  %N  %c  %T  %m  %M  %D  %j"
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@dataclass
class BudgetSummary:
    name: str
    exists: bool
    total_budget: str = ""
    used_budget: str = ""
    percent_used: float | None = None


@dataclass
class HeadnodeState:
    region: str = ""
    project: str = ""
    skip_project_check: bool = False
    reference_bucket: str = ""
    day_contact_email: str = DEFAULT_CONTACT_EMAIL
    aws_profile: str = ""
    aws_account_id: str = ""
    cluster_name_hint: str = ""
    region_az_hint: str = ""
    valid_projects: list[str] = field(default_factory=list)
    budget_summary: BudgetSummary | None = None
    warnings: list[str] = field(default_factory=list)


def _warn(message: str) -> None:
    print(message, file=sys.stderr)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_shell_assignment(text: str, key: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}\s*=\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def _extract_cluster_config_value(tag_name: str, text: str) -> str:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if re.search(rf"\bKey:\s*{re.escape(tag_name)}\b", line):
            for follow in lines[idx + 1 : idx + 4]:
                match = re.search(r"\bValue:\s*['\"]?([^'\"]+)['\"]?\s*$", follow)
                if match:
                    return match.group(1).strip()
    return ""


def _extract_reference_bucket(text: str) -> str:
    match = re.search(r"Script:\s*s3://([^/\s]+)", text)
    return match.group(1).strip() if match else ""


def _read_region(cfnconfig_path: Path = CFNCONFIG_PATH) -> str:
    if not cfnconfig_path.is_file():
        return ""
    return _parse_shell_assignment(_read_text(cfnconfig_path), "cfn_region")


def _read_cluster_project(cluster_config_path: Path = CLUSTER_CONFIG_PATH) -> str:
    if not cluster_config_path.is_file():
        return ""
    return _extract_cluster_config_value(
        "aws-parallelcluster-project",
        _read_text(cluster_config_path),
    )


def _read_reference_bucket(cluster_config_path: Path = CLUSTER_CONFIG_PATH) -> str:
    if not cluster_config_path.is_file():
        return ""
    return _extract_reference_bucket(_read_text(cluster_config_path))


def _read_budget_tags(tags_path: Path = BUDGET_TAGS_PATH) -> dict[str, list[str]]:
    if not tags_path.is_file():
        return {}
    tags: dict[str, list[str]] = {}
    for raw_line in _read_text(tags_path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "\t" not in line:
            continue
        project, users = line.split("\t", 1)
        tags[project.strip()] = [item.strip() for item in users.split(",") if item.strip()]
    return tags


def _derive_region_az_and_cluster_name(project: str) -> tuple[str, str]:
    match = re.match(r"^da-([^-]+-[^-]+-[^-]+)-(.*)$", project)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def _build_budget_summary(budget: dict[str, Any]) -> BudgetSummary:
    total_budget = str(
        ((budget.get("BudgetLimit") or {}).get("Amount") or "")
    )
    used_budget = str(
        (((budget.get("CalculatedSpend") or {}).get("ActualSpend") or {}).get("Amount") or "")
    )
    percent_used = None
    try:
        if total_budget and used_budget:
            percent_used = (float(used_budget) / float(total_budget)) * 100.0
    except (TypeError, ValueError, ZeroDivisionError):
        percent_used = None
    return BudgetSummary(
        name=str(budget.get("BudgetName") or ""),
        exists=True,
        total_budget=total_budget,
        used_budget=used_budget,
        percent_used=percent_used,
    )


def _resolve_project(
    project: Optional[str],
    *,
    skip_project_check: bool,
    valid_projects: dict[str, list[str]],
    user_name: str,
    warnings: list[str],
    cluster_project: str,
) -> str:
    resolved = project or cluster_project
    if not resolved:
        warnings.append("Unable to detect a project from the headnode cluster config.")
        return ""
    if skip_project_check or not valid_projects:
        return resolved
    if user_name in valid_projects.get(resolved, []):
        return resolved

    allowed = sorted(
        project_name
        for project_name, users in valid_projects.items()
        if user_name in users
    )
    warnings.append(
        f"Project '{resolved}' is not valid for user '{user_name}'. Proceeding without fallback."
    )
    if allowed:
        warnings.append(f"Valid projects for '{user_name}': {', '.join(allowed)}")
    return resolved


def _build_session(region: str, profile: str):
    if profile:
        return boto3.Session(profile_name=profile, region_name=region)
    return boto3.Session(region_name=region)


def collect_headnode_state(
    *,
    project: Optional[str] = None,
    profile: Optional[str] = None,
    skip_project_check: bool = False,
    cfnconfig_path: Path = CFNCONFIG_PATH,
    cluster_config_path: Path = CLUSTER_CONFIG_PATH,
    budget_tags_path: Path = BUDGET_TAGS_PATH,
) -> HeadnodeState:
    warnings: list[str] = []
    region = _read_region(cfnconfig_path)
    if not region:
        warnings.append(f"AWS ParallelCluster region not found at {cfnconfig_path}.")

    cluster_project = _read_cluster_project(cluster_config_path)
    if not cluster_project:
        warnings.append(f"Cluster project tag not found at {cluster_config_path}.")

    reference_bucket = _read_reference_bucket(cluster_config_path)
    if not reference_bucket:
        warnings.append(f"Reference bucket not found at {cluster_config_path}.")

    valid_projects = _read_budget_tags(budget_tags_path)
    if not skip_project_check and not valid_projects:
        warnings.append(f"Budget tags file not found at {budget_tags_path}.")

    user_name = getpass.getuser()
    resolved_project = _resolve_project(
        project,
        skip_project_check=skip_project_check,
        valid_projects=valid_projects,
        user_name=user_name,
        warnings=warnings,
        cluster_project=cluster_project,
    )

    resolved_profile = profile or os.environ.get("AWS_PROFILE", "")
    state = HeadnodeState(
        region=region,
        project=resolved_project,
        skip_project_check=skip_project_check,
        reference_bucket=reference_bucket,
        day_contact_email=os.environ.get("DAY_CONTACT_EMAIL", DEFAULT_CONTACT_EMAIL),
        aws_profile=resolved_profile,
        cluster_name_hint=_derive_region_az_and_cluster_name(resolved_project)[1],
        region_az_hint=_derive_region_az_and_cluster_name(resolved_project)[0],
        valid_projects=sorted(
            project_name
            for project_name, users in valid_projects.items()
            if user_name in users
        ),
        warnings=warnings,
    )

    if skip_project_check or not region:
        return state

    try:
        session = _build_session(region, resolved_profile)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        state.aws_account_id = str(identity.get("Account") or "")
        budgets_client = session.client("budgets", region_name=region)
        budgets_response = budgets_client.describe_budgets(AccountId=state.aws_account_id)
        for budget in budgets_response.get("Budgets", []):
            if budget.get("BudgetName") == state.project:
                state.budget_summary = _build_budget_summary(budget)
                break
        if state.budget_summary is None:
            state.budget_summary = BudgetSummary(name=state.project, exists=False)
    except Exception as exc:  # pragma: no cover - boto3 failures vary by environment
        state.warnings.append(f"Unable to inspect AWS budgets: {exc}")

    return state


def build_shell_code(state: HeadnodeState) -> str:
    repo_root = os.environ.get("DAYLILY_EC_REPO_ROOT", "")
    lines = []
    if repo_root:
        lines.append(f"export DAYLILY_EC_REPO_ROOT={shlex.quote(repo_root)}")

    lines.extend(
        [
            f'export DAY_CONTACT_EMAIL="${{DAY_CONTACT_EMAIL:-{DEFAULT_CONTACT_EMAIL}}}"',
            f"export DAY_PROJECT={shlex.quote(state.project)}",
            f"export DAY_AWS_REGION={shlex.quote(state.region)}",
            'export APPTAINER_HOME="/fsx/resources/environments/containers/$USER/$(hostname)/"',
            'export DAY_BIOME="AWSPC"',
            'export DAY_ROOT="${PWD}"',
            'export ORIG_PATH="${ORIG_PATH:-$PATH}"',
            'export ORIG_PS1="${ORIG_PS1:-$PS1}"',
            f"reference_bucket={shlex.quote(state.reference_bucket)}",
            'if [ -n "${DAYLILY_EC_REPO_ROOT:-}" ]; then',
            '    alias dy-b="${DAYLILY_EC_REPO_ROOT}/bin/init_dayec"',
            '    alias day-build-env="${DAYLILY_EC_REPO_ROOT}/bin/init_dayec"',
            "else",
            "    alias dy-b='bin/init_dayec'",
            "    alias day-build-env='bin/init_dayec'",
            "fi",
            "sqq() {",
            f'    local sq_cmd="squeue -o \'{SQUEUE_FORMAT}\'"',
            '    if [ "$#" -eq 0 ]; then',
            '        eval "$sq_cmd"',
            "    else",
            '        eval "$sq_cmd -j \\"$(echo "$@" | tr \' \' \',\')\\""',
            "    fi",
            "}",
            "alias sq=sqq",
        ]
    )
    return "\n".join(lines) + "\n"


def _prompt(prompt: str, default: str = "") -> str:
    import typer

    return typer.prompt(prompt, default=default, show_default=bool(default)).strip()


def _confirm(prompt: str, default: bool = False) -> bool:
    import typer

    return bool(typer.confirm(prompt, default=default))


def _prompt_email(default: str) -> str:
    while True:
        email = _prompt("Enter an email for budget alerts", default)
        if EMAIL_REGEX.match(email):
            return email
        print("Invalid email format. Please use string@string.string format.")


def _prompt_bucket_name(reference_bucket: str) -> str:
    bucket_url = _prompt("Enter S3 bucket URL", f"s3://{reference_bucket}" if reference_bucket else "")
    if bucket_url.startswith("s3://"):
        bucket_url = bucket_url[5:]
    return bucket_url.strip().strip("/")


def _create_missing_budgets(
    state: HeadnodeState,
    *,
    project_name: str,
    region_az: str,
    cluster_name: str,
    bucket_name: str,
) -> BudgetSummary:
    session = _build_session(state.region, state.aws_profile)
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    account_id = str(identity.get("Account") or "")
    budgets_client = session.client("budgets", region_name=state.region)
    s3_client = session.client("s3", region_name=state.region)

    budget_email = _prompt_email(state.day_contact_email)
    global_allowed = _prompt("Enter csv of allowed user names for global budget", "")
    global_amount = _prompt("Enter global budget amount", "200")

    if not budget_exists(budgets_client, account_id, GLOBAL_BUDGET_NAME):
        create_budget(
            budgets_client,
            account_id,
            GLOBAL_BUDGET_NAME,
            global_amount,
            GLOBAL_BUDGET_NAME,
            cluster_name,
        )
        create_notifications(
            budgets_client,
            account_id,
            GLOBAL_BUDGET_NAME,
            GLOBAL_THRESHOLDS,
            budget_email,
        )
        update_tags_file(
            s3_client,
            bucket_name,
            GLOBAL_BUDGET_NAME,
            global_allowed.replace(" ", ""),
            state.region,
        )

    allowed_users = _prompt(
        "Enter csv string of allowed user names for cluster budget",
        "",
    )
    budget_amount = _prompt("Enter cluster budget amount", "200")
    create_budget(
        budgets_client,
        account_id,
        project_name,
        budget_amount,
        project_name,
        cluster_name,
    )
    create_notifications(
        budgets_client,
        account_id,
        project_name,
        CLUSTER_THRESHOLDS,
        budget_email,
    )
    update_tags_file(
        s3_client,
        bucket_name,
        project_name,
        allowed_users.replace(" ", ""),
        state.region,
    )

    refreshed = budgets_client.describe_budgets(AccountId=account_id)
    for budget in refreshed.get("Budgets", []):
        if budget.get("BudgetName") == project_name:
            return _build_budget_summary(budget)
    return BudgetSummary(name=project_name, exists=True)


def _print_state(state: HeadnodeState) -> None:
    if state.project:
        print(f"Project: {state.project}")
    if state.region:
        print(f"Region: {state.region}")
    if state.aws_profile:
        print(f"AWS Profile: {state.aws_profile}")
    if state.reference_bucket:
        print(f"Reference bucket: {state.reference_bucket}")
    if state.valid_projects and not state.skip_project_check:
        print(f"Valid projects for {getpass.getuser()}: {', '.join(state.valid_projects)}")
    if state.budget_summary:
        if state.budget_summary.exists:
            print(
                f"Budget {state.budget_summary.name}: "
                f"total={state.budget_summary.total_budget} "
                f"used={state.budget_summary.used_budget}"
            )
            if state.budget_summary.percent_used is not None:
                print(f"Percent used: {state.budget_summary.percent_used:.2f}%")
        else:
            print(f"Budget {state.budget_summary.name} was not found.")


def run_headnode_init(
    *,
    project: Optional[str] = None,
    profile: Optional[str] = None,
    skip_project_check: bool = False,
    non_interactive: bool = False,
    emit_shell: bool = False,
    cfnconfig_path: Path = CFNCONFIG_PATH,
    cluster_config_path: Path = CLUSTER_CONFIG_PATH,
    budget_tags_path: Path = BUDGET_TAGS_PATH,
) -> int:
    state = collect_headnode_state(
        project=project,
        profile=profile,
        skip_project_check=skip_project_check,
        cfnconfig_path=cfnconfig_path,
        cluster_config_path=cluster_config_path,
        budget_tags_path=budget_tags_path,
    )

    if emit_shell and non_interactive:
        for warning in state.warnings:
            _warn(f"Warning: {warning}")
        sys.stdout.write(build_shell_code(state))
        return 0

    _print_state(state)
    for warning in state.warnings:
        _warn(f"Warning: {warning}")

    if (
        not non_interactive
        and not skip_project_check
        and state.project
        and state.budget_summary is not None
        and not state.budget_summary.exists
    ):
        if _confirm(f"Create missing budget '{state.project}' now?", default=False):
            region_az = state.region_az_hint or _prompt(
                "Enter the region+AZ for the budget", ""
            )
            cluster_name = state.cluster_name_hint or _prompt(
                "Enter the cluster name for budget tagging",
                "",
            )
            bucket_name = _prompt_bucket_name(state.reference_bucket)
            if region_az and cluster_name and bucket_name:
                try:
                    state.budget_summary = _create_missing_budgets(
                        state,
                        project_name=state.project,
                        region_az=region_az,
                        cluster_name=cluster_name,
                        bucket_name=bucket_name,
                    )
                    print(f"Created budget '{state.project}'.")
                except Exception as exc:
                    _warn(f"Warning: failed to create budget '{state.project}': {exc}")
            else:
                _warn("Warning: missing region+AZ, cluster name, or bucket name; skipping budget creation.")

    if emit_shell:
        sys.stdout.write(build_shell_code(state))
        return 0

    print('To apply shell context, run: eval "$(daylily-ec headnode init --emit-shell)"')
    return 0


__all__ = [
    "BUDGET_TAGS_PATH",
    "CFNCONFIG_PATH",
    "CLUSTER_CONFIG_PATH",
    "DEFAULT_CONTACT_EMAIL",
    "HeadnodeState",
    "BudgetSummary",
    "build_shell_code",
    "collect_headnode_state",
    "run_headnode_init",
]
