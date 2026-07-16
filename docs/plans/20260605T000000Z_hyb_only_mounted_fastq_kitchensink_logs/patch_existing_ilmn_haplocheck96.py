#!/usr/bin/env python3
"""Add Haplocheck 96-thread settings to the existing dirty ILMN checkout."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell  # noqa: E402


SESSION = "hybonly_ilmn_haplocheck96_dryrun_20260606T091748Z"

SCRIPT_TEMPLATE = r"""
set -euo pipefail
repo=/fsx/analysis_results/ubuntu/hybonly_ilmn_kitchensink_mounted_20260606T053415Z/daylily-omics-analysis
run_dir=/home/ubuntu/daylily-runs/__SESSION__
mkdir -p "$run_dir"
cd "$repo"
if [[ ! -s "$run_dir/pre_haplocheck96_dirty_worktree.patch" ]]; then
  git diff > "$run_dir/pre_haplocheck96_dirty_worktree.patch"
fi
git diff > "$run_dir/pre_haplocheck96_patch_$(date -u +%Y%m%dT%H%M%SZ).patch"
python3 - <<'PY'
from pathlib import Path

repo = Path("/fsx/analysis_results/ubuntu/hybonly_ilmn_kitchensink_mounted_20260606T053415Z/daylily-omics-analysis")
rule_path = repo / "workflow/rules/contam_identity.smk"
config_paths = [
    repo / "config/day_profiles/slurm/templates/rule_config.yaml",
    repo / "config/day_profiles/slurm/rule_config.yaml",
]

rule_text = rule_path.read_text()
thread_block = (
    '        export HAPLOCHECK_THREADS={threads}\n'
    '        export JAVA_TOOL_OPTIONS="-XX:ActiveProcessorCount={threads} -XX:+UseParallelGC '
    '-XX:ParallelGCThreads={threads} -Djava.util.concurrent.ForkJoinPool.common.parallelism={threads} '
    '${JAVA_TOOL_OPTIONS:-}"\n'
)
marker = (
    '        set -euo pipefail\n'
    '        test {params.sample_ok:q} = ok\n'
    '        outdir="$(dirname {output.contamination:q})"\n'
)
replacement = (
    '        set -euo pipefail\n'
    '        test {params.sample_ok:q} = ok\n'
    + thread_block
    + '        outdir="$(dirname {output.contamination:q})"\n'
)
if "export HAPLOCHECK_THREADS={threads}" not in rule_text:
    count = rule_text.count(marker)
    if count != 2:
        raise SystemExit(f"expected two haplocheck shell markers, found {{count}}")
    rule_text = rule_text.replace(marker, replacement)
elif "ForkJoinPool.common.parallelism={threads}" not in rule_text:
    raise SystemExit("HAPLOCHECK_THREADS present but JVM parallelism flags missing")
rule_path.write_text(rule_text)

for config_path in config_paths:
    if not config_path.exists():
        continue
    config_lines = config_path.read_text().splitlines()
    out = []
    in_haplo = False
    seen_partition = False
    seen_threads = False
    for line in config_lines:
        if line.startswith("haplocheck:"):
            in_haplo = True
            out.append(line)
            continue
        if in_haplo and line and not line.startswith((" ", "\t")):
            in_haplo = False
        if in_haplo and line.strip().startswith("partition:"):
            out.append('    partition: "i192,i192mem,i192bigmem"')
            seen_partition = True
            continue
        if in_haplo and line.strip().startswith("threads:"):
            out.append("    threads: 96")
            seen_threads = True
            continue
        out.append(line)
    if not seen_partition or not seen_threads:
        raise SystemExit(
            f"missing haplocheck config keys in {config_path}: "
            f"partition={{seen_partition}} threads={{seen_threads}}"
        )
    config_path.write_text("\n".join(out) + "\n")
PY
touch config/day_profiles/slurm/*.yaml
echo "post_patch_status:"
git status --short -- workflow/rules/contam_identity.smk config/day_profiles/slurm/templates/rule_config.yaml config/day_profiles/slurm/rule_config.yaml
echo "post_patch_diff_target:"
git diff -- workflow/rules/contam_identity.smk config/day_profiles/slurm/templates/rule_config.yaml config/day_profiles/slurm/rule_config.yaml | sed -n '1,320p'
echo "active_haplocheck_config:"
grep -n -A8 -B2 '^haplocheck:' config/day_profiles/slurm/rule_config.yaml || true
echo "backup_patch=$run_dir/pre_haplocheck96_dirty_worktree.patch"
"""

SCRIPT = SCRIPT_TEMPLATE.replace("__SESSION__", SESSION)


def main() -> int:
    try:
        result = run_shell(
            "i-05374380b57fad901",
            "us-west-2",
            SCRIPT,
            profile="lsmc",
            as_user="ubuntu",
            timeout=120,
            comment="patch existing ILMN checkout Haplocheck 96 threads",
        )
    except SsmCommandFailedError as exc:
        print(exc.result.stdout, end="")
        print(exc.result.stderr, end="", file=sys.stderr)
        return exc.result.response_code or 1

    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.response_code


if __name__ == "__main__":
    raise SystemExit(main())
