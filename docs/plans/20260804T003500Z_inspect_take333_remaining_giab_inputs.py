#!/usr/bin/env python3
"""Read-only inventory for the Take333 HG002 and remaining-GIAB campaign."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = r"""set -euo pipefail
date -u +%Y-%m-%dT%H:%M:%SZ
printf '%s\n' '== filesystem capacity =='
df -hT /fsx /fsx/analysis_results /fsx/data /fsx/references
df -B1 /fsx | tail -1
printf '%s\n' '== analysis roots =='
find /fsx/analysis_results/preval-hiomr2 -mindepth 1 -maxdepth 2 -type d -name daylily-omics-analysis -printf '%h\n' | sort
printf '%s\n' '== candidate configs/manifests =='
find /fsx/analysis_results/preval-hiomr2 -path '*/daylily-omics-analysis/config/*' -type f \
  \( -name '*hg002*' -o -name '*take101*' -o -name '*take222*' -o -name '*5x*' -o -name 'analysis_units.tsv' -o -name 'sequencing_inputs.tsv' -o -name 'samples.tsv' -o -name 'libraries.tsv' -o -name 'units.tsv' \) \
  -printf '%s|%y|%p\n' | sort -k3
printf '%s\n' '== config summaries =='
for root in /fsx/analysis_results/preval-hiomr2/*/daylily-omics-analysis; do
  test -d "$root/config" || continue
  hits=$(find "$root/config" -maxdepth 1 -type f \( -name '*hg002*' -o -name '*take101*' -o -name '*take222*' -o -name '*5x*' \) -print)
  test -n "$hits" || continue
  printf 'ROOT=%s\n' "$root"
  for path in $hits; do
    printf '%s\n' "--- $path"
    rg -n 'analysis|sample|HG00|NA19|NA20|ILMN|ONT|FASTQ|fastq|fq_data|batch|platform|source' "$path" | head -80 || true
  done
done
printf '%s\n' '== active workflow state =='
squeue -u ubuntu
ps -fu ubuntu | awk '/dy-r|bin\/day_run|snakemake/ && !/awk/ {print}'
printf '%s\n' '== tmux =='
tmux list-sessions 2>/dev/null || true
"""
    result = run_shell(target.instance_id, REGION, script, profile=PROFILE, as_user="ubuntu", timeout=300, comment="Inspect Take333 and remaining GIAB inputs")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
