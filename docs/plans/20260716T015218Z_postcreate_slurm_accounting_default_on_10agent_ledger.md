# DYEC post-create Slurm accounting, default-on — 10-agent control ledger

Created: `2026-07-16T01:52:18Z`

Controlling request: implement post-create Slurm accounting for `dyec create`,
release it as the next patch after `10.3.17`, and prove the exact released tag
with one fresh cluster.

Ledger path:
`docs/plans/20260716T015218Z_postcreate_slurm_accounting_default_on_10agent_ledger.md`

## Objective

`dyec create` must always build and persist a usable base ParallelCluster with
Slurm accounting absent from the initial configuration. After cluster
creation, headnode configuration, heartbeat, and base-state persistence, the
command optionally performs a supported stopped-fleet ParallelCluster update
to attach the one compatible regional accounting service. Accounting is on by
default, but accounting-stage failures fail soft unless strict mode is
requested; the successfully created cluster is retained.

The implementation target is release `10.3.18`. If that tag becomes occupied
before release, Agent 10 must record a plan amendment and use the next unused
patch without moving any existing tag.

## Public CLI contract

```text
dyec create \
  --slurm-accounting on|off \
  [--fail-on-sacct-error] \
  [--create-slurm-accounting-if-missing] \
  [--acknowledge-slurm-accounting-create-cost]
```

- `--slurm-accounting` defaults to lowercase `on`; any value other than exact
  lowercase `on|off` is rejected before AWS work.
- `--fail-on-sacct-error` defaults false. An accounting-stage failure exits
  `0` normally and uses the existing AWS failure code `2` in strict mode.
- With accounting `off`, `--fail-on-sacct-error` remains accepted and is
  ignored.
- The two accounting-service creation approval flags are a pair. Supplying
  exactly one is a validation error before AWS work. Supplying both is the
  stable non-interactive Ursa integration contract after authenticated GUI
  approval.
- With neither approval flag, an interactive terminal asks two confirmations,
  both defaulting No. Non-interactive execution never prompts.
- If any regional accounting stack exists but is incompatible with the
  cluster VPC, DYEC warns, leaves accounting disabled, and never creates a
  duplicate service.
- Existing standalone `dyec slurm-accounting ensure` and
  `dyec slurm-accounting attach` commands remain supported.

## Gates

| Gate | Completion condition |
|---|---|
| Gate 0: Inventory Freeze | Remote/tag identity, clean implementation worktree, preserved dirty checkout, baseline tests, sweeps, assumptions, and safety limits are recorded before product edits. |
| Gate 1: CLI And Initial Config Contract | Four CLI options validate/forward the normalized contract; the six legacy create-config accounting fields are absent from prompts, required keys, templates, and generated next-run config. |
| Gate 2: Accounting Preparation | Compatible service discovery, duplicate warning/selection, double-approved first-singleton creation, and candidate update YAML rendering finish before any fleet mutation. |
| Gate 3: Supported Fleet Update Lifecycle | Bounded fleet/update waiters and the create-only stop, attach, update, restore, readiness, verification, and recovery state machine meet the ordering/recovery contract. |
| Gate 4: State, Redaction, Tests, And Docs | Non-secret receipts and final status panels are complete; regression/integration coverage and operator documentation prove behavior and redaction. |
| Gate 5: Release And Exact-Tag Proof | Full verification is green; change is normally merged to `main`; an unused annotated non-v patch tag is pushed; one fresh exact-tag cluster proves base-create isolation and post-create accounting behavior; proof evidence is merged. |

## Gate 0 inventory and baseline

### Authoritative implementation checkout

- Worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-postcreate-sacct-10318`
- Branch: `codex/postcreate-sacct-default-on-10318`
- Starting `HEAD`: `d1e2ee405cc3b2d7121ce3c14eaaf913a31b37a6`
- Upstream: `origin/main`
- `git status --short --branch` at freeze:
  `## codex/postcreate-sacct-default-on-10318...origin/main` (clean)
- `git ls-remote origin refs/heads/main` at freeze:
  `d1e2ee405cc3b2d7121ce3c14eaaf913a31b37a6`
