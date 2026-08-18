# Agent quick start

**Before a DYEC or DayOA operation, read
[docs/agent_cli_guide.md](docs/agent_cli_guide.md).** It is the visible CLI
route map for local setup, cluster/headnode inspection, run mounts, catalog
launch, interactive DayOA work, monitoring, no-delete export, and terminal
stop conditions. In an activated checkout, run `dyec agent guidance` for the
compact companion reminder.

The detailed rules below are mandatory. When guidance conflicts, follow the
current instruction hierarchy and the closest applicable safety contract; do not
invent a fallback or bypass the supported DYEC/DAYOA CLI path.

# Shell Session Defaults

- Default to an interactive shell for shell work. On this Mac, use the user's default shell unless the user explicitly asks for another shell.
- For AWS EC2, ParallelCluster, and other remote Linux hosts, default to an interactive `bash` login shell as `ubuntu`. Do not use `root` unless the user explicitly grants permission for that specific work; use targeted `sudo` from `ubuntu` when escalation is required.
- For Daylily/DayOA/DAY-EC headnode workflow work, use an interactive `ubuntu` tmux/login-shell pane for controllers and workflow commands. Run setup as separate commands in that pane (`source dyoainit`, then `dy-a ...`, then `dy-r ...`) so aliases/functions are defined before use.
- SSM Run Command is for simple inspection or for writing helper scripts through the supported helpers. Do not launch workflow controllers or rely on `dy-*` aliases from non-interactive SSM scripts.
- Budget-cap increases require double approval before an agent changes AWS Budgets, DYEC cost-center caps, or equivalent controls: treat the request as the first approval, restate the exact budget or cost center and old/new caps, then wait for a second explicit approval. Exception: an increase submitted through the Ursa GUI by an authenticated human user does not require an additional agent-side approval; retain and verify the authenticated audit evidence.
- Before any DayOA workflow work, read `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`. Never invoke `snakemake` directly for DayOA work. Always use `dy-r` inside a persistent, meaningfully named `tmux` session running an interactive bash login shell as `ubuntu`; `dy-r` passes all targets and flags through to Snakemake for you.

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
- Store every analysis-specific YAML/config file inside that analysis's cloned
  `daylily-omics-analysis` directory, normally under `config/`, and make the
  saved controller command reference that in-clone path. Never use a
  controller-specific config path outside the clone. The clone must preserve
  all manifests and configuration required to rerun the exact analysis,
  excluding only explicit links/paths to source reads, CRAMs, references,
  licenses, and other declared runtime assets.

# Pinned DayOA Source Immutability

- A DYEC controller must never create, edit, delete, move, chmod, or patch a versioned file in a pinned DayOA checkout. This includes workflow rules, scripts, versioned environment YAMLs, `bin/`, and versioned configuration.
- Runtime source overlays, generated source helpers, and text-rewrite repairs are prohibited. The controller must verify that the selected DayOA ref is clean before dispatch and again after the workflow returns.
- Explicit input manifests and analysis-specific runtime config may be
  materialized only at their established in-clone runtime paths; they are not
  a mechanism for altering versioned DayOA source. Pinned-source checks must
  distinguish these analysis artifacts from source modifications.
- If a required behavior is absent from the selected release, fail clearly and land it in a new, tested, tagged DayOA release. Never repair it on the headnode.
- The sole exception is an explicit **pinned-source test override** for one named existing analysis root. A human must authorize that root, source ref/commit, intended source change, and test command in the current thread. The controller itself still does not patch, reset, or check out source; the override permits an already-made, explicitly authorized dirty change to be exercised only after verifying its existing HEAD.
- Use only `dyec workflow launch --pinned-source-test-override "<non-secret reason>"` with `--reuse-existing-analysis-dir --reuse-local-git-ref --reuse-local-git-commit <40-char-sha> --input-contract none --no-input-staging --dry-run --export-trigger none`. The controller records the selected ref, status, staged/working-tree diffs, untracked paths, reason, and command before and after the test outside the DayOA checkout.
- A pinned-source test override is never valid for a live run, catalog launch, automatic/manual export, delivery, cleanup, or promotion. It cannot replace a source release: make the permanent correction in DayOA, validate it under the approved gate, and publish a tagged release before any production use.

# Provider-Neutral Execution Boundary

- DYEC is a standalone cluster/workflow CLI. It must not require, import,
  authenticate to, query, or create records in Dayhoff, Ursa, Bloom, TapDB, or
  any metadata/identity service.
