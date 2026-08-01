from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SBATCH_SOURCE = REPO_ROOT / "config" / "day_cluster" / "sbatch"
PACKAGED_SBATCH = (
    REPO_ROOT / "daylily_ec" / "resources" / "payload" / "config" / "day_cluster" / "sbatch"
)


def test_sbatch_wrappers_are_identical_and_have_no_monthly_usage_admission_lookup() -> None:
    source = SBATCH_SOURCE.read_bytes()
    assert source == PACKAGED_SBATCH.read_bytes()
    text = source.decode("utf-8")
    assert "active_until" in text
    assert "cost_center_usage_table" not in text
    assert "current_month" not in text


def _write(path: Path, text: str, *, mode: int = 0o644) -> Path:
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)
    return path


def _prepared_wrapper(
    tmp_path: Path,
    *,
    enforce_budget: str = "true",
    budget_mode: str = "ok",
    registry_mode: str = "ok",
    usage_mode: str = "ok",
    registry_active_until: str = "",
    include_usage_table_tag: bool = True,
) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    fake_slurm = _write(
        bin_dir / "real-slurm",
        "#!/bin/bash\nprintf 'REAL_SLURM'\nprintf ' [%s]' \"$@\"\nprintf '\\n'\n",
        mode=0o755,
    )
    registry_active_until_attribute = (
        f',"active_until":{{"S":"{registry_active_until}"}}' if registry_active_until else ""
    )
    _write(
        bin_dir / "aws",
        f"""#!/bin/bash
set -euo pipefail
if [ "$1" = "sts" ] && [ "$2" = "get-caller-identity" ]; then
  printf '123456789012\\n'
  exit 0
fi
if [ "$1" = "budgets" ] && [ "$2" = "describe-budget" ]; then
  budget_name=""
  while [ "$#" -gt 0 ]; do
    if [ "$1" = "--budget-name" ]; then
      shift
      budget_name="$1"
    fi
    shift || true
  done
  if [ "$budget_name" != "cluster-a" ]; then
    echo "unexpected budget name $budget_name" >&2
    exit 2
  fi
  case "{budget_mode}" in
    ok) printf '200\\t50\\tUSD\\n' ;;
    exceeded) printf '200\\t200\\tUSD\\n' ;;
    missing) echo 'NotFoundException' >&2; exit 254 ;;
    malformed) printf 'None\\tNone\\tUSD\\n' ;;
    *) echo 'bad test aws mode' >&2; exit 2 ;;
  esac
  exit 0
fi
if [ "$1" = "dynamodb" ] && [ "$2" = "get-item" ]; then
  table=""
  while [ "$#" -gt 0 ]; do
    if [ "$1" = "--table-name" ]; then
      shift
      table="$1"
    fi
    shift || true
  done
  if [ "$table" = "dayec-cost-centers" ]; then
    case "{registry_mode}" in
      ok) printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"status":{{"S":"active"}},"monthly_cap_usd":{{"N":"200"}},"allowed_users":{{"SS":["ubuntu"]}}%s}}}}\\n' '{registry_active_until_attribute}' ;;
      unknown) printf '{{}}\\n' ;;
      unauthorized) printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"status":{{"S":"active"}},"monthly_cap_usd":{{"N":"200"}},"allowed_users":{{"SS":["alice"]}}}}}}\\n' ;;
      disabled) printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"status":{{"S":"disabled"}},"monthly_cap_usd":{{"N":"200"}},"allowed_users":{{"SS":["ubuntu"]}}}}}}\\n' ;;
      malformed) printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"status":{{"S":"active"}},"monthly_cap_usd":{{"N":"NaN"}},"allowed_users":{{"SS":["ubuntu"]}}}}}}\\n' ;;
      empty_json) : ;;
      invalid_json) printf '{{"Item":' ;;
      *) echo 'bad registry mode' >&2; exit 2 ;;
    esac
    exit 0
  fi
  if [ "$table" = "dayec-cost-center-usage" ]; then
    latest=$(date -u +%Y-%m-%dT%H:00:00Z)
    stale="2026-01-01T00:00:00Z"
    case "{usage_mode}" in
      ok) printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"month":{{"S":"2026-07"}},"monthly_spend_usd":{{"N":"50"}},"latest_processed_hour":{{"S":"%s"}}}}}}\\n' "$latest" ;;
      exceeded) printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"month":{{"S":"2026-07"}},"monthly_spend_usd":{{"N":"200"}},"latest_processed_hour":{{"S":"%s"}}}}}}\\n' "$latest" ;;
      stale) printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"month":{{"S":"2026-07"}},"monthly_spend_usd":{{"N":"50"}},"latest_processed_hour":{{"S":"%s"}}}}}}\\n' "$stale" ;;
      within_override) latest="$(python3 -c 'from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(days=7)).replace(minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z"))')"; printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"month":{{"S":"2026-07"}},"monthly_spend_usd":{{"N":"50"}},"latest_processed_hour":{{"S":"%s"}}}}}}\\n' "$latest" ;;
      missing) printf '{{}}\\n' ;;
      empty_json) : ;;
      invalid_json) printf '{{"Item":' ;;
      *) echo 'bad usage mode' >&2; exit 2 ;;
    esac
    exit 0
  fi
fi
echo "unexpected aws call: $*" >&2
exit 2
""",
        mode=0o755,
    )

    usage_table_tag_lines = (
        [
            "- Key: aws-parallelcluster-cost-center-usage-table",
            '  Value: "dayec-cost-center-usage"',
        ]
        if include_usage_table_tag
        else []
    )
    cluster_config = _write(
        tmp_path / "cluster-config.yaml",
        "\n".join(
            [
                "Tags:",
                "- Key: aws-parallelcluster-clustername",
                '  Value: "cluster-a"',
                "- Key: aws-parallelcluster-enforce-budget",
                f'  Value: "{enforce_budget}"',
                "- Key: aws-parallelcluster-cost-center-region",
                '  Value: "us-west-2"',
                "- Key: aws-parallelcluster-cost-center-table",
                '  Value: "dayec-cost-centers"',
                *usage_table_tag_lines,
                "",
            ]
        ),
    )
    cfnconfig = _write(tmp_path / "cfnconfig", "cfn_region=us-west-2\n")

    wrapper_text = SBATCH_SOURCE.read_text(encoding="utf-8")
    wrapper_text = wrapper_text.replace(
        'cluster_config="/opt/parallelcluster/shared/cluster-config.yaml"',
        f'cluster_config="{cluster_config}"',
    )
    wrapper_text = wrapper_text.replace(
        "/etc/parallelcluster/cfnconfig",
        str(cfnconfig),
    )
    wrapper_text = wrapper_text.replace(
        'exec "/opt/slurm/sbin/${slurm_command}"',
        f'exec "{fake_slurm}"',
    )
    wrapper = _write(tmp_path / "sbatch", wrapper_text, mode=0o755)
    return wrapper


