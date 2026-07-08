from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "cmdcat-103-all-20260707"
REGION = "us-west-2"
PROFILE = "lsmc"
SESSION = "ccv_live_inflection-bjuice-product-v0.1_20260707T214334Z"


def main() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%H%M")
    out = Path(
        f"docs/plans/20260707T144453Z_inflection_failed5044_triage_{stamp}_invocation.json"
    )
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    remote = f"""
set -euo pipefail
date -u
repo=/fsx/analysis_results/ubuntu/{SESSION}/daylily-omics-analysis
log=$(ls -t "$repo"/.snakemake/log/*.snakemake.log | head -1)
echo SNAKE_LOG="$log"
echo EXTERNAL_5044_CONTEXT
grep -n -B60 -A80 "external jobid .*5044" "$log" || true
echo FAILURE_LINES
grep -n -E "Error in rule|RuleException|failed|FAILED|non-zero exit|one of the commands exited|5044|Exiting because" "$log" | tail -80 || true
echo SACCT_5044
sacct -j 5044 -o JobID,JobName%120,State,ExitCode,Elapsed,NodeList%80,ReqMem,MaxRSS -P || true
echo FIND_FINAL_NORM_LOGS_RECENT
find "$repo"/results/day/hg38_broad/HIOa-HG003-SR1x-ONT1x-0-D0-PF-ILMN-NOVASEQ/align/ont/na/snv/sentdhiomr/log -name "*final_norm.log" -mmin -30 -printf "%TY-%Tm-%TdT%TH:%TM:%TS %p\\n" | sort | tail -20 || true
echo FINAL_NORM_LOG_TAILS
while IFS= read -r f; do
  echo "==== $f ===="
  tail -n 80 "$f"
done < <(find "$repo"/results/day/hg38_broad/HIOa-HG003-SR1x-ONT1x-0-D0-PF-ILMN-NOVASEQ/align/ont/na/snv/sentdhiomr/log -name "*final_norm.log" -mmin -30 | sort)
"""
    result = run_shell(
        target.instance_id,
        REGION,
        remote,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=180,
        comment="triage inflection failed slurm job 5044",
    )
    payload = {
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "instance_id": target.instance_id,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(out)
    print(result.stdout[-30000:])
    print(result.stderr[-2000:])


if __name__ == "__main__":
    main()