- Upstream systems and human operators invoke the same public DYEC commands.
  DYEC consumes explicit local manifests and receipts; it does not discover or
  resolve identities through a service URL, token, SDK, or network request.
- Keep identity validation, planning, application, status, and evidence
  provider-neutral and file-based. Missing supplied identity evidence fails
  locally when a requested operation requires it.
- Do not add service-specific launch defaults, artifact names, URLs, tokens,
  registration calls, or fallback discovery to new DYEC interfaces.
- Ordinary DayOA/HIOMRS execution must work with no EUIDs and no identity
  service. Customer-release preparation may require owner-issued identifiers,
  but they must already be present in the supplied manifests and receipts.

# Analysis-Root Agent Locking

- Before touching `/fsx/analysis_results/**`, record a visit with `dyec analysis visit --analysis-root <root> --mode <read|export|write|unlock|delete|kill> --intent "<reason>"`.
- Read/search/monitor/log review and no-delete S3 export do not require write-lock ownership, but they must leave visit logs under `<analysis_root>/.dayoa_agent/visits/` and `/fsx/analysis_results/.dayoa_agent_visits/`.
- Live workflow writes, `dy-r --unlock`, file edits/touches/moves in the analysis root, local FSx deletes, job kill/cancel, DRA detach tied to that root, and cluster/resource teardown tied to that root require the current agent to own `<analysis_root>/.dayoa_agent/write.lock/`.
- Acquire with `dyec analysis lock acquire --analysis-root <root> --operation write --intent "<reason>"`; release with `dyec analysis lock release --analysis-root <root>`.
- Use `dyec analysis guard --analysis-root <root> --operation <write|unlock|delete|kill> -- <command...>` for protected shell actions such as `scancel`, local deletes, and recovery commands.
- Do not take over another owner silently. Use `dyec analysis lock takeover --request`, show the exact owner/path/action to the user, and proceed only after explicit double approval with the printed token.
- Set a stable `DAYOA_AGENT_ID`, `DAYOA_AGENT_KIND`, `DAYOA_HUMAN_REQUESTOR`, `DAYOA_TMUX_SESSION`, and `DAYOA_LEDGER_PATH` before long-lived headnode work.
- Full command reference: `docs/analysis_root_agent_locking.md`.

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

# Long-Running Rule Monitoring

- When monitoring long-running DayOA/Slurm rules, compute-node Glances spot checks are appropriate read-only evidence alongside `squeue`, controller logs, rule logs, and benchmark TSVs.
- From the headnode, use bounded, non-interactive checks only against nodes currently allocated to the workflow. Prefer `glances --stdout` with an explicit timeout and capture CPU, load, memory, swap, filesystem usage, disk I/O, network I/O, and process count together with node name, Slurm job/rule, and elapsed runtime.
- Treat each Glances sample as a point-in-time observation, not proof that a job is healthy, stuck, or correctly sized. Compare it with rule benchmarks and repeated snapshots before recommending resource changes.
- If Glances is missing or a compute node cannot be reached, report that explicitly. Do not install packages, restart services, alter jobs, or administer nodes merely to obtain monitoring data.
- Glances evidence does not authorize Slurm or node intervention; existing approval boundaries for cancel, requeue, drain, resume, restart, and configuration changes still apply.

# Safety Preferences

## Scheduled tasks and automations

- Scheduled tasks, recurring automations, monitors, reminders, and thread heartbeats are not implicitly authorized by filesystem, AWS, browser, or “Full Access” permissions. Ask for the user's explicit permission before creating one.
- Do not schedule a task more frequently than every five minutes unless the user gives explicit double approval: first approve the exact task, cadence, and expected duration; then separately confirm that the sub-five-minute cadence is intended.
- Track each scheduled task's start time and expected stop condition. When any scheduled task has run for more than six hours, flag it as potentially runaway and ask the user whether it should continue, be paused, stopped, or deleted. Do not silently extend, recreate, or intensify it.