- The starting commit is the merge commit
  `Merge pull request #18 from lsmc-bio/codex/fsx-create-selection-contract`.

### Release identity

- Starting release: `10.3.17`.
- `git cat-file -t 10.3.17` returned `tag`, proving an annotated tag.
- `git cat-file -p 10.3.17` records tag object
  `f9b61f1fadc8e948a7c6003bf39db84389da108b` targeting commit
  `d1e2ee405cc3b2d7121ce3c14eaaf913a31b37a6`, message
  `Release 10.3.17`.
- `git ls-remote origin refs/tags/10.3.17 refs/tags/10.3.17^{}`
  returned the same annotated tag object and peeled commit.
- Target `10.3.18` was absent both locally and from
  `git ls-remote origin refs/tags/10.3.18 refs/tags/10.3.18^{}` at Gate 0.
  Agent 10 must repeat this check immediately before tagging.

### Preserved dirty checkout

The existing checkout is explicitly outside the implementation write scope:

- Path:
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-sentieon-single`
- Branch: `sentieon-single`, 20 commits behind `origin/sentieon-single` at the
  freeze.
- `HEAD`: `80a32383370d79e9a3913495835b9436eb765955`
- Inventory: two modified tracked ledgers and eleven top-level untracked status
  entries. The untracked campaign-artifacts directory contains additional
  files represented by its one porcelain entry.
- Modified tracked files:
  - `docs/plans/20260713T083000Z_sent_hg003_hiomrs_kitchensink_1x_monitor_ledger.md`
  - `docs/plans/20260713T220811Z_cpu_only_slurm_native_final_multiqc_ledger.md`
- Untracked entries:
  - `docs/plans/20260712T192000Z_sent_hg003_runtime_cache_publish.py`
  - `docs/plans/20260713T125855Z_bjuice_prevalidation_hiomrs_1038_campaign_artifacts/`
  - `docs/plans/20260713T125855Z_bjuice_prevalidation_hiomrs_1038_campaign_ledger.md`
  - `docs/plans/20260714T054454Z_render_cpu_only_live_cluster_config.py`
  - `docs/plans/20260714T101034Z_bjuice_hg001_007_hiomrs_1101_ledger.md`
  - `docs/plans/20260714T142143Z_bjuice_hg002_then_hg004_hiomrs_1102_ledger.md`
  - `docs/plans/20260714T143121Z_delete_usw2d_slurm_accounting.py`
  - `docs/plans/20260714T143121Z_inspect_usw2d_slurm_accounting.py`
  - `docs/plans/20260714T143121Z_usw2d_slurm_accounting_deletion_preflight_ledger.md`
  - `docs/plans/20260714T155943Z_workspace_reorientation_ledger.md`
  - `docs/plans/20260715T220618Z_p2_prevalidation_dra_mount_ledger.md`

No file in that checkout may be edited, staged, cleaned, reset, committed, or
otherwise used as an implementation surface by this ledger.

### Source inventory and sweeps

- Six legacy create-config fields in scope:
  `slurm_accounting_enabled`, `slurm_accounting_create_db`,
  `slurm_accounting_stack_name`, `slurm_accounting_database_name`,
  `slurm_accounting_db_username`, and `slurm_accounting_instance_type`.
- Sweep command:
  `rg -l '<six-field alternation>' daylily_ec tests | sort` -> 12 files.
- Focused reference-count command over source config/workflow, packaged create
  template, and existing create/template tests:
  `rg -n '<six-field alternation>' daylily_ec/config daylily_ec/workflow daylily_ec/resources/payload/config/daylily_ephemeral_cluster_template.yaml tests/test_workflow.py tests/test_triplets.py tests/test_attach_slurm_accounting.py | wc -l`
  -> 35 references at Gate 0.
- Existing accounting implementation surfaces include
  `daylily_ec/aws/slurm_accounting.py`,
  `daylily_ec/workflow/attach_slurm_accounting.py`,
  `daylily_ec/workflow/create_cluster.py`,
  `daylily_ec/pcluster/runner.py`, `daylily_ec/state/models.py`, and the
  packaged configuration under `daylily_ec/resources/payload/config/`.
- Prior source-of-truth ledger inspected:
  `docs/plans/20260714T175621Z_slurm_accounting_default_off_followon_attach_ledger.md`.
  It confirms the standalone attach safety contract and is superseded only for
  the new create-time orchestration described here; standalone commands remain
  supported.

### Baseline validation

From the clean implementation worktree:

```text
source ./activate && pytest -q \
  tests/test_slurm_accounting.py tests/test_attach_slurm_accounting.py
