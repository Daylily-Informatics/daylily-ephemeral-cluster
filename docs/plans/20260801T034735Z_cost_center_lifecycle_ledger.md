# DYEC Cost-Center Lifecycle Redesign Ledger

Controlling request: make Slurm cost-center admission independent of monthly usage rows and month rollover. Admission must require an existing active registry row, an authorized submitter, and a non-expired optional UTC `active_until`; retain the cluster AWS Budget gate. Monthly cap and usage remain reporting telemetry only.

Ledger path: `docs/plans/20260801T034735Z_cost_center_lifecycle_ledger.md`

## Gate 0: Inventory Freeze

- Isolated worktree: `/Users/jmajor/.codex/worktrees/7731/daylily-ephemeral-cluster-cost-center-lifecycle-20260801`
- Branch and base: `codex/cost-center-lifecycle-20260801` at `ac18aaaebd4a4f183ecd7a6a312dd87c88a3dde4` (`origin/main`).
- Initial worktree state: clean (`git status --short --branch`).
- Controlling runtime assets: `config/day_cluster/sbatch` and `daylily_ec/resources/payload/config/day_cluster/sbatch`; baseline `cmp -s` returned `0`.
- Primary implementation surfaces: `daylily_ec/aws/cost_centers.py`, `daylily_ec/cli.py`, `daylily_ec/aws/validation.py`, both sbatch assets, focused tests, and operator docs.
- Inventory sweep: `rg -n "current_month|monthly cap|usage snapshot|max_usage_age_hours|initialize_cost_center_usage|cost-center-usage" ...` found 98 matches in the scoped implementation/docs/tests.
- Baseline focused tests: `source ./activate && pytest -q tests/test_cost_centers.py tests/test_sbatch_wrapper.py tests/test_aws_validation_cost_controls.py tests/test_cli_additional_coverage.py` -> `68 passed, 1 failed`. The pre-existing failure is a positional direct call in `test_cost_centers_create_edit_disable_show_list` that drifted after an earlier parameter insertion; production behavior did not fail.
- Live-system boundary: no AWS/DynamoDB mutations, headnode deployment, cap changes, commits, pushes, tags, or PRs are authorized or performed in this worktree.
- Migration assumption: existing registry rows omit `active_until` and therefore remain active indefinitely while `status=active`; no data backfill is required. Existing monthly usage rows remain unchanged.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Freeze source, parity, worktree, test baseline, and live mutation boundary. | SUCCESS | contract_test | Gate 0 | cost-center agent | Gate 0 inventory above. |  | Baseline recorded before runtime edits. |
| LIFE-001 | Registry model | Add optional canonical UTC `active_until` with strict ISO-8601 validation and lossless DynamoDB/JSON serialization. | SUCCESS | feature_implementation | Gate 1 | cost-center agent | `validate_active_until`, `CostCenter.active_until`, DynamoDB codecs, and exact-shape/calendar tests in `tests/test_cost_centers.py`. |  | Boundary is exclusive; omitted attribute decodes to an indefinite lifetime. |
| LIFE-002 | Registry operations | Preserve `active_until` across disable/edit and enforce expiration in shared authorization semantics. | SUCCESS | feature_implementation | Gate 1 | cost-center agent | `cost_center_is_expired`, `authorize_cost_center`, edit/clear/disable paths, and before/at-boundary tests. |  | `now >= active_until` is expired. |
| CLI-001 | CLI | Add `--active-until` create/edit support, an explicit clear operation, and show/list output through the registry model. | SUCCESS | feature_implementation | Gate 1 | cost-center agent | `dyec cost-centers create --help` and `edit --help` expose set/clear options; CLI tests cover set, clear, show, and list. |  | `--usage-table-name` is no longer exposed by create. |
| ADM-001 | Slurm admission | Remove current-month usage lookup, freshness, and monthly-cap admission checks; retain AWS Budget, registry existence/status, authorization, and optional `active_until` checks. | SUCCESS | active_product_contract | Gate 2 | cost-center agent | Both sbatch assets now perform one registry lookup and lifecycle/authorization validation; 20 sbatch tests pass including absent usage-table tag and month-data failure modes. |  | Existing cluster AWS Budget gate and its explicit override semantics remain unchanged. |
| TEL-001 | Telemetry | Stop create/ensure from silently synthesizing a current-month usage row; retain explicit usage write/refresh/report interfaces and monthly cap metadata. | SUCCESS | feature_implementation | Gate 1 | cost-center agent | Create/ensure tests assert an empty usage table; explicit initialize/put/refresh paths remain tested. |  | No synthetic row appears at month rollover or registry creation. |
| VAL-001 | Readiness | Separate currently eligible active rows from expired lifecycle rows; report expiry and monthly usage conditions without blocking unrelated cost centers. | SUCCESS | contract_test | Gate 2 | cost-center agent | `tests/test_aws_validation_cost_controls.py` covers usage-table/missing/stale/exhausted WARN results and verifies an expired row remains in PASS lifecycle details while usage is evaluated only for an eligible peer. |  | Runtime headnode IAM admission requires only registry `GetItem`; submission against the specific expired row remains fail-closed. |
| PAR-001 | Packaged parity | Keep source and payload sbatch assets byte-identical and test parity. | SUCCESS | contract_test | Gate 1 | cost-center agent | Final `cmp -s` returned `0`; `bash -n` returned `0` for both files; parity is also asserted by test. |  | Source and packaged payload are byte-identical. |
| DOC-001 | Documentation | Document lifecycle admission, exact timestamp shape, no month rollover dependency, and telemetry-only monthly fields. | SUCCESS | feature_implementation | Gate 1 | cost-center agent | Updated `docs/operations.md` and `docs/aws_setup.md`. |  | Includes a bounded `RnD` create example and explicit clear operation. |
| DEBT-001 | Removed override | Remove stale-month launch override instead of preserving a no-op compatibility switch. | SUCCESS | active_product_contract | Gate 2 | cost-center agent | No active source/test/current-doc match for `DAY_PASS_ON_STALE` or `--pass-on-stale-budget`; CLI and generator tests assert absence. | Monthly usage is no longer an admission input, so a stale-month admission override has no coherent behavior. | No compatibility shim or silent no-op retained. |
| TEST-001 | Focused validation | Update and pass focused cost-center, sbatch, CLI, and AWS readiness tests only. | SUCCESS | contract_test | Gate 5 | cost-center agent | Core tranche: `82 passed, 155 deselected`; launcher tranche: `22 passed, 225 deselected`; generated-script tranche: `2 passed`; focused Ruff fatal checks, Python compile, shell syntax, parity, and `git diff --check` all pass. |  | Baseline positional-test drift was corrected with keyword calls; no broad repository suite was run. |

