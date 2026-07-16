# DYEC Budget Enforcement Ledger

Created: 2026-07-03T06:45:34Z

## Gate 0 Inventory Freeze

- Controlling request: implement default-on DYEC budget enforcement with `RnD` bypass, required `sbatch --comment`, exact budget matching, S3 budget tag allow-list, and DYEC launch project override verification.
- Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260703T064534Z_dyec_budget_enforcement_ledger.md`
- Primary repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Primary repo head: `jem-dev` at `633eca30`
- Primary repo baseline status: unowned modified docs in `AGENTS.md`, `README.md`, `docs/cli_reference.md`, `docs/monitoring_and_troubleshooting.md`, `docs/operations.md`, `docs/overview.md`, `docs/quickest_start.md`
- Read-only verification repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA repo head: `jem-dev` at `79c5689`, ahead of origin by 1, with unrelated dirty workflow/docs changes left untouched.
- Gate 0 source facts:
  - `daylily_ec/aws/budgets.py` creates `daylily-global` and per-cluster budgets, writes `runtime_assets/budget_tags/pcluster-project-budget-tags.tsv`, and previously treated budget list failures as missing budgets.
  - `daylily_ec/workflow/create_cluster.py` publishes `config/day_cluster/post_install_ubuntu_combined.sh`, `config/day_cluster/sbatch`, and `sleep_test.sh` to `s3://<reference>/runtime_assets/cluster_boot_config` before rendering cluster YAML.
  - `config/day_cluster/post_install_ubuntu_combined.sh` verifies the S3-staged `sbatch` checksum, moves real Slurm binaries under `/opt/slurm/sbin`, installs `/opt/slurm/bin/sbatch`, links `/opt/slurm/bin/srun` to it, and keeps compute/headnode tag propagation through prolog/epilog and `check_tags.sh`.
  - `config/day_cluster/sbatch` already parses `--comment` weakly, checks `/fsx/references/runtime_assets/budget_tags/pcluster-project-budget-tags.tsv`, queries AWS Budgets, but continued on missing/invalid/exceeded budget states.
  - DayOA Slurm profile submits `sbatch ... --comment "$DAY_PROJECT"` and `dyoainit` accepts `--project`, exporting `DAY_PROJECT`.
  - DYEC `workflow launch` and `samples run` already expose `--project`; tests/docs need to make that contract explicit.
