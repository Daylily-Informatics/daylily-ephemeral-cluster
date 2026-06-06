# Shell Session Defaults

- Default to an interactive shell for shell work. On this Mac, use the user's default shell unless the user explicitly asks for another shell.
- For AWS EC2, ParallelCluster, and other remote Linux hosts, default to an interactive `bash` login shell as `ubuntu`. Do not use `root` unless the user explicitly grants permission for that specific work; use targeted `sudo` from `ubuntu` when escalation is required.
- For Daylily/DayOA/DAY-EC headnode workflow work, use an interactive `ubuntu` tmux/login-shell pane for controllers and workflow commands. Run setup as separate commands in that pane (`source dyoainit`, then `dy-a ...`, then `dy-r ...`) so aliases/functions are defined before use.
- SSM Run Command is for simple inspection or for writing helper scripts through the supported helpers. Do not launch workflow controllers or rely on `dy-*` aliases from non-interactive SSM scripts.
- Before any DayOA workflow work, read `AGENTS-HOW-TO-RUN-DAYOA.md`. Never invoke `snakemake` directly for DayOA work. Always use `dy-r` inside a persistent, meaningfully named `tmux` session running an interactive bash login shell as `ubuntu`; `dy-r` passes all targets and flags through to Snakemake for you.

# CRITICAL - HEADNODE ACCESS (READ FIRST)
**SSM is the only supported access model for AWS ParallelCluster headnodes.**
- Use the supported `daylily-ec headnode connect` / AWS Systems Manager path for headnode access.
- Do not use direct SSH, PEM files, or `pcluster ssh` for this repo's headnodes.
- Commands run through SSM must still use a login bash shell when they depend on PATH, conda, aliases, functions, Slurm, or Daylily shell setup.
- **PATTERN (MANDATORY)**: run `bash -l -c 'your command here'` inside the SSM session or SSM command invocation.
- **WHY**: Login shells initialize PATH, conda, aliases, functions.
- **WITHOUT login shell**: Commands fail silently or mislead status checks (squeue not found, conda unavailable, etc.).
- **NEVER deviate** from this pattern. No exceptions.
- See "SSM Commands" section below for details and examples.

# AWS CREDENTIALS
Ask user for profile name to set AWS_PROFILE to, never use default as profile name.

# UPON STARTING A NEW TERMINAL SESSION ON A MAC
On a mac, no workflows will actually ever be run, but we need the conda env for the dy-cli to work to debug and tinker locally.  This repo must be deployed to an AWS ParallelCluster headnode which has been configured by `daylily-ephemeral-cluster`, and each analysis workset is run from a clone of this repo (or reruns).

# TERMINAL STARTUP (ALWAYS RUN THESE COMMANDS IN THIS ORDER)
## ON A MAC 
Always `conda activate DAY-EC`, little is done in this repo from a mac, but most dependencies needed to tinker and debug are in the daylily-ephemeral-cluster env DAY-EC.

