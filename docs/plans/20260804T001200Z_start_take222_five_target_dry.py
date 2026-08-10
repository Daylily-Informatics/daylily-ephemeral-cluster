#!/usr/bin/env python3
"""Start the exact Take222 five-target mtime dry run in its owner tmux."""

from __future__ import annotations

import shlex

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"
CHECKOUT = f"{ROOT}/daylily-omics-analysis"
SESSION = "dayoa_take222_hg003_hg004_smn12_20260803"
LOG = f"{CHECKOUT}/take222_hg003_hg004_na19235_na20775_fullcov_13.4.3_five_target_dry_20260804.log"
RC = "/home/ubuntu/take222_13.4.3_five_target_dry_20260804.rc"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    command = (
        "DAY_CONTAINERIZED=true dy-r "
        "produce_sentdhiomr2_kitchensink "
        "produce_sentdhiomr2_nicu_research "
        "produce_sentdhiomr2_jasmine_sharded_per_sample "
        "produce_sentdhiomr2_inflection_analytical_package "
        "results/day/hg38/reports/DAY_final_multiqc.html "
        "--configfile config/hiomr2_take222_hg003_hg004_na19235_na20775_fullcov.yaml "
        "--config genome_build=hg38 "
        "'aligners=[\"sentmm2ont\"]' "
        "'dedupers=[\"na\"]' "
        "'snv_callers=[\"sentdhiomr2\"]' "
        "'sv_callers=[]' "
        "'htd_callers=[\"smn12\"]' "
        "hiomr2_inflection_package_mode=analytical "
        "use_fq_data_starting_hrs=0 "
        "use_fq_data_up_to_hrs=25 "
        "seqone_delivery_batch_id=take222 "
        "-j 444 -p -T 1 -k --rerun-triggers mtime -n "
        f">{LOG} 2>&1; "
        "take222_status=$?; "
        f"printf 'TAKE222_13_4_3_FIVE_TARGET_DRY_RC=%s\\n' \"$take222_status\" >{RC}; "
        "unset take222_status"
    )
    script = f"""set -euo pipefail
test "$(tmux list-windows -t {shlex.quote(SESSION)} -F '#{{window_panes}}')" = 1
test "$(tmux list-panes -t {shlex.quote(SESSION)} -F '#{{pane_id}}' | wc -l | tr -d ' ')" = 1
test -z "$(squeue -h -u ubuntu)"
test -z "$(ps -fu ubuntu | awk '/bin\/day_run|snakemake/ && !/awk/ {{print}}')"
rg -q '"agent_id": "codex-take222-release-20260803"' {shlex.quote(ROOT + '/.dayoa_agent/write.lock/owner.json')}
test ! -e {shlex.quote(LOG)}
test ! -e {shlex.quote(RC)}
tmux send-keys -t {shlex.quote(SESSION)} {shlex.quote(command)} Enter
sleep 2
tmux capture-pane -pt {shlex.quote(SESSION)} -S -50
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Start exact Take222 five-target mtime dry run",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