## Final Report

All rows terminal: yes

Objective complete: yes for the isolated implementation and focused validation scope. No release, deployment, live DynamoDB write, or headnode reconfiguration was performed.

Status counts:

- SUCCESS: 11
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- OPEN: 0

## Migration and Rollout Notes

- DynamoDB is schemaless for this optional attribute. Existing registry rows with no
  `active_until` need no backfill and remain indefinite while `status=active`.
- Existing monthly cap metadata and usage rows are untouched and remain available to
  reporting and refresh commands. New cost-center creation no longer synthesizes a
  current-month zero row.
- The active sbatch wrapper and headnode runtime policy must be delivered through a
  later normal DYEC release/configure operation before a cluster uses the new contract.
  This ledger does not claim that rollout.
- Existing IAM grants and cluster tags for the usage table may remain for telemetry;
  Slurm admission no longer requires them.
- The stale-month override CLI/environment interface is deliberately removed because
  monthly freshness is no longer an admission decision. Callers must remove that
  obsolete option rather than depending on a compatibility no-op.

Final validation timestamp: `2026-08-01T04:35:34Z`.

## Review Correction

An `active_until` boundary is a normal lifecycle termination, not a malformed
global registry state. Readiness now reports status-active rows in separate
`eligible_active_cost_centers` and `expired_active_cost_centers` collections,
keeps expiry in the structured details of a passing check, and evaluates monthly
usage telemetry only for the eligible collection. `WARN` would abort the normal
preflight unless `--pass-on-warn` were supplied, so it is intentionally not used
for normal expiration. The sbatch wrapper continues to reject the specific
expired cost center.