## ON THE HEADNODE (ubuntu)
- Intended use via is brokered by daylily-ephemeral-cluster, often via the GUI daylily-ursa. 
- CLONE REPO USING `day-clone` (which should be in the login bash PATH). See the day-clone --help for more info (and the .md docs).
- upon moving to reso cloned dir (the analysis dir):
  - INITIALIZE: source the `dyoainit` script to initialize the dy-cli. (note: the output of dyoainit should tell you how to activte slurm or local execution env, set genome build, run example commands.
  - ACTIVATE: `dy-a local hg38` to activate the local execution env, or  `dy-a slurm hg38` to activate the slurm execution env. Note, the second argument is the genome build, and must be set. In practice, this is almost always `hg38`, but could be `b37` or `hg38_broad`. 
  - RUN: `dy-r help` to see the available targets, and the init output should tell you how to run the common workflow. Important flags: -n for dry run, -p to print helpful info to stdout, -j for job limit (local should be 1 or 2, slurm can be 300-500), -k to keep going if a job fails... the dy-r cli command actually composes a complex snakemake command given these user command line specified ones. Run `dy-r --help` for all of them.
- For future work on replacing the `dy-*` alias model with shell functions or executable entrypoints, read `docs/potential_future_improvements.md` first.

## Headnode Persistent tmux Pipeline Launch Spec
Use this pattern when a user asks an agent to launch Daylily workflow commands on an AWS ParallelCluster headnode and leave the run inspectable after the agent disconnects.

### Required launch inputs
- AWS profile, region, and cluster name. Do not use the default AWS profile; ask the user when it is not specified.
- Workset code for `day-clone -d`, such as `take1` or `agbt_ug`.
- Git ref for `day-clone -t`, usually `main` unless the user gives another ref.
- S3 paths for `config/samples.tsv` and `config/units.tsv`.
- Genome build for `dy-a`, usually `hg38_broad` for Ultima and hybrid examples here.
- `dy-r` targets and flags.
- A unique, descriptive tmux session name that includes the workset/pipeline/date.

### Connect to the headnode
From a Mac terminal, activate `DAY-EC` first:

```bash
eval "$(conda shell.zsh hook)" && conda activate DAY-EC
```

Connect with the requested profile through SSM/daylily-ec:

```bash
AWS_PROFILE=<profile> daylily-ec headnode connect --profile <profile> --region <region> --cluster <cluster>
```

The resulting SSM shell must be the `ubuntu` user running a bash login shell. Verify with `id -un` and `echo "$0"`; if the shell is not a login bash shell, run `exec bash -l` before `day-clone`, `tmux`, `source dyoainit`, `dy-a`, or `dy-r`.

After connecting, verify you are `ubuntu` and that required commands are present. Fail loudly if any are missing:

```bash
id -un
command -v day-clone
command -v tmux
command -v squeue
```

### Create and use a persistent tmux session
Create one named session per launched pipeline. Do not reuse unrelated existing sessions.

Before sending keys, attaching, capturing output, or otherwise interacting with an existing tmux session, verify the session has exactly one window and exactly one pane. If either check fails, stop and report an error instead of guessing which pane is active.

```bash
window_count=$(tmux list-windows -t <session_name> -F '#{window_index}' | wc -l)
pane_count=$(tmux list-panes -a -F '#{session_name}' | awk '$1 == "<session_name>" {n++} END {print n + 0}')
test "$window_count" -eq 1
test "$pane_count" -eq 1
```

```bash
tmux new-session -d -s <session_name>
tmux send-keys -t <session_name> 'cd /fsx/analysis_results/ubuntu' Enter
tmux send-keys -t <session_name> 'day-clone -t <git_ref> -d <workset_code>' Enter
tmux send-keys -t <session_name> 'cd /fsx/analysis_results/ubuntu/<workset_code>/daylily-omics-analysis' Enter
```

Stage manifests exactly from the verified S3 locations:

```bash
tmux send-keys -t <session_name> 'mkdir -p ./config' Enter
tmux send-keys -t <session_name> 'aws s3 cp <samples_s3_uri> ./config/samples.tsv' Enter
tmux send-keys -t <session_name> 'aws s3 cp <units_s3_uri> ./config/units.tsv' Enter
```

When the user asks for only the first four lines of `units.tsv`, trim explicitly and verify:

```bash
tmux send-keys -t <session_name> "awk 'NR <= 4' ./config/units.tsv > ./config/units.tsv.tmp" Enter
tmux send-keys -t <session_name> 'mv ./config/units.tsv.tmp ./config/units.tsv' Enter
tmux send-keys -t <session_name> 'wc -l ./config/units.tsv' Enter
```

Initialize and launch interactively, one command per `tmux send-keys`. Do not combine `source dyoainit && dy-a ... && dy-r ...` into one shell line; `dy-a`/`dy-r` may be shell functions or aliases defined by `dyoainit` and may not resolve later in the same parsed command. Do not run `source dyoainit` under `set -u`; `dyoainit` may reference unset variables before assigning defaults.

```bash
tmux send-keys -t <session_name> 'source dyoainit' Enter
tmux send-keys -t <session_name> 'dy-a slurm <genome_build>' Enter
tmux send-keys -t <session_name> 'dy-r <targets> <snakemake_flags> &' Enter
```

### Verify launch before reporting success
Check the tmux pane, SLURM queue, and controller process. `squeue` must be on `PATH`; if it is not available, treat that as a failed status check.

```bash
tmux capture-pane -pt <session_name> -S -120
squeue -u ubuntu | head -80
ps -fu ubuntu | awk '/snakemake|dy-r|day_run/ && !/awk/ {print}' | head -40
```

Report the session name and attach command back to the user:

```bash
tmux attach -t <session_name>
```

### Worked examples
Hybrid ILMN+ONT `take1`:

```bash
tmux new-session -d -s take1_hiom_rerun_20260422
tmux send-keys -t take1_hiom_rerun_20260422 'cd /fsx/analysis_results/ubuntu' Enter
tmux send-keys -t take1_hiom_rerun_20260422 'day-clone -t main -d take1' Enter
tmux send-keys -t take1_hiom_rerun_20260422 'cd /fsx/analysis_results/ubuntu/take1/daylily-omics-analysis' Enter
tmux send-keys -t take1_hiom_rerun_20260422 'mkdir -p ./config' Enter
tmux send-keys -t take1_hiom_rerun_20260422 'aws s3 cp <verified_samples_s3_uri> ./config/samples.tsv' Enter
tmux send-keys -t take1_hiom_rerun_20260422 'aws s3 cp <verified_units_s3_uri> ./config/units.tsv' Enter
tmux send-keys -t take1_hiom_rerun_20260422 "awk 'NR <= 4' ./config/units.tsv > ./config/units.tsv.tmp" Enter
tmux send-keys -t take1_hiom_rerun_20260422 'mv ./config/units.tsv.tmp ./config/units.tsv' Enter
tmux send-keys -t take1_hiom_rerun_20260422 'source dyoainit' Enter
tmux send-keys -t take1_hiom_rerun_20260422 'dy-a slurm hg38_broad' Enter
tmux send-keys -t take1_hiom_rerun_20260422 'dy-r produce_snv_concordances produce_sentdhiom_sv produce_sentdhiom_vcf -p -j 100 -k &' Enter
```

Solo Ultima `agbt_ug`:

```bash
tmux new-session -d -s agbt_ug_ultima_rerun_20260422
tmux send-keys -t agbt_ug_ultima_rerun_20260422 'cd /fsx/analysis_results/ubuntu' Enter
tmux send-keys -t agbt_ug_ultima_rerun_20260422 'day-clone -t main -d agbt_ug' Enter
tmux send-keys -t agbt_ug_ultima_rerun_20260422 'cd /fsx/analysis_results/ubuntu/agbt_ug/daylily-omics-analysis' Enter
tmux send-keys -t agbt_ug_ultima_rerun_20260422 'mkdir -p ./config' Enter
tmux send-keys -t agbt_ug_ultima_rerun_20260422 'aws s3 cp <verified_samples_s3_uri> ./config/samples.tsv' Enter
tmux send-keys -t agbt_ug_ultima_rerun_20260422 'aws s3 cp <verified_units_s3_uri> ./config/units.tsv' Enter
tmux send-keys -t agbt_ug_ultima_rerun_20260422 "awk 'NR <= 4' ./config/units.tsv > ./config/units.tsv.tmp" Enter
tmux send-keys -t agbt_ug_ultima_rerun_20260422 'mv ./config/units.tsv.tmp ./config/units.tsv' Enter
tmux send-keys -t agbt_ug_ultima_rerun_20260422 'source dyoainit' Enter
tmux send-keys -t agbt_ug_ultima_rerun_20260422 'dy-a slurm hg38_broad' Enter
tmux send-keys -t agbt_ug_ultima_rerun_20260422 'dy-r produce_sentdug_vcf produce_alignstats produce_snv_concordances -p -j 20 -k -T 1 &' Enter
```

## Wrapper Script (not for agents unless explicitly approved)
Agents must use `dy-r` from an initialized persistent tmux pane. `bin/augment_setup_and_run_dayoa.bash` is historical/local helper documentation and is not an agent workflow execution path unless the user explicitly approves it in the current thread.

```bash
source bin/augment_setup_and_run_dayoa.bash <executor> <genome_build> "<targets>" "<snakemake_flags>" ["<dry_run_flag>"]
```

- **executor**: `local` or `slurm`
- **genome_build**: `hg38`, `hg38_broad`, or `b37`
- **targets**: Quoted space-separated Snakemake targets (e.g. `"produce_snv_concordances"`)
- **snakemake_flags**: Quoted flags (e.g. `"-p -j 10 -k -T 1"`)
- **dry_run_flag**: Optional 5th arg. Pass `"-n"` for dry-run; omit for real execution.

Examples:
```bash
# Dry-run
source bin/augment_setup_and_run_dayoa.bash slurm hg38_broad \
    "produce_snv_concordances" "-p -j 2 -k -T 1" "-n"

# Production run
source bin/augment_setup_and_run_dayoa.bash slurm hg38 \
    "produce_sentdhiom_vcf produce_snv_concordances" "-p -j 2 -k -T 1"
```

**Important**: This script must be `source`d (not executed) because `dyoainit` uses `return`. Use `bash bin/day_run` internally (not `source bin/day_run`) so that `exit` in day_run stays in a subprocess.

# Debugging From MAC
If given an AWS_PROFILE, region, cluster name, optional path to analysis, and potentially a tmux session analysis is running in, activate `DAY-EC` first. Use `pcluster describe-cluster -n <name> --region <region>` only for read-only cluster metadata such as instance ID, private IP, and public IP. Use SSM/daylily-ec for all headnode access.

## SSM Commands
**CRITICAL REQUIREMENTS**:
1. Use SSM/daylily-ec as the only supported access model for headnode commands and shells.
2. Always use login shells for remote commands that need the configured headnode environment. Use `bash -l -c 'your command here'` inside the SSM session or command invocation to ensure the full shell environment (including PATH and conda) is available.
3. **`squeue` must be on PATH** — if it is not available, the command must fail loudly with an error. Do NOT report zero exit code or silently skip SLURM status checks.
4. **Always use an interactive bash shell as the `ubuntu` user for headnode workflow work.** `dy-a`, `dy-r`, `dy-m`, and related `dy-*` commands are aliases from `dyoainit`, not standalone executables. Bash does not expand aliases in non-interactive scripts by default, and `bin/day_activate` also expects an initialized interactive shell/conda context. For workflow launches, use an interactive ubuntu tmux/login pane and send separate commands: `source dyoainit`, then `dy-a slurm <genome_build>`, then `dy-r ...`. Do not assume `dy-a` or `dy-r` will work inside an SSM `send-command` script.

## Terminal Heredoc Corruption
**CRITICAL RULE - DO NOT USE HEREDOC**:
- **NEVER use heredoc syntax** (`<< 'EOF'`, `<< 'EOFSCRIPT'`, etc.) in terminal commands. Heredoc ALWAYS corrupts the terminal with character doubling and scrambling.
- **ALWAYS use temporary scripts instead**: Write scripts to `/tmp/` using `save-file` tool or echo commands, then execute them.
- **Alternative approaches**:
  - Use `save-file` tool to create scripts (preferred)
  - Use multiple `echo` commands to build files line-by-line
  - Use Python to write files
  - Use `str-replace-editor` to create/edit files
- **If terminal becomes corrupted**: Kill the terminal with `kill-process` and start a fresh one.

# Log Locations for SLURM-based Workflows

When jobs are running via the SLURM profile in `/fsx/analysis_results/ubuntu/<workdir>/`, logs are split across three locations:

1. **Snakemake Master Log** (PRIMARY - read this first)
   - Location: `.snakemake/log/<most_recent_timestamp>`
   - Contains: Snakemake command output, rule execution order, and progress updates (e.g., "3 of 1556 steps (0.2%) done")
   - On failure: Includes failure messages (note: failures may not be terminal; Snakemake may retry based on configuration)

2. **SLURM Job Logs** (SECONDARY - per-job details)
   - Location: `logs/slurm/<taskname>/*.out` and `logs/slurm/<taskname>/*.err`
   - Named by SLURM job ID
   - Important: Job reruns create new log files; use file modification timestamps to find the latest logs
   - Reruns may have smaller job IDs than previous attempts

3. **Rule-Specific Logs** (TERTIARY - rule execution details)
   - Location: `.snakemake/log/` (Snakemake-managed) and `logs/slurm/` (SLURM-managed)
   - Contains: Output and errors from individual rule executions

4. **Command History Log**
   - Location: `day_cmd.log`
   - Contains: Record of all `dy-r` command invocations

**Debugging Strategy**: Start with the Snakemake master log to identify which rules failed, then check the corresponding SLURM logs by job ID and timestamp to see detailed error messages.

# Sentieon Info
Some can be found here: https://github.com/Sentieon/sentieon-models?tab=readme-ov-file

# Slurm Service Boundary

- Do not perform Slurm service, daemon, scheduler, partition, accounting, node-health, node drain/resume, or queue interventions unless the user first receives a specific proposal for that exact Slurm action and explicitly approves it in the current thread.
- In Dayhoff, DayOA, and DYEC work, Slurm is an expected infrastructure service, not an optimization target for the coding agent. Do not restart `slurmd`, repair nodes, modify Slurm config, alter partitions, drain/resume nodes, tune scheduling, or otherwise administer Slurm while running workflow tests.
- Jobs in Slurm `CF`/`CONFIGURING` can legitimately remain there while ParallelCluster creates spot instances from scratch; this can take tens of minutes. This is information for status reporting only, not a trigger for action or job management.
- Do not actively manage workflow jobs. Scheduling, retries, queue state, and job lifecycle are Snakemake/Slurm responsibilities. Do not cancel, requeue, hold, release, reprioritize, drain/resume, restart services for, or otherwise manipulate jobs or scheduler state unless the user explicitly approves that exact action in the current thread.
- Monitoring and reporting are allowed. Jobs running for more than 3 hours may be flagged as `needs investigation`, but do not take corrective action without confirmed user approval.
- If Slurm is unavailable or unhealthy, record the blocker and route the durable fix through ParallelCluster/pcluster configuration or infrastructure code changes.
