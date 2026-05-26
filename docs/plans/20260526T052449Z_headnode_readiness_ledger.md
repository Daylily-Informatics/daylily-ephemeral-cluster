# Headnode Readiness Hardening Ledger

- Created: 2026-05-26T05:24:49Z
- Orchestrator: Codex
- Controlling request: harden post-create/headnode readiness so smoke workflows cannot start until a newly created cluster proves DAY-EC activation, `day-clone` availability, and `/fsx/references` reference visibility.
- Failure trail: `docs/plans/20260523T010341Z_tstver411_cluster_monitor_hg003_1x_ledger.md`
- Primary repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- Reference repo: `/Users/jmajor/projects/daylily/daylily-omics-references`

## Gate 0 Inventory

### DAY-EC repo

- Branch: `codex/analysis-id-export-catalog-validation`
- Status: dirty before this ledger was created.
- Existing modified files to preserve:
  - `config/day_cluster/post_install_ubuntu_combined.sh`
  - `config/daylily_available_repositories.yaml`
  - `daylily_ec/repositories.py`
  - `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`
  - `daylily_ec/resources/payload/config/daylily_available_repositories.yaml`
  - `tests/test_headnode_init.py`
  - `tests/test_repository_catalog.py`
- Existing untracked artifacts to preserve include prior `docs/plans/` ledgers and inputs/logs, `docs/AWS_3month_retrospective_cost_analysis.md`, `docs/aws_3month_retrospective_cost_analysis_assets/`, `docs/tstver411b_command_catalog_test_results.md`, `fill_in_the_blanks_lims.md`, and `tmp/`.

### daylily-omics-references repo

- Branch: `main`
- Status: dirty before this ledger was created.
- Existing modified files to preserve:
  - `.gitignore`
- Branch note: local `main` is behind `origin/main` by one commit; this task preserves current checked-out state and does not pull.

## Non-Destructive Guardrails

- No live AWS smoke is required for this regression.
- No destructive AWS operation is authorized.
- Any live headnode validation remains a separate row and must use DAY-EC SSM helpers as `ubuntu`.
- No fallback, compatibility shim, inferred alternate path, `/data` substitute, or service-side discovery will be added.

## Multi-Agent Rows

| Row | Owner | Scope | Status | Evidence |
| --- | --- | --- | --- | --- |
| G0-001 | Orchestrator | Record Gate 0 inventory for both repos before implementation. | SUCCESS | Ledger created with dirty worktree baseline. |
| DEC-001 | Orchestrator | Use one shared DAY-EC readiness helper and fail hard on missing runtime state. | SUCCESS | Added shared helper; no `/data` substitute or fallback path added. |
| DYEC-001 | Agent A, DAY-EC readiness | Add `daylily_ec/headnode_readiness.py` with SSM-backed ubuntu login-shell validation. | SUCCESS | Helper builds a `script -q -c "bash -lc ..."` readiness probe and runs via `daylily_ec.aws.ssm.run_shell` as `ubuntu`. |
| DYEC-002 | Agent A, DAY-EC readiness | Replace inline `configure_headnode` fresh-login validation with shared helper. | SUCCESS | `configure_headnode` delegates final validation to `validate_headnode_readiness`. |
| DYEC-003 | Agent A, DAY-EC readiness | Gate e2e staging and workflow launch with shared helper before smoke workflow actions. | SUCCESS | `_validate_headnode_bootstrap` now uses the shared helper and records `ssm:headnode-readiness` before staging/launch. |
| DYEC-004 | Agent A, DAY-EC readiness | Gate `daylily_run_omics_analysis_headnode.main()` immediately after SSM-online and before stage discovery or tmux creation. | SUCCESS | Launcher calls readiness after `wait_for_ssm_online` and before run-context/stage discovery. |
| DYEC-T001 | Agent B, DAY-EC tests | Add focused readiness tests and update configure/e2e/launcher ordering coverage. | SUCCESS | `tests/test_headnode_readiness.py`, `tests/test_workflow.py`, `tests/test_ssm_e2e_runner.py`, and `tests/test_script_entrypoints.py` cover readiness contents and call ordering. |
| REF-001 | Agent C, reference verifier | Add explicit DAY-EC required object/prefix constants. | SUCCESS | Added `DAYEC_REQUIRED_OBJECT_KEYS` and `DAYEC_REQUIRED_PREFIXES` in `daylily-omics-references`. |
| REF-002 | Agent C, reference verifier | Harden Python verifier to check exact required S3 object keys and required prefixes. | SUCCESS | `ReferenceBucketManager.verify_bucket` checks `head_object` for required keys and required conda prefix visibility. |
| REF-003 | Agent C, reference verifier | Mirror required object/prefix checks in `scripts/daylily-omics-references.sh` and README wording. | SUCCESS | Shell verifier uses `head-object`; README now states exact DAY-EC readiness object validation. |
| REF-T001 | Agent C, reference verifier | Add verifier tests for success and missing required object failures; run shell syntax check. | SUCCESS | `tests/test_manager.py` covers success and missing required object; `bash -n` passed. |
| VERIFY-001 | Orchestrator | Run focused local verification commands from the plan. | SUCCESS | DAY-EC focused suite passed: 104 tests. References verifier suite and shell syntax passed: 18 tests plus `bash -n`. |
| LIVE-001 | Orchestrator | Live AWS smoke or headnode check. | NOT_REQUIRED | User plan says no live AWS smoke is required for regression coverage. |
| FINAL-001 | Orchestrator | Confirm all non-live rows are terminal and objective is complete. | SUCCESS | All non-live rows are terminal; local regression objective complete. |

## Required Runtime Proofs

The DAY-EC readiness path must prove all of the following before workflow staging or launch:

- fresh `ubuntu` login-shell bootstrap
- `DAYLILY_EC_HEADNODE_BOOTSTRAPPED=1`
- `CONDA_DEFAULT_ENV=DAY-EC`
- `daylily-ec` on `PATH`
- `day-clone` on `PATH`
- `day-clone --list` succeeds
- `/fsx/runtime_assets/cached_envs/apptainer_1.4.5_amd64.deb`
- `/fsx/runtime_assets/tool_specific_resources/cromwell_87.jar`
- `/fsx/runtime_assets/tool_specific_resources/womtool_87.jar`
- `/fsx/runtime_assets/cached_envs/conda/`

## Verification Evidence

- 2026-05-26T05:34:05Z DAY-EC: `source ./activate && pytest tests/test_headnode_readiness.py tests/test_workflow.py tests/test_ssm_e2e_runner.py tests/test_script_entrypoints.py -q`
  - Result: `104 passed in 0.68s`
- 2026-05-26T05:34:05Z references: `pytest tests/test_manager.py -q && bash -n scripts/daylily-omics-references.sh`
  - Result: `18 passed in 0.02s`; shell syntax check passed.
- 2026-05-26T05:34:05Z diff hygiene:
  - DAY-EC `git diff --check`: passed.
  - daylily-omics-references `git diff --check`: passed.

## Closure

- All non-live ledger rows are terminal.
- Live AWS smoke was intentionally not run.
- Existing dirty worktree files from Gate 0 were preserved.
