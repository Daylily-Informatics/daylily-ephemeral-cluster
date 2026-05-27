#!/usr/bin/env python3
"""Inspect focused Goodole3 workflow logs through the DYEC SSM helpers."""

from __future__ import annotations

import argparse

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster", default="goodole3")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--analysis-id", required=True)
    parser.add_argument("--lines", type=int, default=160)
    args = parser.parse_args()

    target = resolve_headnode_instance_id(args.cluster, args.region, profile=args.profile)
    root = f"/fsx/analysis_results/ubuntu/{args.analysis_id}"
    run_dir = f"/home/ubuntu/daylily-runs/{args.analysis_id}"
    script = f"""set -euo pipefail
printf 'INSTANCE=%s\\n' {target.instance_id!r}
printf 'ROOT=%s\\n' {root!r}
printf 'RUN_DIR=%s\\n' {run_dir!r}
test -d {root!r}
cd {root!r}
printf '\\n== root files ==\\n'
find . -maxdepth 2 -type f | sort | sed 's#^./##' || true
printf '\\n== status ==\\n'
find . -maxdepth 3 -type f -name '*status*.json' -print -exec cat {{}} \\; || true
printf '\\n== run dir status ==\\n'
cat {run_dir!r}/status.json || true
printf '\\n== tmux tail ==\\n'
find . -maxdepth 3 -type f -name '*tmux*.log' -print -exec tail -n {args.lines} {{}} \\; || true
printf '\\n== run dir tmux tail ==\\n'
tail -n {args.lines} {run_dir!r}/tmux.log || true
printf '\\n== final multiqc log ==\\n'
tail -n {args.lines} daylily-omics-analysis/results/day/hg38_broad/reports/logs/all__mqc_fin_a.log || true
printf '\\n== final multiqc files ==\\n'
ls -l daylily-omics-analysis/results/day/hg38_broad/reports/ || true
printf '\\n== dayoa summary logs ==\\n'
for path in daylily-omics-analysis/day_cmd.log daylily-omics-analysis/day_pipe_stats.json daylily-omics-analysis/sbatch_errs.log daylily-omics-analysis/unlock_fails.log; do
  printf '\\n-- %s --\\n' "$path"
  tail -n {args.lines} "$path" || true
done
"""
    result = run_shell(
        target.instance_id,
        args.region,
        script,
        profile=args.profile,
        timeout=300,
        comment=f"Inspect Goodole3 workflow logs for {args.analysis_id}",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
