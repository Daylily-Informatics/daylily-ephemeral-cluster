#!/usr/bin/env python3
"""Launch NA00232/NA09677 chip1+chip2 FASTQ hybrid HIOMR dry-run via DYEC."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys


DYEC = "/Users/jmajor/miniconda3/envs/DAY-EC/bin/dyec"
STAGE_DIR = (
    "/home/ubuntu/daylily-staged-configs/"
    "hybonly_hybrid_hiomr_na2_chip12_fastq_20260606T120700Z_config"
)
SESSION = "hybonly_hybrid_hiomr_na2_chip12_fastq_dryrun2_20260606T120700Z"

DY_COMMAND = (
    "bin/day_run "
    "produce_sent_align "
    "produce_dmd_dedup_cram "
    "produce_sentd_snv_vcf "
    "produce_sentdhiomr_snv_vcf "
    "produce_sentdhiomr_sv "
    "produce_snv_concordances "
    "produce_sentdhiomr_cnv "
    "produce_sentdhiomr_segdup "
    "produce_sentdhiomr_mito "
    "produce_expansionhunter "
    "produce_alignstats "
    "produce_relatedness "
    "produce_gatk_contam_estimate "
    "produce_site_mix_contam_estimate "
    "produce_global_contam_check "
    "produce_vep "
    "produce_multiqc_all "
    "results/day/hg38_broad/reports/DAY_final_multiqc.html "
    "results/day/hg38_broad/reports/dayoa_evidence_manifest.json "
    "--config "
    "'aligners=[\"sent\"]' "
    "'dedupers=[\"dmd\"]' "
    "'snv_callers=[\"sentd\",\"sentdhiomr\"]' "
    "'sv_callers=[\"sentdhiomr\"]' "
    "'sentdhiomr={\"segdup_genes\":\"CYP11B1,NCF1,SMN1\"}' "
    "'contam_identity={\"primary_snv_caller\":\"sentd\"}' "
    "'multiqc_qc={\"enable_tools\":[\"vep\",\"contam_identity\"]}' "
    "-j 125 -p -k --rerun-triggers mtime -n"
)


def main() -> int:
    cmd = [
        DYEC,
        "workflow",
        "launch",
        "--profile",
        "lsmc",
        "--region",
        "us-west-2",
        "--cluster",
        "hyb-only",
        "--stage-dir",
        STAGE_DIR,
        "--session-name",
        SESSION,
        "--analysis-id",
        SESSION,
        "--executing-entity",
        "ubuntu",
        "--git-tag",
        "jem-dev",
        "--genome",
        "hg38_broad",
        "--dy-command",
        DY_COMMAND,
        "--dry-run",
    ]
    print("DYEC_COMMAND=" + shlex.join(cmd))
    env = {**os.environ, "AWS_PROFILE": "lsmc"}
    result = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
