#!/usr/bin/env bash
set -euo pipefail
printf 'UTC\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'HOST\t%s\n' "$(hostname)"
printf 'FSX_DF\n'
df -h /fsx || true
printf 'ANALYSIS_DIR_COUNT\t'
find /fsx/analysis_results/ubuntu -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' '
printf '\nANALYSIS_DIR_BYTES\t'
du -sb /fsx/analysis_results/ubuntu 2>/dev/null | awk '{print $1}' || true
printf 'ANALYSIS_TOP30\n'
du -sh /fsx/analysis_results/ubuntu/* 2>/dev/null | sort -h | tail -30 || true
printf 'TMUX_SESSIONS\n'
tmux ls 2>/dev/null || true
printf 'TMUX_SESSION_COUNT\t'
tmux ls 2>/dev/null | wc -l | tr -d ' '
printf '\nDAYLILY_TMUX_COUNT\t'
tmux ls 2>/dev/null | grep -Ec 'ccv20260529|daylily|bcl|roche|ultima|hybrid|illumina' || true
printf 'CONTROLLER_PROCESSES\n'
ps -u ubuntu -o pid=,ppid=,stat=,etime=,cmd= | grep -E 'day_run|snakemake|daylily_run_omics_analysis_headnode|tmux new-session|tmux attach' | grep -v grep || true
printf 'CONTROLLER_PROCESS_COUNT\t'
ps -u ubuntu -o cmd= | grep -E 'day_run|snakemake|daylily_run_omics_analysis_headnode' | grep -v grep | wc -l | tr -d ' '
printf '\nSLURM_JOBS\n'
squeue -o '%i|%P|%C|%T|%M|%D|%R|%j' || true
printf 'SLURM_JOB_COUNT\t'
squeue -h 2>/dev/null | wc -l | tr -d ' '
printf '\nSLURM_RUNNING_COUNT\t'
squeue -h -t R 2>/dev/null | wc -l | tr -d ' '
printf '\nSLURM_PENDING_CONFIGURING_COUNT\t'
squeue -h -t PD,CF 2>/dev/null | wc -l | tr -d ' '
printf '\nFSX_STAGING_DIRS\n'
find /fsx/staging/staged_external_sequencing_data -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort || true
printf 'FSX_STAGING_DIR_COUNT\t'
find /fsx/staging/staged_external_sequencing_data -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' '
printf '\n'
