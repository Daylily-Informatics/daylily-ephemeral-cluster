# DYEC Workflow Observability Ledger

Controlling request: strengthen `dyec workflow status` and add the exact
Snakemake stream to `dyec workflow logs` for launched and explicitly identified
manual/recovery workflows.

Ledger path: `docs/plans/20260810T073000Z_dyec_workflow_observability_ledger.md`

## Gate 0 baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `codex/pin-dayoa-13.4.10-16.1.45`, tracking the same origin branch.
- Existing worktree state: many unrelated untracked plans, reports, backups,
  recordings, temporary files, and `TrusSV/`; this work will not modify them.
- Owned implementation surfaces at baseline:
  `daylily_ec/cli.py`, a new focused workflow-observability module, focused
  tests, README/operator docs, and this ledger.
- Source sweep:
  `rg -n 'workflow status|workflow logs|status.json|snakemake' README.md docs daylily_ec tests`.
- Baseline behavior: `workflow status` only returned `status.json`; `workflow
  logs` supported `tmux` and `controller` only.
- Baseline test:
  `source ./activate && python -m pytest tests/test_cli_registry_v2.py -q -k 'workflow_status or workflow_logs'`
  -> `2 passed, 217 deselected`.
- Live-system limit: implementation and validation are local with mocked SSM,
  process, and Slurm evidence. No active workflow, Slurm job, AWS resource,
  analysis output, or runtime-cache process is touched.
- Interface decision: standard DYEC launches use exactly one of `--session` or
  `--run-dir`. Manual/recovery inspection requires explicit `--repo-path` and
  `--controller-pid`; optional `--snakemake-log` supplies an exact log when live
  descriptor correlation cannot. No newest-log or service discovery fallback.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| OBS-001 | status | Derive RUNNING, SUCCEEDED, FAILED, or UNKNOWN from invocation-attributed evidence | SUCCESS | feature_implementation | Gate 1 | workflow_observability | `daylily_ec/workflow_observability.py::derive_state`; launched/manual state tests |  | State does not consume inspection RC or queue emptiness. |
| OBS-002 | controller | Report exact controller PID/liveness and reject stale or mismatched attribution | SUCCESS | feature_implementation | Gate 1 | workflow_observability | Exact controller target or explicit PID, cwd/command/tmux checks; stale receipt and persistent-shell tests |  | PID existence and invocation attribution are reported separately. |
| OBS-003 | Snakemake log | Correlate active log through controller/descendant open descriptors; support explicit exact manual log and reject missing/ambiguous evidence | SUCCESS | feature_implementation | Gate 1 | workflow_observability | `_open_snakemake_logs`; exact path validator; ambiguity tests; launcher persists exact pre/post file-set difference |  | No newest-file selection exists. |
| OBS-004 | progress/jobs | Report last progress, submitted/finished details, and current Slurm states without treating queue emptiness as success | SUCCESS | feature_implementation | Gate 1 | workflow_observability | Parser and Slurm tests cover two submissions, one completion, CONFIGURING and RUNNING |  | Empty/unavailable scheduler evidence does not terminalize the workflow. |
| OBS-005 | failures/RC | Detect only high-signal terminal failures and attribute terminal RC only to the current launched receipt | SUCCESS | legitimate_safety_handling | Gate 4 | workflow_observability | Generic ERROR/stale RC negative tests; anchored rule/workflow failure tests; matching receipt validation |  | Manual status never invents a terminal RC or success. |
| OBS-006 | logs CLI | Add `--stream snakemake` with launched and manual explicit syntax | SUCCESS | feature_implementation | Gate 1 | workflow_observability | `daylily_ec/cli.py`; attributed-tail and ambiguity CLI tests; live `--help` checks |  | Existing tmux/controller streams remain supported. |
| OBS-007 | tests | Cover launched/manual modes, states, active exact log, stale markers, Slurm CF/R, failure markers, ERROR false positives, ambiguity, and CLI help | SUCCESS | contract_test | Gate 5 | workflow_observability | `283 passed` across CLI registry, script entrypoints, and observability tests |  | Requested contracts have focused positive and negative coverage. |
| OBS-008 | docs | Update README, CLI reference, operations, quick start, and monitoring guide | SUCCESS | feature_implementation | Gate 5 | workflow_observability | README plus four requested operator/CLI documents updated |  | Commands, fields, semantics, and manual limitations documented. |
| OBS-009 | acceptance | Run focused tests and diff checks; terminalize every row | SUCCESS | contract_test | Gate 5 | workflow_observability | After both live-discovered bugfixes: `283 passed`; Ruff, mypy, py_compile, CLI help, and `git diff --check` pass |  | All rows terminal after local and live read-only proof. |
| OBS-010 | live-proof amendment | Correct the local-CLI/new-headnode-version boundary exposed by read-only prod-cand validation | SUCCESS | plan_amendment | Gate 5 | workflow_observability | Failed SSM IDs `81ec9fd6-3465-4941-a0ab-0f485effc88f` and `4778d271-66df-460d-9ef1-5978938982c7`; `find_spec(...) -> None`; exact rerun then reported RUNNING PID 564368, exact log `2026-08-10T072121.547201.snakemake.log`, Slurm job 82 RUNNING, and log tail succeeded |  | Replaced remote module import with compressed self-contained probe; added transport regression and structured SSM diagnostics. |
| OBS-011 | live-tail amendment | Return exact Snakemake tail content within the attributed observability probe | SUCCESS | plan_amendment | Gate 5 | workflow_observability | Isolated exact tail read returned content, while the former two-SSM command repeatedly reached the caller's roughly 30-second process boundary before emitting; the repaired exact `--lines 120` command returned content through `12 of 195 steps (6%) done` in one SSM call | Attribution and log reading were separate serial remote calls, so no bytes were emitted until the second call completed. | Tail is zlib/base64 transported with byte-count and SHA-256 verification; oversized tails fail clearly rather than truncate. |

