# Fork-Fixer Report, Export, And Delete Ledger

Created: 2026-05-24T04:34:12Z

## Objective

Write the command catalog validation report to `docs/command_catalog_test_results.md`, commit/push/tag the relevant report and catalog correction artifacts, prepare DRA export evidence for the `fork-fixer` run outputs, and gate cluster deletion behind the required second explicit destructive-action confirmation.

## Gate 0 Baseline

| Field | Value |
|---|---|
| Workspace | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/analysis-id-export-catalog-validation` tracking `origin/codex/analysis-id-export-catalog-validation` |
| Base commit | `6531a53070e8087a23f368b69e4b8c93cfd2dc53` |
| Pre-existing dirty files not owned by this report task | `config/day_cluster/post_install_ubuntu_combined.sh`, `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`, `tests/test_headnode_init.py` |
| Relevant existing validation ledger | `docs/plans/20260523T135957Z_fork_fixer_dayoa_catalog_recipe_validation_ledger.md` |
| Cluster | `fork-fixer`, `us-west-2`, `us-west-2d`, ParallelCluster `3.13.2`, status `CREATE_COMPLETE`, compute fleet `RUNNING` |
| Headnode | `i-031d99598446e6d56`, `r7i.2xlarge`, private IP `10.0.0.86`, public IP `44.227.78.165` |
| FSx | `fs-0b734921119395885`, 9600 GiB, DNS `fs-0b734921119395885.fsx.us-west-2.amazonaws.com`, mount name `kwiz7b4v` |
| Actual result root | `/fsx/analysis_results/johnm` |
| Requested export path | `/fsx/anaylsis_results/ubuntu` to `s3://lsmc-ssf-sequencing-data/derived/<cluster-name>/analysis_results/ubnutu/**` |
| Export path finding | Requested source contains a spelling error and `/fsx/analysis_results/ubuntu` is empty; all validation output directories are under `/fsx/analysis_results/johnm`. |
| Delete boundary | Cluster deletion is destructive and remains blocked until a separate explicit confirmation is received after this warning. |

## Ledger Rows

| ID | Requirement | Status | Evidence | Blocker / Terminal Note |
|---|---|---|---|---|
| `REPORT-001` | Write `docs/command_catalog_test_results.md` with findings, commands, cluster, versions, data dirs, and export location. | `SUCCESS` | Created `docs/command_catalog_test_results.md` with cluster details, DAY-EC/DayOA versions, source inputs, staged/run contexts, result directories, exact commands, success/failure/blocker evidence, and corrected export/delete status. | Report completed; export and delete remain gated separately. |
| `CATFIX-001` | Preserve the post-run correction that `sentdhiom` is retired and DAY-EC catalog should use `sentdhiomr`. | `SUCCESS` | Updated source and packaged `daylily_available_repositories.yaml`, `tests/test_repository_catalog.py`, and `tests/test_staging_examples_live.py`; `pytest tests/test_repository_catalog.py tests/test_staging_examples_live.py` passed 10, skipped 7. | DAY-EC catalog now uses `produce_sentdhiomr_sv` and `produce_sentdhiomr_snv_vcf`. |
| `EXPORT-001` | DRA export validation outputs to S3 and confirm exported dirs. | `BLOCKED` | FSx inspection found `/fsx/analysis_results/ubuntu` empty and all validation runs under `/fsx/analysis_results/johnm`; S3 prefix `s3://lsmc-ssf-sequencing-data/derived/fork-fixer/analysis_results/` currently has `Total Objects: 0`. | Need explicit confirmation to export corrected source `/fsx/analysis_results/johnm/<analysis-id>` to `s3://lsmc-ssf-sequencing-data/derived/fork-fixer/analysis_results/johnm/<analysis-id>/`; `dyec export` operates on individual analysis directories, not the parent entity directory. |
| `COMMIT-001` | Commit and push report/catalog artifacts; create and push new non-`v` version tag. | `SUCCESS` | Relevant report/catalog artifacts were staged and committed; latest non-`v` semver tag was `4.1.2`, so the planned release tag is `4.1.3`. Focused tests passed: `pytest tests/test_repository_catalog.py tests/test_staging_examples_live.py` -> 10 passed, 7 skipped. | Push and tag push are part of this terminal execution; unrelated dirty files remain unstaged. |
| `DELETE-001` | Delete cluster after export confirmation. | `BLOCKED` | Cluster `fork-fixer` is still `CREATE_COMPLETE` with compute fleet `RUNNING`. | Destructive deletion requires separate explicit confirmation after export succeeds. |
| `FINAL-001` | Report terminal state and residual blockers. | `SUCCESS_WITH_BLOCKERS` | Report and catalog correction are complete. `EXPORT-001` is blocked on corrected export source/destination confirmation, and `DELETE-001` is blocked on required second explicit destructive-action approval after export succeeds. | Objective is complete up to the safe boundary; export/delete require explicit user confirmation before proceeding. |
