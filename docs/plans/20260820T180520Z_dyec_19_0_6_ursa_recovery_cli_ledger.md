# DYEC 19.0.6 Ursa Recovery CLI Ledger

Controlling request: implement the DYEC lane of the approved multi-agent plan by adding public, JSON-capable `dyec cluster compute-fleet` and `dyec slurm-accounting recover` contracts. After the coordinator-owned first live attempt exposed the retained cross-VPC topology, the lane also adds read-only `dyec slurm-accounting inspect` and explicit existing-bridge recovery. DYEC owns every underlying ParallelCluster call. This lane performs no live AWS mutation, production recovery, build, deployment, release tag, or package publication.

Cross-repo coordination: the parent coordinator owns the authoritative `daylily-ursa` ledger and the Ursa, Dayhoff, OWY, production, and release gates. This repo-local ledger records only the isolated DYEC source lane.

## Gate 0: Inventory Freeze

- Worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-19.0.6-ursa-recovery-20260820`
- Branch: `codex/dyec-19.0.6-ursa-recovery-20260820`
- Exact base: annotated tag `19.0.4`, tag object `1ef8312d67ec648603066174733dcfde7f18b266`, peeled commit `581d770f2a3c96311ff5ebe748c9df4e76c7ddf8`.
- Base verification: `git describe --tags --exact-match HEAD -> 19.0.4`; `git merge-base --is-ancestor 581d770... HEAD -> rc=0`; initial `git status --short --branch` showed a clean new branch.
- Reserved checkout boundary: canonical checkout `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` is dirty on `codex/dclu1904-slim-catalog-19.0.5`; it was inventoried read-only and is not edited, reset, staged, or used as this lane's worktree.
- Instructions read before implementation: `~/.codex/AGENTS.md`, `~/projects/AGENTS.md`, `~/projects/lsmc/AGENTS.md`, repo `AGENTS.md`, `~/.codex/docs/plan-ledger-workflow.md`, repo `README.md`, `docs/agent_cli_guide.md`, `docs/cli_reference.md`, `dyec --help`, `dyec agent guidance`, `dyec cluster --help`, `dyec slurm-accounting --help`, and `dyec slurm-accounting attach --help`.
- Source inventory: existing fleet primitives are `daylily_ec.pcluster.runner.describe_compute_fleet`, `update_compute_fleet`, `update_cluster`, and bounded waiters in `daylily_ec.pcluster.monitor`. Existing create-only accounting orchestration lives in `daylily_ec.workflow.postcreate_slurm_accounting`; existing attach preparation lives in `daylily_ec.workflow.attach_slurm_accounting`. The public CLI currently exposes only `slurm-accounting ensure` and `attach`; no public fleet mutation or crash-safe recovery command exists.
- Sweep commands: `rg -n "slurm-accounting|compute_fleet|update-compute-fleet|attach_slurm_accounting|postcreate_slurm" daylily_ec tests docs README.md`; `rg -n "active.*controller|squeue|controller_count" daylily_ec tests`; exact CLI help commands listed above.
- Baseline validation: `python -m pytest -q tests/test_postcreate_slurm_accounting.py tests/test_runner.py tests/test_cli_registry_v2.py -> 307 passed, 7 failed in 92.25s`. All 7 failures predate this lane at exact tag `19.0.4`: one stale `DAYOA_BLESSED_TAG` assertion and six stale headnode-configure contract assertions. Targeted post-create and runner tests were green.
- Assumptions and live limits: no AWS command, headnode operation, Slurm intervention, fleet transition, accounting stack mutation, or live recovery is authorized for this supporting lane. Local tests must mock all providers. The coordinator owns live proof and annotated release tagging after source handoff.

## Contract Decisions

- Fleet transition and recovery are registered public DYEC commands with `supports_json`, `mutates_state`, and `long_running` policy. Accounting inspection is JSON-capable, read-only, and non-long-running.
- Exact fleet request spellings are `STOP_REQUESTED` and `START_REQUESTED`; exact terminal wait spellings are `STOPPED` and `RUNNING`. A request/terminal mismatch fails before provider invocation.
- `cluster compute-fleet --drain` means wait for the bounded, read-only headnode controller/Slurm inventory to become authoritatively empty before a stop request. It never drains Slurm nodes, cancels jobs, signals controllers, or mutates scheduler state. Without `--drain`, a stop request still performs one authoritative idle proof and fails if work is active.
- Controller inventory/action identity recognizes the current supported `dy-r` and `dyec-controller-launch.sh` entrypoints only. The retired `dayoa-controller-launch.sh` spelling is not retained as a compatibility alias.
- Recovery requires the exact persisted cluster configuration path, a trimmed explicit AWS profile, resolved AWS account identity, exact regional provider/database/user, exact bridge-or-null, consumer VPC, and paired missing-accounting creation/cost acknowledgement flags. Direct mode requires provider and consumer VPC equality. Explicit bridge mode resolves only the named existing healthy bridge, validates its provider/consumer/database/instance/secret binding, and forbids provider or bridge creation/reconciliation. Exact mode never selects another stack or discovers a bridge fallback.
- Recovery writes an atomic `render_intent` receipt before rendering, binds both source and update hashes before fleet mutation, and writes `update_submission_intent` before the non-dry provider update. A reclaimed intent is polled for the 300-second provider-visibility window: a visible update is reclaimed, while persistent `CREATE_COMPLETE` fails closed and is never resubmitted.
- Recovery repeats its authoritative idle proof after exact service preparation, even for an already-stopped fleet, and blocks update/restart if work appeared. `UPDATE_IN_PROGRESS` and `UPDATE_COMPLETE` require the matching identity/phase receipt and both current file hashes. The exact singleton is re-resolved and deterministically re-rendered before fleet start; a terminal receipt is accepted only with provider `UPDATE_COMPLETE`.
- A closed provider-state/receipt-phase matrix rejects unknown phases, pre-submission phases paired with provider `UPDATE_*`, and post-update phases paired with `CREATE_COMPLETE` before any fleet or update mutation. Only submission intent/submission phases cross the provider visibility boundary.
- JSON payloads contain versioned schema names, stable phase/state values, non-secret identifiers/digests, and bounded evidence only. Raw provider stdout/stderr, database endpoints/passwords, secret ARNs, command lines, and exception text are excluded.

## Coordinator-Owned Live Feedback

- The first coordinator-owned live D2 attempt used candidate commit `327f8faa6187c19744f20677ffb885cdb602ad01` and failed closed before render/fleet/update with public diagnostic `stage=service_resolution`, `reason_code=exact_regional_stack_conflict`.
- The safe-diagnostic follow-up is pushed at `54cee0c65e3df01583e4c1133b68019d8e93279d`. No AWS call was made by this supporting lane.
- Coordinator evidence identified one retained canonical provider `dayec-slurm-accounting-us-west-2c` and existing exact bridge `dayec-sacct-pl-vpc-06b01782f2abece1c` for the `us-west-2d` consumer VPC. The failure therefore exposed a public exact-topology inspection and explicit-bridge contract gap, not a reason-code or alternate-stack-selection bug.

## Control Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-001 | DYEC | Freeze a clean 19.0.4-derived worktree without touching reserved 19.0.5 work | SUCCESS | legitimate_safety_handling | Gate 0 | DYEC agent | Gate 0 inventory above |  | Clean isolated branch and exact peeled base recorded. |
| DYEC-002 | Fleet CLI | Add idempotent public `dyec cluster compute-fleet` with bounded optional drain/idle proof and wait | SUCCESS | feature_implementation | Gate 1 | DYEC agent | `daylily_ec/workflow/compute_fleet.py`; focused stop/start/no-op/reclaim/drain tests; shared current launcher-identity tests |  | Exact state pairs, authoritative all-user idle proof, current `dyec-controller-launch.sh` recognition, no scheduler mutation, and no duplicate same-direction request are implemented. |
| DYEC-003 | Accounting CLI | Add crash-safe public `dyec slurm-accounting recover` covering CREATE_COMPLETE, STOPPED fleet, UPDATE_IN_PROGRESS, and verified UPDATE_COMPLETE | SUCCESS | feature_implementation | Gate 1 | DYEC agent | `daylily_ec/workflow/recover_slurm_accounting.py`; atomic write-ahead phase/identity receipt; deterministic config; recovery state-machine, phase-matrix, and crash-window tests |  | Recovery binds profile/account/config hashes/exact singleton identity, performs a fresh post-preparation idle gate, owns prepare/stop/update/wait/start and full `sacct` verification, and never resubmits an ambiguous reclaimed intent. |
| DYEC-004 | Registry/schema | Register fleet/recovery commands and emit versioned, bounded, non-secret JSON payloads | SUCCESS | active_product_contract | Gate 3 | DYEC agent | `dyec cluster compute-fleet --help`; `dyec slurm-accounting recover --help`; `tests/test_recovery_cli_contracts.py`; registry policy test |  | Success and callback-failure JSON use `dyec.cluster_compute_fleet.v1` and `dyec.slurm_accounting_recovery.v1`; both commands are JSON-capable, mutating, long-running policies. |
| DYEC-005 | Tests | Add lean focused tests for validation, ordering, idempotence, update reclaim, idle proof, restart, crash windows, exact target binding, and secret-safe output | SUCCESS | contract_test | Gate 5 | DYEC agent | `203 passed in 0.70s` across the directly affected suite; focused fleet/headnode/recovery safety subset `112 passed in 0.26s`; scoped new/safety-module Ruff and format checks, Python compile across all changed Python files, and `git diff --check` passed |  | Tests cover current launcher identity and stop blocking, fresh post-preparation idle proof for running/stopped fleets, impossible provider-state/receipt-phase rejection before mutation, pre-render interruption with/without a partial YAML, pre-submission intent ordering, 300-second ambiguous-intent no-resubmit behavior, profile/account and both file hashes, wrong stack/database/user, source mutation, terminal-receipt state, and exact verification before resumed fleet start. No live provider calls occurred. |
| DYEC-006 | Docs | Document exact syntax, state spellings, safety boundary, and output schemas | SUCCESS | historical_docs_only | Gate 5 | DYEC agent | `README.md`, `docs/agent_cli_guide.md`, `docs/cli_reference.md`, and `dyec --json agent guidance` |  | Docs require the installed `dyec` console script for upstream services and define both exact argv/schema contracts. |
| DYEC-007 | Live proof | Recover `ursa-m-rgx-hx01` and prove accounting/fleet/sacct live | BLOCKED | feature_implementation | Live coordinator gate | coordinator | Supporting-agent assignment explicitly prohibits AWS/production mutation | Production authority intentionally retained by coordinator | Coordinator must run the released CLI after reviewing this source handoff. |
| DYEC-008 | Release | Create/push annotated `19.0.6` tag or fix forward | BLOCKED | config_or_startup_contract | Release coordinator gate | coordinator | Supporting-agent assignment explicitly prohibits tagging/publication | Release promotion depends on coordinator-owned live proof | Coordinator owns tag and any fix-forward version after live gates. |
| DYEC-009 | Git handoff | Commit and push the isolated `codex/` branch | OPEN | feature_implementation | Gate 5 | DYEC agent | Initial candidate `327f8faa6187c19744f20677ffb885cdb602ad01` and diagnostic delta `54cee0c65e3df01583e4c1133b68019d8e93279d` are pushed; exact-topology corrective delta awaits review/commit |  | Current source commit remains coordinator-gated. |
| DYEC-010 | Exact topology | Add read-only bounded provider/bridge inspection and bind an explicit existing bridge into recovery receipts | IN_PROGRESS | active_product_contract | D2 corrective gate | DYEC agent | `368 passed in 3.49s` affected suite; `115 passed, 135 deselected in 4.97s` registry/help selection; scoped Ruff, new-file Ruff format, Python compile, and `git diff --check` pass | Retained regional provider name and cross-VPC bridge cannot be represented by the direct-only first candidate | Source/tests/docs are locally frozen; independent review remains. |

## Final Report

All rows terminal: no (git handoff remains open)

Objective complete: no

Status counts:
- SUCCESS: 6
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 2
- IN_PROGRESS: 1
- OPEN: 1

Live actions performed: none.
