#!/usr/bin/env python3
"""Clear the failed preflight lock and retry HG002 without an hour filter."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text

PROFILE = "lsmc"
REGION = "us-west-2"
CLUSTER = "preval-hiomr2"
SESSION = "dayoa_take333lc_hg002_5x5x_20260804"
ROOT = "/fsx/analysis_results/preval-hiomr2/take333lc"

ARGS = (
    "produce_sentdhiomr2_kitchensink "
    "produce_sentdhiomr2_nicu_research "
    "produce_sentdhiomr2_jasmine_sharded_per_sample "
    "produce_sentdhiomr2_inflection_analytical_package "
    "results/day/hg38/reports/DAY_final_multiqc.html "
    "--configfile config/hiomr2_take333lc_hg002_5x5x.yaml "
    "--config genome_build=hg38 aligners='[\"sentmm2ont\"]' dedupers='[\"na\"]' "
    "snv_callers='[\"sentdhiomr2\"]' sv_callers='[]' htd_callers='[\"smn12\"]' "
    "hiomr2_inflection_package_mode=analytical seqone_delivery_batch_id=take333lc "
    "-j 333 -T 0 -p -k --rerun-triggers mtime -n"
)


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    command = (
        f"dy-r {ARGS} > /home/ubuntu/take333lc_dry.log 2>&1; "
        "rc=$?; printf 'DRY_RC=%s\\n' \"$rc\" > /home/ubuntu/take333lc_dry.rc; "
        "printf '\\nDRY_RUN_TERMINAL_RC=%s\\n' \"$rc\""
    )
    remote_path = "/home/ubuntu/take333lc_dry.command"
    write_remote_text(target.instance_id, REGION, remote_path, command, profile=PROFILE, as_user="ubuntu")
    lines = [
        "set -euo pipefail",
        f"tmux send-keys -t {SESSION} \"dyec analysis lock acquire --analysis-root {ROOT} --operation unlock --intent 'Clear failed dry-run working-directory lock'\" Enter",
        f"tmux send-keys -t {SESSION} 'dy-r --unlock' Enter",
        f"tmux send-keys -t {SESSION} \"dyec analysis lock acquire --analysis-root {ROOT} --operation write --intent 'Retry corrected HG002 dry plan'\" Enter",
        "rm -f /home/ubuntu/take333lc_dry.rc",
        f"tmux load-buffer -b take333lc_retry {remote_path}",
        f"tmux paste-buffer -b take333lc_retry -t {SESSION}",
        f"tmux send-keys -t {SESSION} Enter",
    ]
    result = run_shell(target.instance_id, REGION, "\n".join(lines), profile=PROFILE, as_user="ubuntu", timeout=120, comment="Retry corrected HG002 dry plan")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
