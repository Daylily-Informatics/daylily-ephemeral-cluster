# ParallelCluster 3.15.0 Pinned Upgrade Ledger

Controlling plan: user request in Codex thread on 2026-06-07.
Ledger path: `docs/plans/20260607T120236Z_parallelcluster_3_15_0_upgrade_ledger.md`

## Gate 0 Baseline

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-dev...origin/jem-dev`
- Pre-existing untracked files:
  - `.cf`
  - `.may11cf`
  - `docs/plans/20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/ilmn20x_dra_export_20260607T004343Z/`
  - `docs/plans/20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/ilmn20x_dra_export_20260607T004414Z/`
  - `docs/plans/20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/ilmn20x_realcopy_dra_export_20260607T010234Z/`
  - `docs/plans/20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/ont_solo_dra_export_20260607T010531Z/`
  - `docs/smn12_and_friends_solo_Ailmn_ds_files_multiqc.md`
- No AWS-mutating commands are allowed. `pcluster create-cluster`, `pcluster update-cluster`, `pcluster delete-cluster`, and `pcluster create-cluster --dryrun true` are prohibited for this pass.
- Existing supported activation probe:
  - `source ./activate` entered `DAY-EC` at `/Users/jmajor/miniconda3/envs/DAY-EC`.
  - `python --version` -> `Python 3.11.15`
  - `python -m pip --version` -> `pip 26.1.2` from the DAY-EC environment.
  - `which pcluster` -> `/Users/jmajor/miniconda3/envs/DAY-EC/bin/pcluster`
  - `pcluster version` -> `{"version": "3.13.2"}`
- Active dependency manager: Conda operator environment plus editable pip install from `pyproject.toml`. No active root lock file was found.
- External compatibility facts checked before implementation:
  - PyPI `aws-parallelcluster==3.15.0` declares `Requires-Python >=3.9`.
  - PyPI `aws-parallelcluster==3.15.0` declares `boto3>=1.39.4`.
  - AWS release notes list ParallelCluster `3.15.0` on 2026-03-23.
  - AWS ParallelCluster v3 CLI docs do not list `validate-cluster-configuration`; AWS documents `create-cluster --dryrun true` as validation, but that command is prohibited here.

## Inspected Files

| File or path | Why it mattered |
|---|---|
| `AGENTS.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md` | Shell, AWS safety, DayOA, no-fallback, and ledger rules. |
| `pyproject.toml`, `environment.yaml`, `activate`, `bin/init_dayec`, `daylily_ec/resources/payload/environment.yaml` | Active dependency and install surfaces. |
| `bin/legacy/daylily-create-ephemeral-cluster.bash`, `daylily_ec/resources/payload/quarantine/bin/legacy/daylily-create-ephemeral-cluster.bash` | Hard-coded expected ParallelCluster version guards. |
| `daylily_ec/pcluster/runner.py`, `tests/test_runner.py` | pcluster subprocess wrapper and command behavior tests. |
| `daylily_ec/render/renderer.py`, `daylily_ec/workflow/create_cluster.py`, `daylily_ec/aws/validation.py`, `config/day_cluster/*.yaml` | Render path and template placeholder inventory. |
| `README.md`, `README.md.bland`, `docs/DAY_EC_ENVIRONMENT.md`, `docs/pip_install.md`, `docs/quickest_start.md`, `docs/aws_setup.md`, `docs/testing_and_debugging.md` | User-facing install and validation docs. |
| `REFACTOR_SPEC.md`, `day-ec_scripts.log`, `scripts/_clusters.txt`, `scripts/_delete.txt`, historical reports/assets under `docs/` | Current-looking notes and historical `3.13.2` evidence classification. |
| `.github/workflows/update-badges.yml`, `setup.py`, `.gitignore`, `tests/test_environment_contract.py`, `tests/test_activate.py`, `tests/test_resources_extraction.py` | CI/install/test surfaces and generated-file boundaries. |

## Config Template Inventory

Direct template validation is blocked by unresolved `REGSUB_*` placeholders unless a rendered config is produced from explicit DayEC config.

| Template | Placeholder count | Placeholders |
|---|---:|---|
| `config/day_cluster/prod_cluster.yaml` | 27 | `REGSUB_ALLOCATION_STRATEGY`, `REGSUB_AWS_ACCOUNT_ID`, `REGSUB_CLUSTER_NAME`, `REGSUB_DAYLILY_GIT_DEETS`, `REGSUB_DELETE_LOCAL_ROOT`, `REGSUB_DETAILED_MONITORING`, `REGSUB_ENFORCE_BUDGET`, `REGSUB_FSX_SIZE`, `REGSUB_HEADNODE_INSTANCE_TYPE`, `REGSUB_MAX_COUNT_128I`, `REGSUB_MAX_COUNT_192I`, `REGSUB_MAX_COUNT_8I`, `REGSUB_PRIVATE_SUBNET`, `REGSUB_PROJECT`, `REGSUB_PUB_SUBNET`, `REGSUB_REGION`, `REGSUB_S3_BUCKET_INIT`, `REGSUB_S3_CONTROL_DATA_BUCKET`, `REGSUB_S3_EXPORT_BUCKET`, `REGSUB_S3_IAM_POLICY`, `REGSUB_S3_REFERENCE_BUCKET`, `REGSUB_S3_REFERENCE_URI`, `REGSUB_S3_STAGE_BUCKET`, `REGSUB_SAVE_FSX`, `REGSUB_SLURM_ACCOUNTING_DATABASE`, `REGSUB_SLURM_ACCOUNTING_HEADNODE_NETWORKING`, `REGSUB_USERNAME` |
| `config/day_cluster/prod_cluster_variant.yaml` | 22 | `REGSUB_ALLOCATION_STRATEGY`, `REGSUB_AWS_ACCOUNT_ID`, `REGSUB_CLUSTER_NAME`, `REGSUB_DELETE_LOCAL_ROOT`, `REGSUB_DETAILED_MONITORING`, `REGSUB_ENFORCE_BUDGET`, `REGSUB_FSX_SIZE`, `REGSUB_PRIVATE_SUBNET`, `REGSUB_PROJECT`, `REGSUB_PUB_SUBNET`, `REGSUB_REGION`, `REGSUB_S3_BUCKET_INIT`, `REGSUB_S3_CONTROL_DATA_BUCKET`, `REGSUB_S3_EXPORT_BUCKET`, `REGSUB_S3_IAM_POLICY`, `REGSUB_S3_REFERENCE_BUCKET`, `REGSUB_S3_REFERENCE_URI`, `REGSUB_S3_STAGE_BUCKET`, `REGSUB_SAVE_FSX`, `REGSUB_SLURM_ACCOUNTING_DATABASE`, `REGSUB_SLURM_ACCOUNTING_HEADNODE_NETWORKING`, `REGSUB_USERNAME` |
| `config/day_cluster/prod_cluster_dragen.yaml` | 27 | `REGSUB_ALLOCATION_STRATEGY`, `REGSUB_AWS_ACCOUNT_ID`, `REGSUB_CLUSTER_NAME`, `REGSUB_DAYLILY_GIT_DEETS`, `REGSUB_DELETE_LOCAL_ROOT`, `REGSUB_DETAILED_MONITORING`, `REGSUB_ENFORCE_BUDGET`, `REGSUB_FSX_SIZE`, `REGSUB_HEADNODE_INSTANCE_TYPE`, `REGSUB_MAX_COUNT_128I`, `REGSUB_MAX_COUNT_192I`, `REGSUB_MAX_COUNT_8I`, `REGSUB_PRIVATE_SUBNET`, `REGSUB_PROJECT`, `REGSUB_PUB_SUBNET`, `REGSUB_REGION`, `REGSUB_S3_BUCKET_INIT`, `REGSUB_S3_CONTROL_DATA_BUCKET`, `REGSUB_S3_EXPORT_BUCKET`, `REGSUB_S3_IAM_POLICY`, `REGSUB_S3_REFERENCE_BUCKET`, `REGSUB_S3_REFERENCE_URI`, `REGSUB_S3_STAGE_BUCKET`, `REGSUB_SAVE_FSX`, `REGSUB_SLURM_ACCOUNTING_DATABASE`, `REGSUB_SLURM_ACCOUNTING_HEADNODE_NETWORKING`, `REGSUB_USERNAME` |

## Control Ledger

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record branch, dirty/untracked state, commands, local tool versions, inspected files, and no-AWS-mutation boundary. | SUCCESS | config_or_startup_contract | Gate 0 | Agent 1 | Gate 0 sections above. |  | Baseline recorded before edits. |
| DEP-001 | Dependency pins | Change active ParallelCluster pin to exactly `aws-parallelcluster==3.15.0`; update adjacent comments for 3.15. | SUCCESS | config_or_startup_contract | Gate 1 | Agent 2 | `pyproject.toml` now pins `aws-parallelcluster==3.15.0`; `tests/test_environment_contract.py::test_pyproject_pins_parallelcluster_exactly` covers exact pin. |  | Active pin updated without a lock-file change because no active root lock file exists. |
| ENV-001 | Local install | Refresh DAY-EC through existing Conda/editable install path and verify env-local `pcluster version`. | SUCCESS | config_or_startup_contract | Gate 2 | Agent 3 | `python -m pip install --upgrade pip`; `python -m pip install -e .`; final `command -v pcluster` -> `/Users/jmajor/miniconda3/envs/DAY-EC/bin/pcluster`; `pcluster version` -> `3.15.0`. | Fresh activation initially let `/opt/homebrew/bin` precede `DAY-EC/bin`, resolving global `pcluster 3.13.2`. | `activate` now requires `CONDA_PREFIX/bin` and prepends it. Pip reported an `awscli`/`jmespath` resolver warning, but `aws --version` still runs in DAY-EC. |
| SCRIPT-001 | Script guards | Update active expected-version guards from `3.13.2` to `3.15.0`. | SUCCESS | config_or_startup_contract | Gate 1 | Agent 4 | `bin/legacy/daylily-create-ephemeral-cluster.bash` and packaged quarantine copy now set `expected_pcluster_version="3.15.0"`. |  | Covered by `test_legacy_parallelcluster_version_guards_match_active_pin`. |
| DOC-001 | Documentation | Document target version, pinned install, safe validation, and non-upgrade of live clusters. | SUCCESS | historical_docs_only | Gate 1 | Agent 5 | Updated `README.md`, `README.md.bland`, `docs/DAY_EC_ENVIRONMENT.md`, `docs/pip_install.md`, `docs/quickest_start.md`, `docs/aws_setup.md`, `docs/testing_and_debugging.md`. |  | Docs state this tooling pass does not create, update, or delete live clusters. |
| CFG-001 | Config templates | Inventory templates/placeholders and make no topology/config edits. | SUCCESS | config_or_startup_contract | Gate 0 | Agent 6 | Config Template Inventory section. |  | No topology, queue, subnet, FSx, IAM, or Slurm settings changed. |
| VALID-001 | Validation command | Attempt only `pcluster validate-cluster-configuration --cluster-configuration <path> --region us-west-2` after upgrade; block if absent. | BLOCKED | legitimate_safety_handling | Gate 3 | Agent 7 | Command exited 2: `invalid choice: 'validate-cluster-configuration'`; available operations did not include validation. | ParallelCluster 3.15.0 CLI does not expose the requested command. | Did not run `pcluster create-cluster --dryrun true` or any substitute AWS-mutating command. |
| HIST-001 | Historical references | Leave historical `3.13.2` run evidence unchanged or label current-looking notes accurately. | SUCCESS | historical_docs_only | Gate 1 | Agent 8 | Active/current-looking `REFACTOR_SPEC.md` and `day-ec_scripts.log` were updated. `git grep -l -F "3.13.2"` now returns only historical inventories, old run reports, raw cluster describe outputs, `scripts/_clusters.txt`, `scripts/_delete.txt`, and `tmp/aws_orphan_inventory_lsmc_20260520.json`. |  | Historical cluster/run provenance was preserved. |
| TEST-001 | Tests | Add/update exact-pin and guard consistency tests; run focused tests. | SUCCESS | contract_test | Gate 4 | Agent 9 | `python -m pytest tests/test_environment_contract.py tests/test_activate.py tests/test_resources_extraction.py tests/test_runner.py -q` -> 36 passed. |  | Added activation regression coverage for env-local `pcluster` precedence. |
| REPORT-001 | Final report | Summarize files changed, commands, outputs, blockers, validation status, and next safe manual command. | SUCCESS | plan_amendment | Gate 5 | Agent 10 | This ledger final status and Codex final response. |  | All rows are terminal; config validation is blocked by unavailable CLI command. |

## Command Log

| Command | Result |
|---|---|
| `git status --short --branch` | Baseline branch and pre-existing untracked files recorded above. |
| `source ./activate; python --version; python -m pip --version; which pcluster; pcluster version` | DAY-EC Python 3.11.15, pip 26.1.2, env-local `pcluster`, version `3.13.2`. |
| `git ls-files -z | xargs -0 rg -n -i "aws-parallelcluster|parallelcluster|pcluster|3\\.13\\.2|3\\.13|3\\.15|validate-cluster-configuration"` | Initial sweep found active pin/guard plus historical evidence references. |
| `python3 -c '<placeholder inventory script>'` | Recorded unresolved template placeholders. |
| `python -m pip install --upgrade pip` | Pip already satisfied at `26.1.2` in DAY-EC. |
| `python -m pip install -e .` | Installed editable `daylily-ephemeral-cluster` with `aws-parallelcluster-3.15.0`; uninstalled `aws-parallelcluster-3.13.2`. Pip warning: `awscli 2.34.29 requires jmespath<1.1.0,>=0.7.1, but you have jmespath 1.1.0`. |
| `source ./activate; command -v pcluster; python -c "import pcluster, sys; ..."; pcluster version` | Before activation patch, fresh shell resolved `/opt/homebrew/bin/pcluster` and reported `3.13.2`; after patch, resolved `/Users/jmajor/miniconda3/envs/DAY-EC/bin/pcluster`, imported from DAY-EC Python, and reported `3.15.0`. |
| `pcluster validate-cluster-configuration --cluster-configuration config/day_cluster/prod_cluster.yaml --region us-west-2` | Safe validation attempted after upgrade; exited 2 because `validate-cluster-configuration` is not a valid pcluster operation in 3.15.0. |
| `python -m pytest tests/test_environment_contract.py tests/test_activate.py tests/test_resources_extraction.py tests/test_runner.py -q` | 36 passed in 9.70s. |
| `git grep -n -F "3.13.2" -- <active files>` | No active/current target hits after updates. |
| `git grep -l -F "3.13.2" -- .` | Remaining exact hits are historical inventories, old run reports, raw cluster describe outputs, `scripts/_clusters.txt`, `scripts/_delete.txt`, and `tmp/aws_orphan_inventory_lsmc_20260520.json`. |
| `git diff --check` | Clean. |
| `source ./activate; command -v aws; aws --version; python -c "import jmespath; print(jmespath.__version__)"` | `/Users/jmajor/miniconda3/envs/DAY-EC/bin/aws`; `aws-cli/2.34.29 Python/3.11.15 Darwin/25.5.0 source/arm64`; `jmespath 1.1.0`. |
| `git status --short --branch` | Final modified files include dependency/docs/tests/activation/legacy guards plus this ledger. Pre-existing unrelated untracked files remain untouched. |

## Final Status

All ledger rows are terminal. The repo and local DAY-EC tooling now target exactly `aws-parallelcluster==3.15.0`, and fresh `source ./activate` resolves env-local `pcluster` reporting `3.15.0`.

Config validation was attempted safely and is blocked because `pcluster validate-cluster-configuration` is not available in ParallelCluster 3.15.0. No AWS-mutating command was run, and this pass did not apply any upgrade to an existing live cluster.
