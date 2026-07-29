# DayOA 13.0.76 to DYEC Pin and Self-Pin Release Train

## Control Ledger

Controlling plan: this ledger
Ledger path: `docs/plans/20260729T113042Z_dayoa_13076_dyec_release_train_ledger.md`

Gate 0 baseline:

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `codex/hiomr2-catalog-repair`
- Baseline commit/tag: `e90a9e66723bd3fcb9c093de808d5c24d9e9dae2` / `15.0.22`
- Tracked state: clean and equal to `origin/codex/hiomr2-catalog-repair`.
- Preserved user-owned state: pre-existing untracked `bkup/`, `recordings/`,
  `tmp/`, `reports/`, historical `docs/plans/` artifacts, and root working
  files are outside this release and will not be staged.
- DayOA release source: remote annotated tag `13.0.76`, peeled to
  `896b07086fd5d406118f038bb79187cce54f2743`.
- DYEC release candidates: `15.0.23` and `15.0.24`; neither exists locally or
  on `origin` at Gate 0.
- Pin inventory: each command catalog has 28 active `13.0.71` references; each
  self-config has two active `15.0.21` references. Source and packaged copies
  are byte-identical at baseline.
- Release scope: repository files, focused local tests, branch pushes, and
  immutable annotated tags only. No AWS, cluster, budget, Slurm, or workflow
  mutation is part of this release train.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-000 | DYEC | Freeze branch, dirty state, remote DayOA provenance, candidate tags, and pin counts | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 baseline above; `git fetch`; `git status`; `git ls-remote`; `rg` counts; `cmp -s` |  | Baseline recorded without touching unrelated untracked files. |
| REL-001 | DYEC catalogs | Advance every active DayOA default and command tag to `13.0.76` in source and packaged catalogs | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | 28 replacements per catalog; source/package `cmp -s` RC 0; `git diff --check` RC 0 |  | All active DayOA defaults and command tags now resolve to `13.0.76`. |
| REL-002 | DYEC tests | Advance DayOA pin constants and exact remote release commit contract | SUCCESS | contract_test | Gate 5 | orchestrator | `python -m pytest tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_lsmc_bio_fork_contract.py -q` -> 236 passed |  | Catalog, CLI, and fork contracts accept the exact released tag and commit. |
| REL-003 | DYEC release | Commit and push the DayOA-pin release; create and push annotated tag `15.0.23` | IN_PROGRESS | feature_implementation | Gate 5 | orchestrator | Candidate tag verified unclaimed; release diff and focused tests complete |  |  |
| REL-004 | DYEC self-config | Advance both source and packaged DYEC self-pins to `15.0.23` | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Pending source diff and parity check |  |  |
| REL-005 | DYEC tests | Advance the self-pin contract and rerun focused validation | OPEN | contract_test | Gate 5 | orchestrator | Pending focused pytest result |  |  |
| REL-006 | DYEC release | Commit and push the self-pin release; create and push annotated tag `15.0.24` | OPEN | feature_implementation | Gate 5 | orchestrator | Candidate tag verified unclaimed |  |  |
| REL-007 | DYEC | Verify final branch equality, clean intended diff, annotated tag types, and remote peeled commits | OPEN | contract_test | Gate 5 | orchestrator | Pending final Git verification |  |  |

## Final Report

All rows terminal: no
Objective complete: no

Status counts:

- SUCCESS: 3
- IN_PROGRESS: 1
- OPEN: 4
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

Changed files:

- `config/daylily_pipeline_command_catalog.yaml`
- `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`
- `tests/test_repository_catalog.py`
- `tests/test_cli_registry_v2.py`
- `tests/test_lsmc_bio_fork_contract.py`
- this ledger

Validation:

- DayOA-pin focused suite: 236 passed.

Non-success terminal rows: none.

Residual risks: first and second DYEC release operations remain in progress.
