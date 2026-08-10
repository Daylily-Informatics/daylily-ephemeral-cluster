#!/usr/bin/env python3
"""Queue the two approved DayOA dry runs in their initialized tmux panes."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text

CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"

COMMON_TARGETS = (
    "produce_sentdhiomr2_kitchensink "
    "produce_sentdhiomr2_nicu_research "
    "produce_sentdhiomr2_jasmine_sharded_per_sample "
)
COMMON_CONFIG = (
    "--config genome_build=hg38 aligners='[\"sentmm2ont\"]' dedupers='[\"na\"]' "
    "snv_callers='[\"sentdhiomr2\"]' sv_callers='[]' htd_callers='[\"smn12\"]' "
    "use_fq_data_starting_hrs=0 use_fq_data_up_to_hrs=25 "
)
RUNS = {
    "dayoa_take333lc_hg002_5x5x_20260804": (
        COMMON_TARGETS
        + "produce_sentdhiomr2_inflection_analytical_package "
        + "results/day/hg38/reports/DAY_final_multiqc.html "
        + "--configfile config/hiomr2_take333lc_hg002_5x5x.yaml "
        + COMMON_CONFIG
        + "hiomr2_inflection_package_mode=analytical seqone_delivery_batch_id=take333lc "
        + "-j 333 -T 0 -p -k --rerun-triggers mtime -n"
    ),
    "dayoa_remaining_giab_20260804": (
        COMMON_TARGETS
        + "results/day/hg38/reports/DAY_final_multiqc.html "
        + "--configfile config/hiomr2_remaining_giab.yaml "
        + COMMON_CONFIG
        + "-j 333 -T 0 -p -k --rerun-triggers mtime -n"
    ),
}


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    lines = ["set -euo pipefail"]
    for session, args in RUNS.items():
        analysis_id = "take333lc" if "take333lc" in session else "remaining-giab"
        remote_command = (
            f"dy-r {args} > /home/ubuntu/{analysis_id}_dry.log 2>&1; "
            "rc=$?; "
            f"printf 'DRY_RC=%s\\n' \"$rc\" > /home/ubuntu/{analysis_id}_dry.rc; "
            "printf '\\nDRY_RUN_TERMINAL_RC=%s\\n' \"$rc\""
        )
        remote_path = f"/home/ubuntu/{analysis_id}_dry.command"
        write_remote_text(
            target.instance_id,
            REGION,
            remote_path,
            remote_command,
            profile=PROFILE,
            as_user="ubuntu",
        )
        lines.append(f"rm -f /home/ubuntu/{analysis_id}_dry.rc")
        lines.append(f"tmux load-buffer -b {analysis_id}_dry {remote_path}")
        lines.append(f"tmux paste-buffer -b {analysis_id}_dry -t {session}")
        lines.append(f"tmux send-keys -t {session} Enter")
    result = run_shell(
        target.instance_id,
        REGION,
        "\n".join(lines),
        profile=PROFILE,
        as_user="ubuntu",
        timeout=120,
        comment="Queue two DayOA HIOMR2 dry runs",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