- Live-system limits: no live cluster creation, AWS budget mutation, or Slurm job submission is approved in this thread; local implementation and tests only.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| ORCH-001 | Ledger | Record Gate 0 inventory, dirty baseline, row ownership, and final counts. | SUCCESS | feature_implementation | Gate 0 | orchestrator | This ledger; final status count 10 SUCCESS / 0 working rows. |  | Gate 0 and terminal evidence recorded; no live AWS cluster creation, budget mutation outside mocked tests, or Slurm submission was run. |
| A-001 | BudgetManager | Make budget existence exact/idempotent and fail hard on API errors instead of treating errors as missing budgets. | SUCCESS | feature_implementation | Gate 1 | Agent A | `daylily_ec/aws/budgets.py`; `pytest tests/test_budgets.py -q -> 38 passed`. |  | `budget_exists()` now uses exact `describe_budget`, returns false only for not found, and raises other API failures. |
| A-002 | BudgetManager | Align cluster/project budget name with rendered project/comment string and update S3 TSV before cluster launch. | SUCCESS | feature_implementation | Gate 1 | Agent A | `daylily_ec/workflow/create_cluster.py`, `daylily_ec/aws/budgets.py`; focused workflow tests passed. |  | `dyec create` now ensures global/project budgets and upserts the S3 allow-list before render/dry-run/create; project budget name matches the rendered project string. |
| A-003 | DYEC Create | Add `--disable-budget-enforcement` and `--budget-project`; default enforcement on and project to cluster name. | SUCCESS | feature_implementation | Gate 1 | Agent A | `daylily_ec/cli.py`, config templates; `tests/test_cli_registry_v2.py`, `tests/test_workflow.py`. |  | CLI flags added; default budget project resolves to cluster name and enforcement resolves to `true` unless disabled. |
| A-004 | Config Defaults | Update generated noninteractive cluster configs and validation render defaults to avoid silent `skip`. | SUCCESS | config_or_startup_contract | Gate 2 | Agent A | `daylily_ec/config/cluster_requests.py`, `daylily_ec/aws/validation.py`, `tests/test_cluster_request_config.py`, `tests/test_renderer.py`. |  | Generated configs and validation substitutions render `budget_project` and default `enforce_budget=true`. |
| B-001 | Wrapper | Require `--comment`, implement `RnD` bypass, `skip` mode, strict budget allow-list and AWS budget gate. | SUCCESS | feature_implementation | Gate 1 | Agent B | `config/day_cluster/sbatch`; `pytest tests/test_sbatch_wrapper.py -q -> 9 passed`; `bash -n config/day_cluster/sbatch`. |  | Wrapper fails missing comments, allows exact `RnD`, honors disabled enforcement while still requiring comment, and blocks missing/unauthorized/missing-budget/exceeded-budget projects with Ursa URL stderr. |
| B-002 | Bootstrap | Mirror wrapper into packaged payload and refresh `sbatch_wrapper_sha256` for S3-staged install. | SUCCESS | config_or_startup_contract | Gate 2 | Agent B | `daylily_ec/resources/payload/config/day_cluster/sbatch`; checksum `f9c437528235435c0c8dc47e19ce664df56fd54df9d45f8de45fb91d60aaa037`; `cmp -s` source vs payload; `bash -n` both bootstrap scripts. |  | Source and packaged wrappers match and both post-install scripts verify the new wrapper checksum. |
| C-001 | DayOA | Verify DayOA `DAY_PROJECT` reaches `sbatch --comment` and DYEC launch `--project` remains the override surface. | SUCCESS | contract_test | Gate 1 | Agent C | DayOA `/Users/jmajor/projects/lsmc/daylily-omics-analysis/config/day_profiles/slurm/templates/config.yaml` contains `sbatch ... --comment "$DAY_PROJECT"`; `tests/test_cli_registry_v2.py`, `tests/test_script_entrypoints.py`. |  | `dyec workflow launch --project` and `dyec samples run --project` forward the project; generated launch script calls `dyoainit --project project-alpha`. |
| D-001 | Tests | Add focused tests for budget manager, create/render defaults, wrapper behavior, checksum/staging, and project override. | SUCCESS | contract_test | Gate 5 | Agent D | `pytest tests/test_budgets.py tests/test_cluster_request_config.py tests/test_cli_registry_v2.py tests/test_workflow.py tests/test_sbatch_wrapper.py tests/test_headnode_init.py tests/test_script_entrypoints.py -q -> 294 passed`; rerun subsets after final edits: 277 passed, 43 passed, 38 passed. |  | Focused regression coverage added for the requested behavior; no live cluster or job submission used. |
| D-002 | Docs | Document default-on enforcement, disable flag, project override, `RnD`, and Ursa budget URL. | SUCCESS | feature_implementation | Gate 5 | Agent D | `README.md`, `docs/cli_reference.md`, `docs/operations.md`; `git diff --check -> clean`. |  | Docs describe default-on enforcement, `--disable-budget-enforcement`, `--budget-project`, DayOA launch `--project`, exact `RnD`, and the Ursa budget monitor URL. |

## Final Terminal Report

Terminal status: 10 SUCCESS, 0 OPEN, 0 IN_PROGRESS, 0 ATTEMPTING_BUGFIX, 0 BLOCKED, 0 FAIL.

Validation evidence:

- `source ./activate && pytest tests/test_budgets.py tests/test_cluster_request_config.py tests/test_cli_registry_v2.py tests/test_workflow.py tests/test_sbatch_wrapper.py tests/test_headnode_init.py tests/test_script_entrypoints.py -q` -> 294 passed.
- After final cleanup, `source ./activate && pytest tests/test_budgets.py tests/test_cli_registry_v2.py tests/test_workflow.py tests/test_sbatch_wrapper.py tests/test_script_entrypoints.py -q` -> 277 passed.
- After final cleanup, `source ./activate && pytest tests/test_cluster_request_config.py tests/test_renderer.py tests/test_headnode_init.py -q` -> 43 passed.
- After final cleanup, `source ./activate && pytest tests/test_budgets.py -q` -> 38 passed.
- `bash -n` passed for source and packaged `sbatch` wrappers and post-install scripts.
- `shasum -a 256 config/day_cluster/sbatch` and packaged payload wrapper both produced `f9c437528235435c0c8dc47e19ce664df56fd54df9d45f8de45fb91d60aaa037`.
- `cmp -s config/day_cluster/sbatch daylily_ec/resources/payload/config/day_cluster/sbatch` succeeded.
- `git diff --check` passed.

Live-system boundary: no live cluster creation, AWS Budget mutation against real AWS, or Slurm job submission was run; all budget and wrapper behavior was validated through local tests and fixtures.