## Decisions

- Standard launched mode reads the exact `status.json` and
  `controller_target.json` selected by `--session` or `--run-dir`.
- Manual mode is deliberately explicit: `--repo-path` and `--controller-pid`
  are required together. `--session` adds tmux process-tree correlation.
- The active master log is accepted only from exactly one controller/descendant
  open file descriptor. `--snakemake-log` is an explicit manual input; it is
  rejected when a live PID does not belong to the requested invocation.
- New launched controllers persist the exact terminal log by comparing the
  invocation's pre-run and post-run Snakemake log file sets. Zero or multiple
  new logs remain unavailable/ambiguous rather than selecting by mtime.
- A terminal RC comes only from the exact matching launched status receipt.
  Anchored Snakemake failures may establish `FAILED` without inventing an RC;
  manual success remains `UNKNOWN` without a receipt.
- The local CLI transports a compressed self-contained Python probe. It does
  not require the headnode's already-installed DYEC package to contain the same
  new module. SSM probe failures now expose command ID, RC, stdout, and stderr.
- Snakemake log streaming attributes and reads the exact tail in that same
  probe. The tail is compressed for bounded SSM output and validated by byte
  count and SHA-256 locally; the CLI does not perform a second remote read.

## Final report

All rows terminal: **yes**

Objective complete: **yes, including live read-only manual-recovery proof**

Status counts:

- SUCCESS: 11
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

Validation:

- `python -m pytest tests/test_cli_registry_v2.py tests/test_script_entrypoints.py tests/test_workflow_observability.py -q` -> `283 passed`.
- `ruff check daylily_ec/workflow_observability.py tests/test_workflow_observability.py --ignore UP045` -> pass.
- `ruff check daylily_ec/cli.py daylily_ec/scripts/daylily_run_omics_analysis_headnode.py tests/test_cli_registry_v2.py tests/test_script_entrypoints.py --select E9,F` -> pass.
- `mypy daylily_ec/workflow_observability.py --ignore-missing-imports` -> success; mypy also warns that its current runtime no longer supports the repo's configured Python 3.9 target.
- `python -m py_compile ...`, both workflow command `--help` checks, and
  `git diff --check` -> pass.

Live actions performed: read-only validation only. No cluster, workflow, Slurm,
analysis-root, AWS, or cache-promotion state was changed. The exact prod-cand
status reported `RUNNING`, attributed PID `564368`, one exact open master log,
12 submitted events, 12 finished events, and Slurm job `82` in `RUNNING`; the
exact Snakemake tail command then returned the requested log lines.
The second live acceptance reran the exact manual/recovery command with
`--lines 120`; it returned the attributed log body and final progress line
`12 of 195 steps (6%) done` through the single-probe transport.

Residual risk: launched-mode terminal persistence is covered by generated
launcher syntax/contract tests; this live recovery run proves manual-mode
`/proc`, tmux, active-log, and Slurm behavior but has no DYEC `status.json` by
design.