def _run(
    wrapper: Path, *args: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{wrapper.parent / 'bin'}:{env['PATH']}"
    env["USER"] = "ubuntu"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(wrapper), *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_sbatch_wrapper_requires_comment(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path)
    result = _run(wrapper, "--partition", "i8", "job.sh")
    assert result.returncode == 1
    assert "Please specify a cost center" in result.stderr


def test_sbatch_wrapper_rejects_reserved_idle(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path)
    result = _run(wrapper, "--comment", "idle", "job.sh")
    assert result.returncode == 1
    assert "reserved" in result.stderr


def test_sbatch_wrapper_skip_mode_requires_comment_and_checks_cost_center(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, enforce_budget="skip", budget_mode="missing")
    result = _run(wrapper, "--comment=project-a", "job.sh")
    assert result.returncode == 0
    assert "cluster AWS Budget check skipped" in result.stderr
    assert "REAL_SLURM [--comment=project-a] [--export=ALL] [job.sh]" in result.stdout


def test_sbatch_wrapper_rejects_unknown_cost_center(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, registry_mode="unknown")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "does not exist" in result.stderr
    assert "cost center 'project-a' does not exist" in result.stderr
    assert (
        "https://us-west-2.console.aws.amazon.com/billing/home#/budgets/details?name=cluster-a"
        in result.stderr
    )
    assert (
        "dynamodbv2/home?region=us-west-2#item-explorer?table=dayec-cost-centers" in result.stderr
    )


def test_sbatch_wrapper_rejects_empty_cost_center_registry_json(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, registry_mode="empty_json")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "cost-center registry lookup returned empty JSON" in result.stderr
    assert "JSONDecodeError" not in result.stderr


def test_sbatch_wrapper_rejects_invalid_cost_center_registry_json(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, registry_mode="invalid_json")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "cost-center registry lookup returned invalid JSON" in result.stderr
    assert "JSONDecodeError" not in result.stderr


def test_sbatch_wrapper_rejects_unauthorized_user(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, registry_mode="unauthorized")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "not authorized" in result.stderr


def test_sbatch_wrapper_rejects_disabled_cost_center(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, registry_mode="disabled")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "not active" in result.stderr


def test_sbatch_wrapper_rejects_missing_aws_budget(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, budget_mode="missing")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "no readable AWS Budget named 'cluster-a'" in result.stderr


def test_sbatch_wrapper_rejects_exceeded_cluster_budget(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, budget_mode="exceeded")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "AWS Budget 'cluster-a' is exhausted" in result.stderr
    assert "100.00% used" in result.stderr


def test_sbatch_wrapper_budget_exceeded_override_is_opt_in_for_cluster(tmp_path: Path) -> None:
    for value in ("", "1", "true", "anything"):
        cluster_dir = tmp_path / f"cluster-{value or 'empty'}"
        cluster_dir.mkdir()
        cluster = _prepared_wrapper(cluster_dir, budget_mode="exceeded")
        cluster_result = _run(
            cluster,
            "--comment=project-a",
            "job.sh",
            extra_env={"DAY_PASS_ON_BUDGET_EXCEEDED": value},
        )
        assert cluster_result.returncode == 0
        assert "WARNING: AWS Budget 'cluster-a' is exhausted" in cluster_result.stderr
        assert "REAL_SLURM [--comment=project-a] [--export=ALL] [job.sh]" in cluster_result.stdout


def test_sbatch_wrapper_budget_overrides_remain_disabled_when_unset_or_false(
    tmp_path: Path,
) -> None:
    for ordinal, value in enumerate((None, "0", "false", "FALSE")):
        env = {} if value is None else {"DAY_PASS_ON_BUDGET_EXCEEDED": value}
        wrapper_dir = tmp_path / f"disabled-{ordinal}"
        wrapper_dir.mkdir()
        wrapper = _prepared_wrapper(wrapper_dir, budget_mode="exceeded")
        result = _run(wrapper, "--comment=project-a", "job.sh", extra_env=env)
        assert result.returncode == 1
        assert "AWS Budget 'cluster-a' is exhausted" in result.stderr


def test_sbatch_wrapper_ignores_monthly_usage_telemetry_and_usage_table_tag(
    tmp_path: Path,
) -> None:
    for mode in ("exceeded", "stale", "missing", "empty_json", "invalid_json"):
        wrapper_dir = tmp_path / mode
        wrapper_dir.mkdir()
        wrapper = _prepared_wrapper(
            wrapper_dir,
            usage_mode=mode,
            include_usage_table_tag=False,
        )
        result = _run(wrapper, "--comment", "project-a", "job.sh")
        assert result.returncode == 0, (mode, result.stderr)
        assert "usage" not in result.stderr.lower()

    malformed_cap_wrapper = _prepared_wrapper(
        tmp_path / "malformed-cap",
        registry_mode="malformed",
    )
    malformed_cap_result = _run(malformed_cap_wrapper, "--comment", "project-a", "job.sh")
    assert malformed_cap_result.returncode == 0


def test_sbatch_wrapper_enforces_active_until(tmp_path: Path) -> None:
    future = (
        (datetime.now(timezone.utc) + timedelta(hours=1))
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    future_wrapper = _prepared_wrapper(tmp_path / "future", registry_active_until=future)
    future_result = _run(future_wrapper, "--comment", "project-a", "job.sh")
    assert future_result.returncode == 0
    assert f"active_until={future}" in future_result.stderr

    expired = (
        (datetime.now(timezone.utc) - timedelta(seconds=1))
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    expired_wrapper = _prepared_wrapper(tmp_path / "expired", registry_active_until=expired)
    expired_result = _run(expired_wrapper, "--comment", "project-a", "job.sh")
    assert expired_result.returncode == 1
    assert f"expired at active_until={expired}" in expired_result.stderr

    invalid_wrapper = _prepared_wrapper(
        tmp_path / "invalid-active-until",
        registry_active_until="2026-08-01T12:30:00+00:00",
    )
    invalid_result = _run(invalid_wrapper, "--comment", "project-a", "job.sh")
    assert invalid_result.returncode == 1
    assert "must be exactly YYYY-MM-DDTHH:MM:SSZ" in invalid_result.stderr


def test_sbatch_wrapper_allows_under_budget_project(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, budget_mode="ok")
    result = _run(wrapper, "--comment", "project-a", "--partition", "i8", "job.sh")
    assert result.returncode == 0
    assert "cluster 'cluster-a' budget" in result.stderr
    assert (
        "cluster budget monitor: https://us-west-2.console.aws.amazon.com/"
        "billing/home#/budgets/details?name=cluster-a"
    ) in result.stderr
    assert "cost center 'project-a' admission ok" in result.stderr
    assert (
        "cost-center report: https://us-west-2.console.aws.amazon.com/dynamodbv2/home"
        in result.stderr
    )
    assert (
        "REAL_SLURM [--comment=project-a] [--export=ALL] [--partition] [i8] [job.sh]"
        in result.stdout
    )


def test_sbatch_wrapper_preserves_exclusive_allocation(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, enforce_budget="skip")
    result = _run(wrapper, "--comment=project-a", "--exclusive", "--partition", "i8", "job.sh")

    assert result.returncode == 0
    assert (
        "REAL_SLURM [--comment=project-a] [--export=ALL] [--exclusive] [--partition] [i8] [job.sh]"
        in result.stdout
    )


def test_sbatch_wrapper_rejects_all_memory_placement_flags(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, enforce_budget="skip")

    for memory_args in (
        ("--mem=8G",),
        ("--mem", "8G"),
        ("--mem-per-cpu=2G",),
        ("--mem-per-cpu", "2G"),
        ("--mem-per-gpu=16G",),
        ("--mem-per-gpu", "16G"),
        ("--mem-per-tres=gres/gpu:16G",),
        ("--mem-per-tres", "gres/gpu:16G"),
    ):
        result = _run(wrapper, "--comment=project-a", *memory_args, "job.sh")
        assert result.returncode == 1, memory_args
        assert "Slurm memory placement is disabled" in result.stderr
        assert "REAL_SLURM" not in result.stdout


def test_sbatch_wrapper_preserves_nonmemory_scheduling_arguments(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, enforce_budget="skip")
    result = _run(
        wrapper,
        "--comment=project-a",
        "--exclusive=user",
        "--nodes",
        "2",
        "--cpus-per-task=8",
        "--mem-bind=local",
        "--hint=nomultithread",
        "job.sh",
    )

    assert result.returncode == 0
    assert (
        "REAL_SLURM [--comment=project-a] [--export=ALL] [--exclusive=user] "
        "[--nodes] [2] [--cpus-per-task=8] [--mem-bind=local] "
        "[--hint=nomultithread] [job.sh]" in result.stdout
    )


def test_sbatch_wrapper_rejects_unknown_enforcement_value(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, enforce_budget="maybe")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "unknown aws-parallelcluster-enforce-budget value" in result.stderr
