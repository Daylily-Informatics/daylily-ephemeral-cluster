# DYEC Max Count Repair Ledger

Date: 2026-06-16

Controlling request: repair DYEC create so CLI max-count values populate rendered cluster max counts, confirm bid costs, and update live `ultimarerun` partitions to allow 16 nodes per compute resource.

## Gate 0 Baseline

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-dev...origin/jem-dev`
- Initial dirty state after code inspection and focused edits started: `daylily_ec/aws/validation.py`, `daylily_ec/config/triplets.py`, `daylily_ec/workflow/create_cluster.py`, `tests/test_triplets.py`, `tests/test_workflow.py`.
- Live generated config inspected: `/Users/jmajor/.config/daylily/ultimarerun_cluster_20260616073903.yaml`.
- Live generated max-count baseline: 15 compute resources, all `MaxCount: 1`.
- Live generated spot-price baseline: all 15 compute resources have numeric `SpotPrice` values (`4.3357` through `10.1876`), so the bid calculation path ran.
- Safety boundary: update is capacity-affecting but not a destructive AWS deletion; user explicitly requested live `ultimarerun` update to 16 nodes per partition/resource.

## Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G0-001 | Baseline | Record repo state, generated config state, max-count evidence, and bid evidence. | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | `git status --short --branch`; parsed `/Users/jmajor/.config/daylily/ultimarerun_cluster_20260616073903.yaml`. |  | Baseline recorded. |
| FIX-001 | Create workflow | Make broad CLI max counts populate all matching subtype `REGSUB_MAX_COUNT_*` render keys unless a subtype has its own explicit set value. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `daylily_ec/config/triplets.py`; `daylily_ec/workflow/create_cluster.py`; smoke render from `/Users/jmajor/.config/daylily/ultimarerun_next_run_20260616073903.yaml` with broad counts set to `16` produced 15 resources with `MaxCount: 16`. |  | Create render and next-run persistence now expand broad max counts into subtype values. |
| VAL-001 | AWS validation | Make read-only validation/rendered quota path use the same broad-to-subtype max-count expansion. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `daylily_ec/aws/validation.py`; validation renderer also fixed to provide `REGSUB_S3_EXPORT_BUCKET` and require only mandatory render keys. |  | Validation renderer uses the same derived max-count logic and can render the `ultimarerun` next-run config. |
| TEST-001 | Tests | Add focused regression coverage for inherited subtype counts and explicit subtype override. | SUCCESS | contract_test | Gate 5 | orchestrator | `pytest tests/test_aws_validation.py tests/test_triplets.py tests/test_workflow.py -q` -> 157 passed; `python -m py_compile daylily_ec/config/triplets.py daylily_ec/workflow/create_cluster.py daylily_ec/aws/validation.py` -> pass. |  | Regression coverage added for inherited counts, explicit subtype override, validation render, and create workflow substitutions. |
| BID-001 | Bid costs | Confirm bid/max spot costs are being rendered correctly. | SUCCESS | config_or_startup_contract | Gate 5 | orchestrator | Baseline and post-update stored cluster YAML each have numeric `SpotPrice` for all 15 compute resources, range `4.3357` to `10.1876`; no `CALCULATE_MAX_SPOT_PRICE` remains in final cluster configs. |  | Spot bid caps appear correctly applied by `apply_spot_prices()` and were preserved during update. |
| LIVE-001 | Live cluster | Update live `ultimarerun` generated cluster config and ParallelCluster to `MaxCount: 16` for each compute resource while preserving spot prices. | SUCCESS | feature_implementation | Gate 5 | orchestrator | `AWS_PROFILE=lsmc pcluster update-cluster --cluster-name ultimarerun --region us-west-2 --cluster-configuration /Users/jmajor/.config/daylily/ultimarerun_live_cluster_max16_20260616T083650Z.yaml` accepted and reached `UPDATE_COMPLETE`; post-update stored config `/Users/jmajor/.config/daylily/ultimarerun_live_cluster_post_update_20260616T084146Z.yaml`. |  | Live cluster updated to `MaxCount: 16` across 15 compute resources. Dry-run/changeSet also showed pre-existing duplicate S3Access list-normalization noise for `lsmc-ssf-sequencing-data`; the applied file preserved the existing write-enabled entries. |
| VERIFY-001 | Live verification | Verify updated live cluster config/Slurm state reflects 16 nodes per compute resource. | SUCCESS | contract_test | Gate 5 | orchestrator | Post-update stored config: 15 resources, `max_counts [16]`, 15 numeric spot prices; SSM `sinfo` as `ubuntu` showed `i8` 16, `i128` 48, `i128nvme` 16, `i192` 48, `i192nvme` 48, `i384nvme` 48, `i192hugenvme` 16. |  | Live pcluster config and Slurm node inventory both reflect the requested capacity. |

## Final Status

- Terminal rows: 7/7.
- Objective complete: yes.
- Tests: `pytest tests/test_aws_validation.py tests/test_triplets.py tests/test_workflow.py -q` -> 157 passed.
- Live verification: `ultimarerun` `clusterStatus=UPDATE_COMPLETE`, `cloudFormationStackStatus=UPDATE_COMPLETE`, `computeFleetStatus=RUNNING`; Slurm `sinfo` reflects 16 nodes per compute resource.
