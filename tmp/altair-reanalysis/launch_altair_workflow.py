#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess


ILMN_BASE_COMMAND = (
    "bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf "
    "produce_snv_concordances produce_alignstats produce_relatedness produce_contam_estimate "
    "produce_verifybamid2_panel_comparison produce_mosdepth produce_multiqc_cram "
    "--config 'aligners=[\"sent\"]' 'dedupers=[\"dmd\"]' 'snv_callers=[\"sentd\"]' "
    "'multiqc_qc={\"include_no_dedup_alignment_qc\":false}' -p -j 100 -k -T 1"
)

HYBRID_BASE_COMMAND = (
    "bin/day_run produce_snv_concordances produce_sentdhiom_sv produce_sentdhiom_snv_vcf "
    "--config 'dedupers=[\"dmd\"]' -p -j 100 -k"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-id", required=True)
    parser.add_argument("--stage-dir", required=True)
    parser.add_argument("--kind", choices=("ilmn", "hybrid"), required=True)
    parser.add_argument("--session-name")
    args = parser.parse_args()

    base = ILMN_BASE_COMMAND if args.kind == "ilmn" else HYBRID_BASE_COMMAND
    dy_command = f"{base} -n && {base}"
    cmd = [
        "dyec",
        "workflow",
        "launch",
        "--profile",
        "lsmc",
        "--region",
        "us-west-2",
        "--cluster",
        "dra-enabled",
        "--analysis-id",
        args.analysis_id,
        "--executing-entity",
        "johnm",
        "--git-tag",
        "1.0.17",
        "--stage-dir",
        args.stage_dir,
        "--session-name",
        args.session_name or args.analysis_id,
        "--dy-command",
        dy_command,
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