- Do not execute destructive AWS resource changes unless the user gives a second explicit approval after being told the action is destructive.
- Do not answer interactive confirmation prompts for destructive AWS changes unless that second explicit approval has already been given in the current thread.
- Treat an initial request to "teardown", "destroy", "delete", or similar as permission to inspect, prepare, or dry-run only. Before any live destructive action, restate the exact effect and wait for a separate explicit confirmation.
- Always read `.md` and other instruction files in `~/.agents/*`, `~/.codex/*`, `./.agents`, `./.codex`, `./AGENTS.md`, and `./CLAUDE.md`.
- Fallback behavior is an antipattern that wastes time and money in this workspace. Unless the user explicitly approves a specific fallback in the current thread, do not add, preserve, or rely on fallback behavior, compatibility shims, legacy aliases, inferred defaults, generated alternate paths, or service-side discovery. Missing config, missing files, missing deployment identity, missing credentials, malformed commands, or unexpected runtime state must fail hard with a clear error.
- Never invent production TapDB/Meridian EUIDs. Artificial or fixture EUIDs
  that intentionally exercise Meridian-shaped identity fields must use the
  reserved `Z-` prefix. `Z-` values are test-only and must never be persisted,
  registered, treated as owner-issued, or accepted for customer release.

# Headnode SSM Access

- All SSM interactive sessions and command payloads that interact with headnodes must run as `ubuntu` in a bash login shell.
- Do not use `root` for headnode work. The `ubuntu` user is in sudoers; use targeted `sudo` from `ubuntu` only when escalation is required.
- Interactive sessions must use `SSM-SessionManagerRunShell` configured with `runAsDefaultUser=ubuntu` and bash login-shell behavior.
- Command payloads must go through the central `daylily_ec.aws.ssm.run_shell` and `daylily_ec.aws.ssm.write_remote_text` helpers rather than ad hoc `aws ssm send-command` calls.
- Use `dyec` for current docs and runbooks. The headnode signature is `dyec headnode connect --profile <profile> --region <region> --cluster <cluster>` and `dyec headnode configure --profile <profile> --region <region> --cluster <cluster>`. Prefer `--cluster`; keep `--cluster-name` for tools such as `pcluster` that require it.
- `dyec headnode connect` must preserve interactive TUI/editor key chords, especially Emacs `Ctrl-S` and `Ctrl-X Ctrl-S`. Keep both layers of XON/XOFF protection: the remote ubuntu login shell must disable flow control, and the local `daylily_ec.aws.ssm.start_session` path must keep a local `/dev/tty` flow-control guard running while Session Manager owns the terminal. A one-time local `stty -ixon -ixoff` is not sufficient because the AWS Session Manager/plugin startup path can leave the live local TTY with flow control enabled again.
- Do not remove or bypass the `tests/test_ssm.py` guardrail coverage for the local flow-control guard. Regression evidence should include a real `dyec headnode connect` session where `cat -v` receives bare `Ctrl-S` as `^S`; for editor validation, `emacs -Q` should enter `I-search` on `Ctrl-S` and write the file on `Ctrl-X Ctrl-S`.

# Local Environment

- Use the repo activation flow before running Daylily commands: `cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster && source ./activate`. If the `DAY-EC` Conda environment is not present or dependencies are missing, run `source ./activate` from the repo root to create/activate it, then use the `DAY-EC` environment for tests and CLI commands.

# Workflow Environment YAML Versioning

- Treat checked-in DayOA `workflow/envs/*.yaml` files as immutable versioned contracts. Never modify an existing versioned environment YAML in place.
- For any environment change, create a new incremented YAML filename, update the explicit DayOA rule/configuration reference and tests, then commit and push that new version.
- Preserve old YAML contents exactly for reproducibility of historical analysis roots and releases.

# Plan Ledger Workflow

- For multi-step, cross-repo, long-running, risky, or explicitly plan-driven work, use `/Users/jmajor/.codex/docs/plan-ledger-workflow.md` as the default execution SOP.
- Treat the controlling plan or plan ledger as the source of truth for tracked execution: record Gate 0 inventory/baseline first, track rows to terminal states, preserve evidence, and report whether all rows are terminal and whether the objective is actually complete.
- Do not use the ledger workflow for tiny single-change tasks unless the user asks for it.
- Every repo should have a `docs/plans/` directory. Create it when it is missing.
- Store plans, ledger plans, execution ledgers, and AI working documents used to carry out repo work under `docs/plans/`.
- Treat these files as durable repo artifacts: check them in and preserve them with the repo unless the user explicitly asks to remove or archive one.
- Name plan and ledger files with a datetime in the filename, such as `YYYYMMDDTHHMMSSZ_<short_slug>_ledger.md` or `YYYYMMDD_<short_slug>.md`.
- Do not keep the authoritative plan or execution ledger only in chat, temporary directories, or agent-local scratch space.

# ParallelCluster CLI

- `pcluster` is not an `aws` CLI subcommand. Do not pass AWS CLI-only flags such as `--json` to `pcluster`; ParallelCluster commands emit JSON by default.

