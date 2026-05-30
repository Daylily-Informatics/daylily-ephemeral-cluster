#!/usr/bin/env bash
set -euo pipefail
printf 'UTC\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'INSPECTION_DU_PROCESSES\n'
ps -u ubuntu -o pid=,ppid=,stat=,etime=,cmd= | grep -E 'du -s[h b]? /fsx/analysis_results/ubuntu|sort -h|capacity_snapshot_headnode' | grep -v grep || true
printf 'FAST_ANALYSIS_DIR_COUNT\t'
find /fsx/analysis_results/ubuntu -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' '
printf '\nFAST_STAGING_DIR_COUNT\t'
find /fsx/staging/staged_external_sequencing_data -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' '
printf '\nFAST_DF\n'
df -h /fsx || true
printf 'FAST_TMUX_COUNT\t'
tmux ls 2>/dev/null | wc -l | tr -d ' '
printf '\nFAST_DAYLILY_TMUX_COUNT\t'
tmux ls 2>/dev/null | grep -Ec 'ccv20260529|daylily|bcl|roche|ultima|hybrid|illumina' || true
printf 'FAST_CONTROLLER_PROCESS_COUNT\t'
ps -u ubuntu -o cmd= | grep -E 'day_run|snakemake|daylily_run_omics_analysis_headnode' | grep -v grep | wc -l | tr -d ' '
printf '\nFAST_SLURM_JOB_COUNT\t'
squeue -h 2>/dev/null | wc -l | tr -d ' '
printf '\nFAST_SLURM_RUNNING_COUNT\t'
squeue -h -t R 2>/dev/null | wc -l | tr -d ' '
printf '\nFAST_SLURM_PENDING_CONFIGURING_COUNT\t'
squeue -h -t PD,CF 2>/dev/null | wc -l | tr -d ' '
printf '\nFAST_SLURM\n'
squeue -o '%i|%P|%C|%T|%M|%D|%R|%j' || true
