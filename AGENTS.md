# Shell Session Defaults

- Default to an interactive shell for shell work. On this Mac, use the user's default shell unless the user explicitly asks for another shell.
- For AWS EC2, ParallelCluster, and other remote Linux hosts, default to an interactive `bash` login shell as `ubuntu`. Do not use `root` unless the user explicitly grants permission for that specific work; use targeted `sudo` from `ubuntu` when escalation is required.
- For Daylily/DayOA/DAY-EC headnode workflow work, use an interactive `ubuntu` tmux/login-shell pane for controllers and workflow commands. Run setup as separate commands in that pane (`source dyoainit`, then `dy-a ...`, then `dy-r ...`) so aliases/functions are defined before use.
- SSM Run Command is for simple inspection or for writing helper scripts through the supported helpers. Do not launch workflow controllers or rely on `dy-*` aliases from non-interactive SSM scripts.

# DayOA Workflow Command Contract

- Read `AGENTS-HOW-TO-RUN-DAYOA.md` before any DayOA workflow work.
- Never invoke `snakemake` directly for DayOA workflow work, including dry-runs, unlocks, help, live runs, or recovery commands. Always use the DayOA wrapper command `dy-r` from an initialized DayOA shell. `dy-r` passes all targets and flags through to Snakemake for you.
- DayOA workflow work must run inside a persistent, meaningfully named `tmux` session on the headnode, as the `ubuntu` user, with an interactive bash login shell. The `tmux` session must remain alive after any submitted command exits so status and follow-up commands can use the same initialized shell.
- The required DayOA sequence is:
  1. `cd /path/to/daylily-omics-analysis`
  2. `source dyoainit`
  3. `dy-a slurm hg38` or `dy-a slurm hg38_broad`
  4. `dy-r <targets> <flags>`
- Example DayOA smoke/dry-run command: `dy-r help -p -k -j 1 -n`.
- For BCL/DayOA execution, send these commands into the persistent `tmux` pane as separate commands. Do not collapse setup and execution into a one-shot non-interactive SSM script.

# DayOA Benchmark Collection

When comparing DayOA workflow runtime, threads, instance mix, or task cost from DAY-EC/headnode work, collect the combined benchmark report from the target DayOA analysis repo root instead of scraping partial summaries. Run from the headnode as `ubuntu` in an interactive bash login shell after initializing DayOA:

```bash
source dyoainit
dy-a slurm <genome_build>
bash bin/util/benchmarks/collect_day_benchmark_data.sh <genome_build>
```

For hybrid Broad-reference runs, the genome build is usually `hg38_broad`, producing:

```text
results/day/hg38_broad/reports/benchmarks_summary.tsv
```

Use the collector output because it adds the authoritative `sample` column from the benchmark file directory structure. Raw task benchmark files live under:

```text
results/day/<genome_build>/**/benchmarks/*.bench.tsv
```

The combined benchmark TSV contains task-level runtime/cost metadata, including `sample`, `rule`, `s`, `h:m:s`, memory fields, `io_in`, `io_out`, `mean_load`, `cpu_time`, `hostname`, `ip`, `nproc`, `cpu_efficiency`, `instance_type`, `region_az`, `spot_cost`, `snakemake_threads`, and `task_cost`.

For cost/performance reports, aggregate directly from those rows: `sum(s)` for task wall time, `sum(cpu_time)` for observed CPU time, `sum(s * snakemake_threads / 3600)` for allocated vCPU-hours, and `sum(task_cost)` for task cost. Keep this separate from cluster startup, Slurm pending/configuring time, and controller wall clock unless the user explicitly asks for broader accounting.

# Safety Preferences

- Do not execute destructive AWS resource changes unless the user gives a second explicit approval after being told the action is destructive.
- Do not answer interactive confirmation prompts for destructive AWS changes unless that second explicit approval has already been given in the current thread.
- Treat an initial request to "teardown", "destroy", "delete", or similar as permission to inspect, prepare, or dry-run only. Before any live destructive action, restate the exact effect and wait for a separate explicit confirmation.
- Always read `.md` and other instruction files in `~/.agents/*`, `~/.codex/*`, `./.agents`, `./.codex`, `./AGENTS.md`, and `./CLAUDE.md`.
- Unless the user explicitly asks for fallback behavior in the current thread, do not add, preserve, or rely on fallback behavior. Prefer direct fixes and hard failures over silent fallback paths.

# Headnode SSM Access

