# DYEC Sacct EC2 Scan Ledger

Created: 2026-06-02T08:36:43Z

## Gate 0: Inventory Freeze

Controlling request: implement `dyec create --scan-slurm-accounting-db` so `create` can scan the target region/VPC for reusable Slurm accounting database hosts, select one interactively, skip cleanly when none are usable, and never create/delete/repair/mutate AWS resources through this scan path.

Repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`

Branch: `codex/dyec515-full-catalog-20260531`

Baseline status:

```text
## codex/dyec515-full-catalog-20260531...origin/codex/dyec515-full-catalog-20260531
 M AGENTS.md
 M docs/plans/20260601T144201Z_dyec_516_517_release_train_ledger.md
?? docs/plans/20260601T165015Z_hg003_illumina_run_catalog.fastqs.tsv
?? docs/plans/20260601T165015Z_hg003_illumina_run_catalog.json
?? docs/plans/20260601T165015Z_hg003_illumina_run_catalog.md
?? docs/plans/20260601T165015Z_hg003_illumina_run_catalog.runs.tsv
?? docs/plans/20260601T165015Z_hg003_illumina_run_catalog.sample_rows.tsv
?? docs/plans/20260601T165015Z_hg003_illumina_run_catalog.samplesheets.tsv
?? docs/plans/20260601T165015Z_hg003_illumina_run_catalog_ledger.md
?? docs/plans/20260601T165015Z_hg003_illumina_s3_catalog.py
?? docs/plans/20260601T185255Z_dyec5117_ilmn_run_mount_ledger.md
?? docs/plans/20260601T234556Z_bcl_l003_25b_shard_experiment/
```

Pre-existing dirty or untracked files not owned by this work:

- `AGENTS.md`
- `docs/plans/20260601T144201Z_dyec_516_517_release_train_ledger.md`
- `docs/plans/20260601T165015Z_hg003_illumina_run_catalog*`
- `docs/plans/20260601T185255Z_dyec5117_ilmn_run_mount_ledger.md`
- `docs/plans/20260601T234556Z_bcl_l003_25b_shard_experiment/`

Inventory commands:

- `git status --short --branch`
- `wc -l daylily_ec/aws/slurm_accounting.py daylily_ec/workflow/create_cluster.py daylily_ec/cli.py tests/test_slurm_accounting.py tests/test_cli_registry_v2.py tests/test_workflow.py tests/test_renderer.py tests/test_triplets.py`
- `rg -n "slurm_accounting|create_slurm_accounting|run_create_workflow|scan" daylily_ec/aws/slurm_accounting.py daylily_ec/workflow/create_cluster.py daylily_ec/cli.py tests/test_slurm_accounting.py tests/test_cli_registry_v2.py tests/test_workflow.py -S`

Inspection facts:

- Existing `dyec create --create-slurm-accounting-db` is wired through `run_create_workflow(..., create_slurm_accounting_db=...)`.
- Existing `dyec slurm-accounting ensure` creates/selects the committed DayEC accounting stack; this helper is tracked and appeared in commit `cb744715` / tag `5.1.9`.
- Existing Slurm accounting render path already injects `HeadNode.Networking.AdditionalSecurityGroups` and `Scheduling.SlurmSettings.Database` from a `SlurmAccountingDb`.
- Existing state model already records selected Slurm accounting fields.

Assumptions and limits:

- “Usable” means all ParallelCluster database fields can be resolved: URI, database, username, password secret ARN, and client security group.
- Broad EC2 scan results are advisory unless they can be correlated to the same complete metadata contract.
- No live AWS mutation is approved or needed for this local implementation.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| SCAN-001 | CLI | Add `dyec create --scan-slurm-accounting-db`, forward to workflow, and reject create/scan conflicts. | SUCCESS | feature_implementation | Gate 1 | Codex | `tests/test_cli_registry_v2.py`; `pytest ... -q` passed | Missing reuse-only CLI option | Added option, forwarding, and direct scan/create conflict rejection. |
| SCAN-002 | AWS discovery | Add read-only EC2 scan that prefers DayEC-tagged accounting hosts, limits selectable candidates to target VPC/region, and keeps broad EC2 probes advisory unless complete metadata is resolvable. | SUCCESS | feature_implementation | Gate 1 | Codex | `daylily_ec/aws/slurm_accounting.py`; `tests/test_slurm_accounting.py`; `pytest ... -q` passed | Existing helper only selected/created CloudFormation accounting stacks | Added read-only same-VPC EC2 scan with CloudFormation output correlation and advisory non-selectable broad candidates. |
| SCAN-003 | Workflow | Run scan after baseline VPC/subnet resolution; select or skip interactively; warn and continue when no usable candidate or when non-interactive. | SUCCESS | feature_implementation | Gate 1 | Codex | `daylily_ec/workflow/create_cluster.py`; `tests/test_workflow.py`; `pytest ... -q` passed | `create` had no reuse discovery path | Added scan branch after VPC/subnet resolution with selector, skip, no-candidate warning, and non-interactive skip warning. |
| SCAN-004 | State/render | Preserve existing accounting render and state persistence when a scanned candidate is selected. | SUCCESS | feature_implementation | Gate 1 | Codex | `tests/test_workflow.py`; `tests/test_renderer.py`; `pytest ... -q` passed | Selected reusable DB needed to feed existing render/state contract | Selected candidates reuse the existing `SlurmAccountingDb` render blocks and persisted next-run/state fields. |
| SCAN-005 | Tests | Add/update focused unit, CLI, workflow, renderer, and triplet tests; run requested focused pytest command. | SUCCESS | contract_test | Gate 5 | Codex | `source ./activate && pytest tests/test_slurm_accounting.py tests/test_cli_registry_v2.py tests/test_workflow.py tests/test_renderer.py tests/test_triplets.py -q` -> 268 passed; `source ./activate && ruff check ...` -> All checks passed | New option required coverage across scan, CLI, workflow, and regressions | Focused verification passed. |

## Verification

- `git diff --check`: passed with no output.
- `source ./activate && pytest tests/test_slurm_accounting.py tests/test_cli_registry_v2.py tests/test_workflow.py tests/test_renderer.py tests/test_triplets.py -q`: `268 passed in 3.96s`.
- `source ./activate && ruff check daylily_ec/aws/slurm_accounting.py daylily_ec/workflow/create_cluster.py daylily_ec/cli.py daylily_ec/create.py tests/test_slurm_accounting.py tests/test_cli_registry_v2.py tests/test_workflow.py`: `All checks passed!`.

All tracking rows are terminal. Objective complete.
