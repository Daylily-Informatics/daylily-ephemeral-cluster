#!/usr/bin/env bash
set -u

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
cd "$analysis_root" || exit 2
echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  . "$HOME/miniconda3/etc/profile.d/conda.sh"
  conda activate DAY-EC
fi
set +u
. dyoainit --project dyec-test --skip-project-check
dyo_rc=$?
echo "dyoainit_rc=$dyo_rc"
. bin/day_activate slurm hg38 remote
act_remote_rc=$?
echo "day_activate_slurm_hg38_remote_rc=$act_remote_rc"
. bin/day_activate slurm hg38
act_rc=$?
echo "day_activate_slurm_hg38_rc=$act_rc"
set -u
echo "env_summary:"
env | sort | grep -E '^(DAY|DY|PROJECT|SNAKEMAKE|CONDA|PATH)=' || true