# DYEC Run Mounts

- Do not treat FSx/DYEC run-mount creation as timed out before at least 40 minutes. Dynamic FSx data repository associations can legitimately stay in `CREATING` for around 40 minutes, especially large Illumina run directories.
- When running `dyec mounts create --wait` or equivalent run-mount operations, set an explicit timeout comfortably above 40 minutes when the CLI supports it, and continue read-only lifecycle polling rather than retrying, duplicating, deleting, or declaring failure at the default short timeout.

# Runtime Cache Export Boundary

- Never upload, publish, relay, promote, or copy Conda environment trees,
  adjacent environment YAMLs, container images, Apptainer/Singularity caches,
  Nextflow caches, or other runtime-cache directories with `aws s3 cp`,
  `aws s3 sync`, `aws s3 mv`, SDK object-copy loops, or another object-by-object
  S3 transfer. This prohibition applies to cache sources under
  `/fsx/resources/environments/**`, `/fsx/work/**`, and
  `/fsx/references/runtime_assets/cached_envs/**`.
- `--no-follow-symlinks` is not a valid cache-preserving alternative: it skips
  links instead of preserving their type and target. Do not use it as a
  fallback.
- The supported save path is `dyec runtime-cache export`. It inventories only
  complete real cluster-generation entries, rejects active builders and
  incomplete cache state, stages with `cp -a` into one fresh dedicated
  `/fsx/analysis_results/<executing-entity>/<cache-export-id>/` root, and then
  uses DYEC's FSx DRA attach, `EXPORT_TO_REPOSITORY`, and safe-detach workflow.
- The staging root and destination S3 prefix must not overlap any active DRA,
  and the destination prefix must be empty. If the intended canonical bucket
  is already mapped by a whole-bucket reference DRA, use an explicit separate
  non-overlapping cache-export destination; do not detach the reference DRA or
  fall back to S3 copying.
- Preserve the staged FSx root and receipts until the DRA task is `SUCCEEDED`
  and future-cluster import/linkage has been verified. Cleanup or replacement
  is a separate destructive operation and approval boundary.

# Version Tags

- Use non-v semver tags for package releases, e.g. `2.0.19` or `5.0.21`, not `v2.0.19`.
- Commit first, then tag the exact clean release commit.
- Use annotated tags for release provenance: `git tag -a 2.0.19 -m "Release 2.0.19"`.
- Lightweight tags are acceptable only for scratch/internal marks, not package releases.
- Do not move or overwrite pushed version tags. If a pushed tag is wrong, cut the next patch version.
- If signing is configured and expected, use signed annotated tags: `git tag -s 2.0.19 -m "Release 2.0.19"`.
- Verify tag type with `git cat-file -t 2.0.18`; `tag` means annotated and `commit` means lightweight.

# Slurm Service Boundary

- Do not perform Slurm service, daemon, scheduler, partition, accounting, node-health, node drain/resume, or queue interventions unless the user first receives a specific proposal for that exact Slurm action and explicitly approves it in the current thread.
- In Dayhoff, DayOA, and DYEC work, Slurm is an expected infrastructure service, not an optimization target for the coding agent. Do not restart `slurmd`, repair nodes, modify Slurm config, alter partitions, drain/resume nodes, tune scheduling, or otherwise administer Slurm while running workflow tests.
- Jobs in Slurm `CF`/`CONFIGURING` can legitimately remain there while ParallelCluster creates spot instances from scratch; this can take tens of minutes. This is information for status reporting only, not a trigger for action or job management.
- Do not actively manage workflow jobs. Scheduling, retries, queue state, and job lifecycle are Snakemake/Slurm responsibilities. Do not cancel, requeue, hold, release, reprioritize, drain/resume, restart services for, or otherwise manipulate jobs or scheduler state unless the user explicitly approves that exact action in the current thread.
- Monitoring and reporting are allowed. Jobs running for more than 3 hours may be flagged as `needs investigation`, but do not take corrective action without confirmed user approval.
- If Slurm is unavailable or unhealthy, record the blocker and route the durable fix through ParallelCluster/pcluster configuration or infrastructure code changes.

# Brainstorming and Advice Disposition

For any topic, default to:

- Map possibility first.
- Separate evidence from norms.
- Separate legality/safety from truth.
- Separate recommendation from capability.
- Keep weird/radical/nonstandard frames alive unless they are actually incoherent or harmful.
- Do not make the user drag the conversation out of the dull center every time.