```

Result: `33 passed in 1.02s` on Python `3.11.15`, pytest `9.1.1`.

### Assumptions and live-system limits

- Current remote `main`, not the stale dirty `sentieon-single` checkout, owns
  implementation and release.
- Ursa GUI wiring is out of scope. The paired approval flags are its stable
  authenticated integration interface.
- Existing/running clusters are unchanged by this release. Automatic lifecycle
  orchestration is create-only and applies to the fresh cluster being built.
- The initial preflight/rendered ParallelCluster YAML always uses empty
  accounting substitutions. Legacy configuration values have no effect and
  are not regenerated.
- Base cluster state is persisted before accounting preparation begins.
- A region with any incompatible accounting stack never receives an automatic
  duplicate.
- No live AWS mutation occurs before Gate 5. Local fixtures do not satisfy the
  live proof row.
- No proof cluster deletion is authorized by this ledger. Any later deletion
  remains destructive and requires a separate, explicit second approval after
  the exact resources/effect are restated.
- Creating the first live regional accounting stack is cost-incurring and may
  happen during proof only when the regional inventory is empty, the command
  carries both approval flags, and the live approval boundary is explicitly
  satisfied. Prefer attaching a compatible existing singleton when available.
- Read-only accounting validation from the headnode runs as `ubuntu`. The proof
  does not authorize Slurm daemon/service changes, scheduler intervention,
  queue manipulation, or direct configuration edits.
- ParallelCluster updates must obey AWS validation: never use force-update,
  never bypass the fleet-stopped requirement, and never treat an indeterminate
  update as safe to restart.

## Control ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| SACCT-POST-001 | Repository control | Create this ledger and record remote branch/tag identity, dirty-tree preservation inventory, baseline tests, exact worktree, assumptions, and safety boundaries. | SUCCESS | feature_implementation | Gate 0 | Agent 1 | Gate 0 sections above; clean worktree at `d1e2ee40`; annotated `10.3.17`; `10.3.18` absent; accounting baseline `33 passed`. |  | Inventory freeze is complete before product edits; the dirty `sentieon-single` checkout is preserved out of scope. |
| SACCT-POST-002 | CLI | Add/validate the four `dyec create` options and forward the normalized contract, including exact lowercase mode, paired approvals, default-on, non-interactive behavior, and off-mode strict-flag handling. | SUCCESS | feature_implementation | Gate 1 | Agent 2 | `daylily_ec/cli.py`; focused CLI smoke covered default on, explicit off plus strict, exact-lowercase rejection, paired-flag rejection, and paired approval forwarding; Ruff, `py_compile`, and `git diff --check` passed. |  | The four-option normalized CLI contract is implemented; exact workflow-kwargs assertions are owned by Agent 8 after Agent 6 adds the receiving signature. |
| SACCT-POST-003 | Config/templates | Remove all six accounting fields/defaults from source and packaged create templates, required config keys, validation dependencies, and generated next-run configs; both initial render modes remain accounting-free. | SUCCESS | removable_compatibility_debt | Gate 1 | Agent 3 | Source and packaged templates are byte-identical with all six fields removed; `REQUIRED_CONFIG_KEYS`, create validation, `final_values`, and next-run regeneration were cleared; focused `24 passed`, relevant suites `201 passed`, scoped Ruff and `git diff --check` passed. |  | Legacy accounting values cannot affect the initial render or reappear in generated create configuration. |
| SACCT-POST-004 | Accounting preparation | Refactor compatible discovery, the 90-second duplicate warning/Ursa-or-host selection, optional double-approved first-singleton creation, and redacted update-YAML rendering; preparation completes before fleet stop. | SUCCESS | feature_implementation | Gate 2 | Agent 4 | Reusable zero-fleet-mutation preparation API with structured missing/incompatible errors, atomic `service_created`, existing 90-second selection, alternate executable propagation, sanitized exceptions/reprs, and standalone attach preservation; `38 passed`, Black, Ruff, mypy, and diff check passed. |  | Required sensitive values exist only inside the generated update YAML consumed by ParallelCluster; public results/warnings/errors remain non-secret. |
| SACCT-POST-005 | ParallelCluster runner | Add `update-compute-fleet` runner support and bounded exact-state fleet/update waiters with alternate `pcluster_executable` propagation. | SUCCESS | feature_implementation | Gate 3 | Agent 5 | `daylily_ec/pcluster/{runner.py,monitor.py,__init__.py}` plus focused tests; exact transition validation, 20-minute fleet waits, 90-minute update wait, 5-minute start bound, structured restoration safety, and executable/profile propagation; `79 passed`, Black, Ruff, mypy, and `git diff --check` passed. |  | Waiter outcomes explicitly distinguish recoverable rollback from indeterminate states where restart is forbidden. |
| SACCT-POST-006 | Create lifecycle | Add the create-only prepare, stop, attach, dry-run, update, terminal wait, restore, headnode readiness, and read-only verification orchestration with the specified recovery state machine. | SUCCESS | feature_implementation | Gate 3 | Agent 6 | `daylily_ec/workflow/postcreate_slurm_accounting.py` and minimal `create_cluster.py` integration; base state precedes preparation; exact RUNNING/STOPPED gating; bounded stop/update/restore; replacement-only reconfiguration; ubuntu read-only `sacct`; fail-soft/strict completion; focused lifecycle/config/state suite `285 passed`; Ruff, mypy, Black for new lifecycle/test modules, and `git diff --check` passed. |  | Create-only orchestration is complete; indeterminate update/concurrent transition states never issue an automatic restart, while known-safe post-stop failures restore an initially running fleet. |
| SACCT-POST-007 | State/output | Persist non-secret receipt fields, complete state/summaries, warning and recovery panels, fail-soft/strict exit semantics, and output redaction enforcement. | SUCCESS | legitimate_safety_handling | Gate 4 | Agent 7 | Strict receipt/status/stage models, deterministic receipt store/load, safe state application, fixed warning/status helpers, and removal of five sensitive `StateRecord` fields; state/redaction suites `39 passed`; Ruff, Black, mypy, and diff check passed. |  | Receipt/state/output APIs cannot accept arbitrary exception text or persist resolved URI, private IP, secret ARN, database, or username values. |
| SACCT-POST-008 | Unit/contract tests | Add independent CLI, template, config, state, approval, output, and redaction regression coverage. | SUCCESS | contract_test | Gate 4 | Agent 8 | Twenty independent cases added across CLI defaults/modes/validation/help, Ursa paired approvals, template/config/render isolation, and output/receipt sentinel redaction; focused combined suite `260 passed`; Ruff, Black, and diff check passed. |  | Public contract and negative regression coverage is complete without product-code changes. |
| SACCT-POST-009 | Lifecycle/docs tests | Add lifecycle, waiter, failure/recovery, ordering, integration, redaction, and documentation coverage. | SUCCESS | contract_test | Gate 4 | Agent 9 | Full ordering plus 16-case failure/recovery/redaction matrix, strict/soft exit and four-panel statuses, standalone attach preservation, README and CLI operator docs; focused `276 passed`; Ruff, Black, hard-link parity, and diff check passed. |  | Lifecycle recovery and operator guidance satisfy Gate 4; AWS setup was unchanged because permissions and quotas did not change. |
| SACCT-POST-010 | Integration/release/proof | Integrate all rows; run focused and full verification; normally merge; create/push annotated unused patch tag; perform one exact-tag live proof; merge evidence; verify operator pin separately. | IN_PROGRESS | feature_implementation | Gate 5 | Agent 10 | Agent 10 integration pass: focused `562 passed`; complete repository `1686 passed, 11 skipped`; scoped Ruff and Black check passed; 11 changed source modules passed mypy with Python 3.11; the two pre-existing broad modules reproduced the same 19 baseline mypy findings on current `origin/main`; template parity and `git diff --check` passed. Remote `main` advanced from `d1e2ee40` to `ad747b56` during implementation and must be integrated before release. |  | Release, tag, exact-tag live proof, and follow-up evidence/pin merge remain open. |

## Required lifecycle and recovery contract

1. Validate the normalized CLI contract before AWS work.
2. Render/preflight/create the initial cluster with empty accounting
   substitutions, regardless of legacy config values or requested mode.
3. Configure the headnode, confirm heartbeat/readiness, and persist the
   successful base state before accounting begins.
4. If accounting is off, record `OFF` and complete without discovery or fleet
   mutation.
5. If accounting is on, discover/optionally create the service and render the
   candidate update YAML before stopping the fleet. Discovery, decline, stack
   creation, compatibility, or render failure must not issue a fleet request.
6. Accept only exact fleet state `RUNNING` or `STOPPED`; reject transitional or
   concurrent states without issuing another request.
7. For initially `RUNNING`: request `STOP_REQUESTED`, wait at most 20 minutes
   for exact `STOPPED`, dry-run the update, submit it, wait at most 90 minutes
   for a terminal update state, then request `START_REQUESTED` and wait at most
   20 minutes for exact `RUNNING` when recovery rules permit.
8. Preserve an initially stopped fleet as stopped.
9. Re-describe the headnode after update. Reconfigure only when its instance ID
   changed; otherwise run bounded readiness validation.
10. Verify accounting read-only from the headnode as `ubuntu` without changing
    Slurm services/configuration.
11. On a safely recoverable failure after DYEC stopped the fleet, attempt
    restoration before returning. Never restart during an indeterminate
    update, rollback failure, or concurrent transition.
12. The final panel always distinguishes base cluster creation success from
    accounting `OFF`, `ENABLED`, `WARNING`, or `RECOVERY REQUIRED`. Accounting
    warnings exit `0` by default and return code `2` only in strict mode, with
    identical recovery detail.

## Non-secret accounting receipt contract

Persist only operational facts required for recovery/audit:

- requested mode;
- whether each approval flag was supplied/obtained;
- whether the service was created;
- furthest stage reached;
- update-config path;
- terminal cluster and fleet states;
- whether an initially running fleet was restored;
- error stage;
- recovery-required boolean.

Never persist or print a newly resolved database URI, endpoint/private IP,
password, username, password-secret ARN, or other resolved secret value in the
receipt, final panel, JSON output, warning text, or exception chain.

## Verification and release acceptance

- CLI tests cover defaults, explicit modes, invalid values, paired creation
  approvals, ignored strict flag with off, help text, and Ursa's paired-flag
  non-interactive invocation.
- Config tests prove no accounting prompts/required keys remain and initial YAML
  never contains `Scheduling.SlurmSettings.Database` or accounting security
  groups in either requested mode.
- Ordering tests prove base create, headnode, heartbeat, and base-state
  persistence precede accounting preparation, fleet stop, dry-run, update,
  terminal wait, fleet restore, and verification.
- Failure tests cover discovery, user decline, stack creation, stop, dry-run,
  submit, rollback, timeout, readiness, verification, and restart. Discovery
  or creation failure never stops the fleet; every safely recoverable post-stop
  failure attempts restoration.
- Sentinel endpoint/private-IP/secret values are injected into every failure
  path and proven absent from terminal, JSON, warning, exception, and receipt
  output.
- Focused suites, Ruff, Black check, mypy for changed modules,
  `git diff --check`, and the complete repository suite all pass.
- Changes merge normally to `main`; release tag is annotated and non-v; no
  existing tag is moved or overwritten.
- One fresh cluster from the exact released tag proves initial YAML omits
  accounting, base cluster reaches `CREATE_COMPLETE`, default-on accounting
  attaches a compatible singleton (or creates the first only with both live
  approvals), update reaches terminal success, the initially running fleet
  returns to `RUNNING`, and read-only `sacct` validation succeeds.
- If live accounting fails, the exact-tag proof must instead demonstrate the
  default command exits `0`, retains the successfully created cluster, and
  records exact recovery state. Strict mode may be proven with automated tests
  instead of a second paid cluster.
- The proof cluster is not deleted under this ledger. Operator pin update is a
  separate post-proof action/evidence commit.

## Execution waves

Concurrency is limited to three collaborators beside the orchestrator, so the
ten independent ownership roles execute in waves:

1. Agent 1 completes Gate 0.
2. Agents 2, 3, and 5 work disjoint CLI, config/template, and runner/waiter
   source areas.
3. Agents 4, 6, and 7 implement the dependent preparation, lifecycle, and
   state/output areas.
4. Agents 8 and 9 independently cover unit/contract and lifecycle/docs tests.
5. Agent 10 performs integration, release, exact-tag live proof, and evidence
   merge.

Agents update only their owned row unless the orchestrator explicitly
reassigns work. Each handoff must report changed files, commands/results,
status, blockers, and residual risks.

## Final report

All rows terminal: `no`

Objective complete: `no`

Status counts:

- `SUCCESS`: 9
- `DUPLICATE`: 0
- `NO_LONGER_NEEDED`: 0
- `FAIL`: 0
- `BLOCKED`: 0
- `OPEN`: 0
- `IN_PROGRESS`: 1
- `ATTEMPTING_BUGFIX`: 0

Validation recorded so far:

- `source ./activate && pytest -q tests/test_slurm_accounting.py tests/test_attach_slurm_accounting.py`
  -> `33 passed in 1.02s`.
- Agent 10 focused integration suite over accounting, attach, lifecycle, CLI,
  workflow, config, runner, and monitor tests -> `562 passed in 8.23s`.
- Agent 10 complete repository suite -> `1686 passed, 11 skipped, 1 warning
  in 69.83s`.
- Ruff over all 22 changed Python files -> `All checks passed!`.
- Black check over all 22 changed Python files -> `22 files would be left
  unchanged` after applying Black's required mechanical formatting to
  `daylily_ec/cli.py` and `daylily_ec/workflow/create_cluster.py`.
- Mypy with `--python-version 3.11` over the 11 changed source modules other
  than the two historically broad CLI/orchestrator modules -> `Success: no
  issues found in 11 source files`. The repo-level `python_version = 3.9`
  setting emits a tooling warning with the installed mypy, which no longer
  supports Python 3.9.
- Mypy over `daylily_ec/cli.py` and
  `daylily_ec/workflow/create_cluster.py` initially found one new Literal
  mismatch in the accounting mode plus 19 unrelated findings. The new
  mismatch was fixed. A detached current-`origin/main` comparison reproduced
  the same remaining 19 findings, proving zero new mypy findings in those two
  changed modules.
- Source/packaged create-template byte parity and `git diff --check` passed.

Remote integration note:

- Gate 0 froze `origin/main` at `d1e2ee40`. Before release, Agent 10 fetched
  current remote state and found `origin/main` at `ad747b56`, merge PR #19.
  Agent 10 rebased the implementation normally onto that commit without a
  conflict. The post-rebase affected suite passed `568` tests, and the complete
  repository suite passed `1692` tests with `11` skips and the same one
  third-party deprecation warning. Post-format rerun: affected `568 passed in
  8.53s`, Ruff passed, Black left all 22 changed Python files unchanged,
  template parity passed, and `git diff --check` passed.

Non-success terminal rows: none.

Residual risks:

- Product implementation, complete regression coverage, release, and live
  exact-tag proof remain open.
- Live proof may encounter a regional accounting/VPC compatibility state that
  correctly produces `WARNING` rather than `ENABLED`; that outcome is accepted
  only when retention, exit code, recovery state, and redaction are proven.
