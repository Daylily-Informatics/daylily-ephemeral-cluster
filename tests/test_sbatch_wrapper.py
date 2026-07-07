from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SBATCH_SOURCE = REPO_ROOT / "config" / "day_cluster" / "sbatch"


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
) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_slurm = _write(
        bin_dir / "real-slurm",
        "#!/bin/bash\nprintf 'REAL_SLURM'\nprintf ' [%s]' \"$@\"\nprintf '\\n'\n",
        mode=0o755,
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
      ok) printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"status":{{"S":"active"}},"monthly_cap_usd":{{"N":"200"}},"allowed_users":{{"SS":["ubuntu"]}}}}}}\\n' ;;
      unknown) printf '{{}}\\n' ;;
      unauthorized) printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"status":{{"S":"active"}},"monthly_cap_usd":{{"N":"200"}},"allowed_users":{{"SS":["alice"]}}}}}}\\n' ;;
      disabled) printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"status":{{"S":"disabled"}},"monthly_cap_usd":{{"N":"200"}},"allowed_users":{{"SS":["ubuntu"]}}}}}}\\n' ;;
      malformed) printf '{{"Item":{{"cost_center":{{"S":"project-a"}},"status":{{"S":"active"}},"monthly_cap_usd":{{"N":"NaN"}},"allowed_users":{{"SS":["ubuntu"]}}}}}}\\n' ;;
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
      missing) printf '{{}}\\n' ;;
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

    cluster_config = _write(
        tmp_path / "cluster-config.yaml",
        "\n".join(
            [
                "Tags:",
                "- Key: aws-parallelcluster-clustername",
                '  Value: "cluster-a"',
                "- Key: aws-parallelcluster-enforce-budget",
                f"  Value: \"{enforce_budget}\"",
                "- Key: aws-parallelcluster-cost-center-region",
                '  Value: "us-west-2"',
                "- Key: aws-parallelcluster-cost-center-table",
                '  Value: "dayec-cost-centers"',
                "- Key: aws-parallelcluster-cost-center-usage-table",
                '  Value: "dayec-cost-center-usage"',
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


def _run(wrapper: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{wrapper.parent / 'bin'}:{env['PATH']}"
    env["USER"] = "ubuntu"
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
    assert "https://ursa.day.lsmc.bio/ursa-actions#cost-centers?cost_center=project-a" in result.stderr


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


def test_sbatch_wrapper_rejects_exceeded_cost_center_cap(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, usage_mode="exceeded")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "cost-center monthly cap exceeded" in result.stderr


def test_sbatch_wrapper_rejects_stale_cost_center_usage(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, usage_mode="stale")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "cost-center usage is stale" in result.stderr


def test_sbatch_wrapper_allows_under_budget_project(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, budget_mode="ok")
    result = _run(wrapper, "--comment", "project-a", "--partition", "i8", "job.sh")
    assert result.returncode == 0
    assert "cluster 'cluster-a' budget" in result.stderr
    assert "cost center 'project-a' usage ok" in result.stderr
    assert (
        "REAL_SLURM [--comment=project-a] [--export=ALL] [--partition] [i8] [job.sh]"
        in result.stdout
    )


def test_sbatch_wrapper_strips_exclusive_allocation(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, enforce_budget="skip")
    result = _run(wrapper, "--comment=project-a", "--exclusive", "--partition", "i8", "job.sh")

    assert result.returncode == 0
    assert "ALERT WARNING: DYEC sbatch stripped exclusive allocation request '--exclusive'" in result.stderr
    assert (
        "REAL_SLURM [--comment=project-a] [--export=ALL] [--partition] [i8] [job.sh]"
        in result.stdout
    )
    assert "--exclusive" not in result.stdout


def test_sbatch_wrapper_rejects_unknown_enforcement_value(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, enforce_budget="maybe")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "unknown aws-parallelcluster-enforce-budget value" in result.stderr
