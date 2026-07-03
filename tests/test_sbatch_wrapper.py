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
    budget_tags: str | None = "project-a\tubuntu\n",
    aws_mode: str = "ok",
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
  project=""
  while [ "$#" -gt 0 ]; do
    if [ "$1" = "--budget-name" ]; then
      shift
      project="$1"
    fi
    shift || true
  done
  case "{aws_mode}" in
    ok) printf '200\\t50\\tUSD\\n' ;;
    exceeded) printf '200\\t200\\tUSD\\n' ;;
    missing) echo 'NotFoundException' >&2; exit 254 ;;
    malformed) printf 'None\\tNone\\tUSD\\n' ;;
    *) echo 'bad test aws mode' >&2; exit 2 ;;
  esac
  exit 0
fi
echo "unexpected aws call: $*" >&2
exit 2
""",
        mode=0o755,
    )

    budget_file = tmp_path / "pcluster-project-budget-tags.tsv"
    if budget_tags is not None:
        _write(budget_file, budget_tags)
    cluster_config = _write(
        tmp_path / "cluster-config.yaml",
        "\n".join(
            [
                "Tags:",
                "- Key: aws-parallelcluster-enforce-budget",
                f"  Value: \"{enforce_budget}\"",
                "",
            ]
        ),
    )
    cfnconfig = _write(tmp_path / "cfnconfig", "cfn_region=us-west-2\n")

    wrapper_text = SBATCH_SOURCE.read_text(encoding="utf-8")
    wrapper_text = wrapper_text.replace(
        'budget_file="/fsx/references/runtime_assets/budget_tags/pcluster-project-budget-tags.tsv"',
        f'budget_file="{budget_file}"',
    )
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
    assert "Please specify a project/budget name" in result.stderr


def test_sbatch_wrapper_allows_exact_rnd_without_budget_files(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, budget_tags=None, aws_mode="missing")
    result = _run(wrapper, "--comment", "RnD", "job.sh")
    assert result.returncode == 0
    assert "exact RnD bypass" in result.stderr
    assert "REAL_SLURM [--comment=RnD] [--export=ALL] [job.sh]" in result.stdout


def test_sbatch_wrapper_skip_mode_requires_comment_but_skips_budget_check(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, enforce_budget="skip", budget_tags=None)
    result = _run(wrapper, "--comment=project-a", "job.sh")
    assert result.returncode == 0
    assert "budget check skipped by cluster config" in result.stderr
    assert "REAL_SLURM [--comment=project-a] [--export=ALL] [job.sh]" in result.stdout


def test_sbatch_wrapper_rejects_project_missing_from_allow_list(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, budget_tags="other\tubuntu\n")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "was not found" in result.stderr
    assert "https://ursa.day.lsmc.bio/ursa-actions#budgets?budget=project-a" in result.stderr


def test_sbatch_wrapper_rejects_unauthorized_user(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, budget_tags="project-a\talice\n")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "not authorized" in result.stderr


def test_sbatch_wrapper_rejects_missing_aws_budget(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, aws_mode="missing")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "no readable AWS Budget named 'project-a'" in result.stderr


def test_sbatch_wrapper_rejects_exceeded_budget(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, aws_mode="exceeded")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "is exhausted" in result.stderr
    assert "100.00% used" in result.stderr


def test_sbatch_wrapper_allows_under_budget_project(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, aws_mode="ok")
    result = _run(wrapper, "--comment", "project-a", "--partition", "i8", "job.sh")
    assert result.returncode == 0
    assert "percent=25.00%" in result.stderr
    assert (
        "REAL_SLURM [--comment=project-a] [--export=ALL] [--partition] [i8] [job.sh]"
        in result.stdout
    )


def test_sbatch_wrapper_rejects_unknown_enforcement_value(tmp_path: Path) -> None:
    wrapper = _prepared_wrapper(tmp_path, enforce_budget="maybe")
    result = _run(wrapper, "--comment", "project-a", "job.sh")
    assert result.returncode == 1
    assert "unknown aws-parallelcluster-enforce-budget value" in result.stderr
