#!/usr/bin/env python3
"""Read-only verification of terminal Take222 release artifacts."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = f"""set -euo pipefail
export DAYOA_AGENT_ID=codex-take222-release-20260803
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION=dayoa_take222_hg003_hg004_smn12_20260803
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T234000Z_dayoa_13_4_3_dyec_release_slack_ledger.md'
dyec analysis visit --analysis-root {ROOT} --mode read --intent 'Verify terminal Take222 DayOA 13.4.3 release artifacts'
cd {ROOT}/daylily-omics-analysis
printf '%s\n' '== recent warning receipts =='
find results/day/hg38 -type f -name '*.json' -mmin -60 -print0 | sort -z | xargs -0 -r rg -l '"status"[[:space:]]*:[[:space:]]*"WARNING"' | tee /tmp/take222_warning_receipts.txt
printf 'warning_receipt_count='
wc -l < /tmp/take222_warning_receipts.txt
while IFS= read -r path; do
  printf '%s|' "$path"
  python - "$path" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding='utf-8'))
print(p.get('status'), p.get('query_sample') or p.get('analysis_unit') or '', 'metrics=', p.get('metrics'))
PY
done < /tmp/take222_warning_receipts.txt
printf '%s\n' '== final artifacts =='
stat -c '%s|%y|%n' results/day/hg38/reports/DAY_final_multiqc.html
find results/day/hg38 -type f -mmin -60 \( -name '*.tar.gz' -o -name '*.zip' \) -printf '%s|%y|%p\n' | sort -k3
printf '%s\n' '== queue/controller/lock =='
squeue -u ubuntu
ps -fu ubuntu | awk '/dy-r|bin\/day_run|snakemake/ && !/awk/ {{print}}'
test ! -e {ROOT}/.dayoa_agent/write.lock
"""
    result = run_shell(target.instance_id, REGION, script, profile=PROFILE, as_user="ubuntu", timeout=300, comment="Verify Take222 release artifacts")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
