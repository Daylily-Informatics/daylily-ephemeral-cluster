# How To Run DayOA From An Agent

This is the required command contract for Daylily Omics Analysis (`daylily-omics-analysis`, DayOA) workflow work from DYEC/headnode agents.

## Hard Rules

- Never invoke `snakemake` directly for DayOA work. This includes help, dry-runs, unlock/recovery, live execution, and status/control operations.
- Always use `dy-r` for DayOA workflow commands. `dy-r` passes all targets and flags through to Snakemake for you; that is the supported DayOA execution interface.
- DayOA workflow work must run on the headnode as `ubuntu` inside a persistent, meaningfully named `tmux` session.
- The `tmux` session must run an interactive bash login shell and must remain alive after submitted commands exit.
- Use SSM/daylily-ec only to connect to the headnode, inspect state, or send keys into the persistent tmux pane. Do not use one-shot non-interactive SSM scripts as workflow controllers.
- Send setup and execution as separate commands. Do not compress `source dyoainit && dy-a ... && dy-r ...` into one line.

## Required Sequence

Inside the persistent headnode tmux pane:

```bash
cd /path/to/daylily-omics-analysis
source dyoainit
dy-a slurm hg38
dy-r <targets> <flags>
```

Use `hg38_broad` instead of `hg38` when the workflow/run configuration requires it:

```bash
dy-a slurm hg38_broad
```

Smoke/dry-run example:

```bash
dy-r help -p -k -j 1 -n
```

## Persistent tmux Pattern

Use a meaningful session name that includes the work purpose, cluster/run if useful, and date/stamp:

```bash
SESSION=dayoa_bcl25b_phase2_20260602
tmux new-session -d -s "$SESSION" 'bash -il'
tmux send-keys -t "$SESSION" 'cd /fsx/analysis_results/ubuntu/<analysis-id>/daylily-omics-analysis' Enter
tmux send-keys -t "$SESSION" 'source dyoainit' Enter
tmux send-keys -t "$SESSION" 'dy-a slurm hg38' Enter
tmux send-keys -t "$SESSION" 'dy-r help -p -k -j 1 -n' Enter
```

Before sending follow-up commands to an existing session, verify it has exactly one window and one pane:

```bash
tmux list-windows -t "$SESSION"
tmux list-panes -t "$SESSION"
```

If there is more than one pane or window, stop and ask/inspect rather than guessing.

## Dry-Run And Live Run

Dry-run:

```bash
tmux send-keys -t "$SESSION" 'dy-r <targets> -p -k -j <jobs> --rerun-triggers mtime -n --config ...' Enter
```

Live run:

```bash
tmux send-keys -t "$SESSION" 'dy-r <targets> -p -k -j <jobs> --rerun-triggers mtime --config ...' Enter
```

If a workflow lock must be cleared, use the DayOA wrapper only:

```bash
dy-r --unlock
```

Do not call `snakemake --unlock` directly.

## Status And Monitoring

Status checks may read:

```bash
tmux capture-pane -pt "$SESSION" -S -200
squeue -u ubuntu
ps -fu ubuntu | awk '/dy-r|day_run|snakemake/ && !/awk/ {print}'
```

Reading Snakemake logs is allowed for diagnosis. Starting, unlocking, dry-running, or running the workflow must go through `dy-r`.

## Failure Contract

If `source dyoainit`, `dy-a`, or `dy-r` is unavailable or fails, stop and report the exact contract gap. Do not substitute raw `snakemake`, inferred config files, fallback paths, or a new checkout unless the user explicitly approves that change.
