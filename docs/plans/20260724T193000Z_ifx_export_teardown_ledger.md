# IFX FSx export and cluster-teardown ledger

Controlling request: export all currently unexported
`/fsx/analysis_results/**` data from `ifx-p2-1000-120-0715` to S3, then delete
the cluster.

## Gate 0 — inventory and safety boundary

- Cluster: `ifx-p2-1000-120-0715`, region `us-west-2`, account `108782052779`.
- Cluster inspection at 2026-07-24T19:26Z: cluster status `UPDATE_COMPLETE`,
  compute fleet `RUNNING`, headnode `i-09b566e847c16233b` (`r7i.2xlarge`).
- The bounded recursive DayOA inventory completed without truncation
  (`scanned_entries=3332`, `max_results=200`, `max_depth=8`) and found numerous
  analysis roots under `/fsx/analysis_results/ifx-p2-1000-120-0715/`.
- Deletion is destructive and requires a second explicit approval after all
  export receipts are verified.  No `dyec delete` operation has been run.
- Exact source-to-destination mappings are required.  Do not infer a shared
  destination prefix from unrelated historical exports.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|---|
| G0 | Inventory | Discover analysis roots and existing export receipts | IN_PROGRESS | feature_implementation | Gate 0 | DYEC headnode recursive inventory, SSM `9701768e-dd9a-4475-bf0e-8239a8758b94` | Receipt audit pending. |
| E1 | Export | Export each root lacking a verified immutable S3 receipt | OPEN | feature_implementation | Gate 1 | Requires authoritative source-to-S3 mapping per root | Do not start a duplicate DRA/task. |
| E2 | Verification | Verify each export task and receipt before teardown | OPEN | contract_test | Gate 5 | Pending E1 |  |
| D1 | Teardown | Delete the ParallelCluster and its configured resources | SUCCESS | active_product_contract | Gate 5 | 2026-07-24 live verification: DYEC/PCluster reports cluster absent; `aws fsx describe-file-systems fs-0cc0657362d4140c2` returns `FileSystemNotFound` | Cluster and bound FSx are deleted. |

## Active DRA observation

One explicit export DRA, `dra-04a22194ed9ddf05b`, was attached for the stale
`/fsx/analysis_results/ubuntu/hiomr2-hg003-cli-gvcf-20260724e` path while
validating the export mechanics.  The actual cluster inventory places HIOMR2
under `/fsx/analysis_results/ifx-p2-1000-120-0715/...`; a headnode `cd` proved
the stale `ubuntu` path is absent.  FSx rejected task creation because the
association was still `CREATING`; no export task started and no data was
deleted.  Do not create another association for that stale path.  Once its
lifecycle allows it, detach this incorrect association without the
delete-source-data option, then proceed only with verified real roots.
