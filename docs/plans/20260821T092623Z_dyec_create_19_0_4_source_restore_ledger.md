# DYEC Create 19.0.4 Source-Restore Ledger

Date: 2026-08-21

## Controlling Plan

Restore root `dyec create` by transplanting its working implementation directly
from released tag `19.0.4` (`581d770f2a3c96311ff5ebe748c9df4e76c7ddf8`)
into a branch based on `19.0.11`
(`4b894698998ad09a21aa6bcf9d8fca41dca92462`). Do not rewrite or reinterpret
the old create behavior. Preserve unrelated 19.0.11 functionality and keep the
newer `create-request`, inspection, compute-fleet, and recovery commands
standalone and disconnected from root create.

No live AWS creation/deletion is authorized by this plan. After approving the
rollback, the user explicitly amended the delivery scope to include committing
the completed work, pushing the `codex/` branch, and creating/pushing the next
safe non-`v` annotated patch tag, explicitly selected as `19.0.12`. The user
also directed that the slow repository-catalog snapshot modules be optional and
off by default. PR creation, merge, package building/publication, and live
infrastructure execution remain outside this authorization.

## Gate 0: Inventory Freeze

- Controlling plan: user-approved Codex task, copied above.
- Ledger: `docs/plans/20260821T092623Z_dyec_create_19_0_4_source_restore_ledger.md`.
- Original checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`,
  detached at `19.0.11`; it contains unrelated untracked user artifacts and is
  not an implementation workspace.
- Implementation checkout:
  `/Users/jmajor/.codex-worktrees/dyec-restore-create-19.0.4`, branch
  `codex/restore-dyec-create-19.0.4`, initially clean at `19.0.11`.
- Source authority: annotated/released Git tag `19.0.4`, commit
  `581d770f2a3c96311ff5ebe748c9df4e76c7ddf8`.
- Inventory sweep:
  `rg -n 'create-request|recover_slurm_accounting|run_postcreate_slurm_accounting|def create\\(|def run_create_workflow\\(' daylily_ec/cli.py daylily_ec/workflow/create_cluster.py daylily_ec/workflow/postcreate_slurm_accounting.py`.
- Create-owned changed files identified between 19.0.4 and 19.0.11:
  `daylily_ec/cli.py`, `daylily_ec/workflow/create_cluster.py`,
  `daylily_ec/workflow/postcreate_slurm_accounting.py`,
  `tests/test_workflow.py`, `tests/test_postcreate_slurm_accounting.py`, and
  `tests/test_create_slurm_failure_coverage.py`.
- Authoritative 19.0.4 function SHA-256 values (AST function source, excluding
  decorators): `create` =
  `152de75072afef57bbc47e2e20c9afb87f52aa0d3e5dc37f1109defd1b6361cb`;
  `run_create_workflow` =
  `a4a86878a79d6cd3617356be133f8b11487e07217fad3f8e43e3170100808471`;
  `run_postcreate_slurm_accounting` =
  `e8f914b63915037b8127b20ed1e2f217ac9b168310624c34b49201ffde60df5c`.
- Baseline command:
  `source ./activate && pytest -q tests/test_workflow.py tests/test_postcreate_slurm_accounting.py tests/test_create_slurm_failure_coverage.py tests/test_cli_registry_v2.py`
  -> `580 collected, 461 passed, 119 failed in 164.37s`. The dominant create
  failures occur before their expected paths because untouched 19.0.11 requires
  `--output-dir`; additional unrelated registry/environment failures are
  inherited baseline failures and must be separated from rollback regressions.
- Live-system limit: validation is local/mocked only. No AWS mutation is
  approved.
- Release boundary: `19.0.12` was absent locally and from the `origin`
  (`lsmc-bio`) tag namespace after a fresh tag fetch; the release branch was
  also absent from `origin` before delivery.
- Assumption explicitly authorized by the user: the historical defaults,
  prompts, and discovery behavior in 19.0.4 are intentional for this rollback,
  notwithstanding the repository's general no-fallback preference.

## Control Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE-000 | repository | Freeze source, target, dirty-state, and baseline evidence before runtime changes | SUCCESS | plan_amendment | Gate 0 | orchestrator | Gate 0 inventory above |  | Baseline and implementation boundary recorded before runtime edits. |
| REST-001 | CLI | Transplant the exact 19.0.4 root `create` function plus its imports, constants, and registration policy | SUCCESS | feature_implementation | Gate 1 | orchestrator | Decorated `create` matches 19.0.4 exactly, SHA-256 `f28d72996866ed70eb2b5fedf5a753702d7ccec7e2611498ab17db8449c75d5a`; `_report_create_runtime` matches at `9163b34b7e420f7e9fca4e812447ed3571aba6f2ee4e54e8f37a50bf83ebe1fd`; both create defaults match. |  | Exact tag source transplanted; no manual reimplementation. |
| REST-002 | create workflow | Transplant the exact 19.0.4 `run_create_workflow` implementation without routing through strict create-request or recovery | SUCCESS | feature_implementation | Gate 1 | orchestrator | Function matches 19.0.4 exactly, SHA-256 `a4a86878a79d6cd3617356be133f8b11487e07217fad3f8e43e3170100808471`; its two reachable formatting-only helpers have identical ASTs. |  | Newer unrelated headnode configuration remains in place around the recovered workflow. |
| REST-003 | accounting | Transplant the exact 19.0.4 post-create accounting implementation; do not modify standalone attach or add force | SUCCESS | feature_implementation | Gate 1 | orchestrator | Entire `daylily_ec/workflow/postcreate_slurm_accounting.py` matches 19.0.4, SHA-256 `29ac0a673593277d0f6fde936fab7e8aaa4458972d32567cd14f7bf503ba7315`; standalone attach source untouched. |  | No `--force` and no new recovery path added. |
| REST-004 | tests | Recover applicable 19.0.4 create/accounting tests while preserving unrelated current coverage | SUCCESS | contract_test | Gate 5 | orchestrator | `TestRunCreateWorkflow`, `_build_workflow_config`, and `_run_stubbed_create_workflow` match 19.0.4 exactly; 70/70 recovered workflow/accounting tests, 122/122 create failure-coverage tests, and 36/36 selected CLI/create/standalone tests pass. |  | One new mocked regression invokes the literal three-flag command. |
| REST-005 | docs | Restore current operator documentation for root create from 19.0.4 source wording while retaining standalone command documentation | SUCCESS | historical_docs_only | Gate 5 | orchestrator | README, agent guide, CLI reference, quickest-start, and ultra-rapid-start now lead with the restored three-flag entrypoint and mark newer request/fleet/inspection/recovery tools as standalone. |  | Newer unrelated operational documentation retained. |
| REST-006 | equivalence | Prove restored create-owned source and normalized help match 19.0.4; prove the exact three-flag invocation enters the old workflow without AWS | SUCCESS | contract_test | Gate 5 | orchestrator | Normalized old/restored `dyec create --help` SHA-256 values both equal `ca1f92d4fed9749338b48a5cc938409ad050dea33619644e93b97a5f7f0eff32`; `test_create_command_three_flag_entrypoint_uses_restored_workflow` passes. |  | No AWS call made; the workflow boundary is monkeypatched. |
| REST-007 | standalone commands | Prove `create-request`, inspection, compute-fleet, recovery, and ordinary accounting attach remain registered and decoupled | SUCCESS | contract_test | Gate 5 | orchestrator | Help exits 0 for `create-request`, `cluster compute-fleet`, `slurm-accounting inspect`, `slurm-accounting recover`, and `slurm-accounting attach`; selected registry suite is 36/36. |  | Root create is exact 19.0.4 source and contains no calls to these standalone commands. |
| REST-008 | acceptance | Run focused local suites and classify the attempted full-suite evidence under the user-amended test policy | SUCCESS | contract_test | Gate 5 | orchestrator | Final restored workflow/accounting/failure suite: 192 passed. Final selected CLI/create/standalone suite: 37 passed. Full CLI registry comparison: untouched 19.0.11 = 210 passed/49 failed; restored = 233 passed/24 failed. Standalone accounting comparison: untouched = 129 passed/54 failed; restored = 130 passed/53 failed. |  | The original full run was stopped at the user's direction after 1001.19s with a nonterminal partial snapshot of 154 failed, 2395 passed, and 11 skipped; observed failures were concentrated in inherited catalog, activation, headnode, and recovery fixtures. The user replaced that gate with focused restore tests and made the slow catalog snapshot modules opt-in. |
| REST-009 | release boundary | Prepare the explicitly requested 19.0.12 source release without changing catalog commands | SUCCESS | release_metadata | Gate 5 | orchestrator | `CURRENT_DYEC_BUILD=19.0.12`; source and packaged catalogs are byte-identical; the explicit 19.0.12 snapshot is semantically identical to 19.0.11 with 33 commands; `dyec --json catalog list --dyec-version 19.0.12 --type prod` exits 0 with `status=resolved`. |  | Follows the established 19.0.10/19.0.11 immutable-snapshot release pattern. No wheel, sdist, package publication, PR, merge, or AWS execution is part of delivery. |
| REST-010 | optional tests | Make the slow repository-catalog snapshot modules opt-in and off by default | SUCCESS | test_policy | Gate 5 | orchestrator | Default invocation collects and skips all 37 marked tests in 0.22s. Explicit opt-in smoke test passed earlier with `--run-catalog-snapshot-tests`. README and CLI reference document the opt-in flag. |  | User-authorized test-policy amendment; other tests retain their existing default behavior. |

## Final Report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 11
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 0
- OPEN: 0

Changed files: `README.md`,
`config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/cli.py`,
`daylily_ec/repositories.py`,
`daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`,
`daylily_ec/workflow/create_cluster.py`,
`daylily_ec/workflow/postcreate_slurm_accounting.py`,
`docs/agent_cli_guide.md`, `docs/cli_reference.md`,
`docs/quickest_start.md`, `docs/ultra_rapid_start.md`, `pyproject.toml`,
`tests/conftest.py`, `tests/test_cli_registry_v2.py`,
`tests/test_repository_catalog.py`,
`tests/test_repository_catalog_aliases.py`, `tests/test_workflow.py`, and this
ledger.

Validation: the restored create-owned source blocks match `19.0.4` exactly at
the hashes recorded above; normalized create help remains identical; the
literal three-flag mocked entrypoint passes; 192 focused workflow/accounting
tests and 37 selected CLI tests pass; 37 optional catalog snapshot tests skip by
default; source/package catalog copies are byte-identical; the 19.0.12 snapshot
equals 19.0.11; public 19.0.12 catalog resolution succeeds; `compileall` and
`git diff --check` pass.

Residual risks: no live AWS creation was run or authorized. The interrupted
full-suite attempt has no terminal result, and the current repository retains
unrelated failing legacy fixtures; acceptance therefore rests on exact
19.0.4 source equivalence, the untouched-19.0.11 comparisons, and the focused
restoration gates explicitly accepted by the user.
