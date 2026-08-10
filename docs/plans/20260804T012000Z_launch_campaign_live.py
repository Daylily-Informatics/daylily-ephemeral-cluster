#!/usr/bin/env python3
"""Launch the two dry-run-approved DayOA controllers in persistent tmux panes."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text

PROFILE = "lsmc"
REGION = "us-west-2"
CLUSTER = "preval-hiomr2"

COMMON_TARGETS = (
    "produce_sentdhiomr2_kitchensink produce_sentdhiomr2_nicu_research "
    "produce_sentdhiomr2_jasmine_sharded_per_sample "
)
COMMON_CONFIG = (
    "--config genome_build=hg38 aligners='[\"sentmm2ont\"]' dedupers='[\"na\"]' "
    "snv_callers='[\"sentdhiomr2\"]' sv_callers='[]' htd_callers='[\"smn12\"]' "
)
RUNS = {
    "take333lc": {
        "session": "dayoa_take333lc_hg002_5x5x_20260804",
        "args": COMMON_TARGETS
        + "produce_sentdhiomr2_inflection_analytical_package results/day/hg38/reports/DAY_final_multiqc.html "
        + "--configfile config/hiomr2_take333lc_hg002_5x5x.yaml "
        + COMMON_CONFIG
        + "hiomr2_inflection_package_mode=analytical seqone_delivery_batch_id=take333lc "
        + "-j 333 -T 0 -p -k --rerun-triggers mtime",
    },
    "remaining-giab": {
        "session": "dayoa_remaining_giab_20260804",
        "args": COMMON_TARGETS
        + "results/day/hg38/reports/DAY_final_multiqc.html "
        + "--configfile config/hiomr2_remaining_giab.yaml "
        + COMMON_CONFIG
        + "use_fq_data_starting_hrs=0 use_fq_data_up_to_hrs=25 "
        + "-j 333 -T 0 -p -k --rerun-triggers mtime",
    },
}


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    shell_lines = ["set -euo pipefail"]
    for analysis_id, item in RUNS.items():
        command = (
            f"DAY_PROJECT=RnD DAYLILY_COST_CENTER=RnD dy-r {item['args']} > /home/ubuntu/{analysis_id}_live_retry.log 2>&1; "
            "rc=$?; "
            f"printf 'LIVE_RETRY_RC=%s\\n' \"$rc\" > /home/ubuntu/{analysis_id}_live_retry.rc; "
            "printf '\\nLIVE_RUN_TERMINAL_RC=%s\\n' \"$rc\""
        )
        remote_path = f"/home/ubuntu/{analysis_id}_live.command"
        write_remote_text(target.instance_id, REGION, remote_path, command, profile=PROFILE, as_user="ubuntu")
        session = item["session"]
        root = f"/fsx/analysis_results/preval-hiomr2/{analysis_id}"
        shell_lines.extend(
            [
                f"tmux send-keys -t {session} \"dyec analysis lock acquire --analysis-root {root} --operation write --intent 'Run approved DayOA 13.4.3 HIOMR2 campaign'\" Enter",
                f"rm -f /home/ubuntu/{analysis_id}_live_retry.rc",
                f"tmux load-buffer -b {analysis_id}_live {remote_path}",
                f"tmux paste-buffer -b {analysis_id}_live -t {session}",
                f"tmux send-keys -t {session} Enter",
            ]
        )
    result = run_shell(target.instance_id, REGION, "\n".join(shell_lines), profile=PROFILE, as_user="ubuntu", timeout=120, comment="Launch two approved HIOMR2 controllers")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