- All SSM interactive sessions and command payloads that interact with headnodes must run as `ubuntu` in a bash login shell.
- Do not use `root` for headnode work. The `ubuntu` user is in sudoers; use targeted `sudo` from `ubuntu` only when escalation is required.
- Interactive sessions must use `SSM-SessionManagerRunShell` configured with `runAsDefaultUser=ubuntu` and bash login-shell behavior.
- Command payloads must go through the central `daylily_ec.aws.ssm.run_shell` and `daylily_ec.aws.ssm.write_remote_text` helpers rather than ad hoc `aws ssm send-command` calls.
- `daylily-ec headnode connect` must preserve interactive TUI/editor key chords, especially Emacs `Ctrl-S` and `Ctrl-X Ctrl-S`. Keep both layers of XON/XOFF protection: the remote ubuntu login shell must disable flow control, and the local `daylily_ec.aws.ssm.start_session` path must keep a local `/dev/tty` flow-control guard running while Session Manager owns the terminal. A one-time local `stty -ixon -ixoff` is not sufficient because the AWS Session Manager/plugin startup path can leave the live local TTY with flow control enabled again.
- Do not remove or bypass the `tests/test_ssm.py` guardrail coverage for the local flow-control guard. Regression evidence should include a real `daylily-ec headnode connect` session where `cat -v` receives bare `Ctrl-S` as `^S`; for editor validation, `emacs -Q` should enter `I-search` on `Ctrl-S` and write the file on `Ctrl-X Ctrl-S`.

# Local Environment

- Use the repo activation flow before running Daylily commands. If the `DAY-EC` Conda environment is not present or dependencies are missing, run `source ./activate` from the repo root to create/activate it, then use the `DAY-EC` environment for tests and CLI commands.

# Working Docs And Plan Ledgers

- Every repo should have a `docs/plans/` directory. Create it when it is missing.
- Store plans, ledger plans, execution ledgers, and AI working documents used to carry out repo work under `docs/plans/`.
- Treat these files as durable repo artifacts: check them in and preserve them with the repo unless the user explicitly asks to remove or archive one.
- Name plan and ledger files with a datetime in the filename, such as `YYYYMMDDTHHMMSSZ_<short_slug>_ledger.md` or `YYYYMMDD_<short_slug>.md`.
- Do not keep the authoritative plan or execution ledger only in chat, temporary directories, or agent-local scratch space.

# ParallelCluster CLI

- `pcluster` is not an `aws` CLI subcommand. Do not pass AWS CLI-only flags such as `--json` to `pcluster`; ParallelCluster commands emit JSON by default.

# DYEC Run Mounts

- Do not treat FSx/DYEC run-mount creation as timed out before at least 30 minutes. Dynamic FSx data repository associations can legitimately stay in `CREATING` for around 30 minutes, especially large Illumina run directories.
- When running `dyec mounts create --wait` or equivalent run-mount operations, set an explicit timeout comfortably above 30 minutes when the CLI supports it, and continue read-only lifecycle polling rather than retrying, duplicating, deleting, or declaring failure at the default short timeout.

# Version Tags

- Daylily version tags should not use a leading `v`. When determining the next version, use non-`v` semver tags as the source of truth.

# Slurm Service Boundary

- Do not perform Slurm service, daemon, scheduler, partition, accounting, node-health, node drain/resume, or queue interventions unless the user first receives a specific proposal for that exact Slurm action and explicitly approves it in the current thread.
- In Dayhoff, DayOA, and DYEC work, Slurm is an expected infrastructure service, not an optimization target for the coding agent. Do not restart `slurmd`, repair nodes, modify Slurm config, alter partitions, drain/resume nodes, tune scheduling, or otherwise administer Slurm while running workflow tests.
- Jobs in Slurm `CF`/`CONFIGURING` can legitimately remain there while ParallelCluster creates spot instances from scratch; this can take tens of minutes. This is information for status reporting only, not a trigger for action or job management.
- Do not actively manage workflow jobs. Scheduling, retries, queue state, and job lifecycle are Snakemake/Slurm responsibilities. Do not cancel, requeue, hold, release, reprioritize, drain/resume, restart services for, or otherwise manipulate jobs or scheduler state unless the user explicitly approves that exact action in the current thread.
- Monitoring and reporting are allowed. Jobs running for more than 3 hours may be flagged as `needs investigation`, but do not take corrective action without confirmed user approval.
- If Slurm is unavailable or unhealthy, record the blocker and route the durable fix through ParallelCluster/pcluster configuration or infrastructure code changes.
