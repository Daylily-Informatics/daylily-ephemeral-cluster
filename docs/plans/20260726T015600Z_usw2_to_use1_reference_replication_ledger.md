# US West to US East reference-data replication ledger

Controlling request: while the existing cluster teardown proceeds, retain the
west-side S3 data and seed east-side DayOA reference and control-data buckets.

## Gate 0 — inventory and safety boundary

- AWS profile: `lsmc`; account: `108782052779`.
- Cluster teardown observed at `2026-07-26T01:56Z`: `ursa-m-rgx-f9b4-r3` in
  `DELETE_IN_PROGRESS`; its FSx `fs-0cea20d318ebfc179` was also
  `DELETE_IN_PROGRESS`, and its reference DRA `dra-059256d4bf26bb50b` was
  `DELETE_COMPLETE`.
- That CloudFormation stack has no S3 bucket resource.  The source buckets are
  external to the teardown and must not be deleted.
- Sources: `s3://lsmc-dayoa-references-usw2/` and
  `s3://lsmc-dayoa-control-data-usw2/`, both in `us-west-2`; the reference
  source uses AES256 default encryption and blocks all public access.
- Destination inventory found neither `lsmc-dayoa-references-use1` nor
  `lsmc-dayoa-control-data-use1`.  Therefore no east-side bucket deletion is
  needed or performed.
- Source-to-destination mapping is explicit and intentionally limited to the
  two DayOA data buckets: `references-usw2 -> references-use1` and
  `control-data-usw2 -> control-data-use1`.  Runtime assets reside under the
  references source and are included by that copy.
- The west reference bucket also has `BucketOwnerEnforced` ownership, project
  tag `aws-parallelcluster-project=dayoa-references`, and a non-public
  BioCompute list/location policy.  The equivalent east policy was applied
  with its resource changed to `lsmc-dayoa-references-use1`; its verified
  policy status remains non-public.  The west FSx auto-import notification is
  intentionally not copied because it targets a west-region SNS/FSx
  association and there is no confirmed east counterpart.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|---|
| G0 | Inventory | Establish source, destination, and concurrent-teardown boundary | SUCCESS | feature_implementation | Gate 0 | Live `list-buckets`, locations, stack resources, and source bucket policy checks | Two explicit sources; no east targets existed. |
| R1 | S3 | Create and configure east reference bucket | SUCCESS | feature_implementation | Gate 1 | Created `lsmc-dayoa-references-use1`; live location `us-east-1`, AES256 default encryption, and all public-access blocks are true | Private destination posture matches the source baseline. |
| R2 | S3 | Copy west reference data to east without deleting west objects | IN_PROGRESS | feature_implementation | Gate 1 | Persistent local tmux `reference_replication_20260726`; live PID 94242 running `aws s3 sync` with no `--delete`; destination listing already returns copied source keys | Includes `runtime_assets/` and controls under the reference tree. |
| C1 | S3 | Create and configure east control-data bucket | OPEN | feature_implementation | Gate 1 | Target `lsmc-dayoa-control-data-use1` | Separate bucket because cluster configs mount it independently. |
| C2 | S3 | Copy west control data to east without deleting west objects | OPEN | feature_implementation | Gate 1 | Explicit source/target mapping | No `--delete` flag is permitted. |
| V1 | Verification | Verify bucket regions, policy posture, and object-count/byte parity | OPEN | contract_test | Gate 5 | Pending sync results | Must not claim version parity because sources have no versioning enabled. |
| T1 | Teardown observation | Confirm in-progress cluster/FSx teardown reaches terminal AWS state | IN_PROGRESS | active_product_contract | Gate 5 | Stack `ursa-m-rgx-f9b4-r3`, FSx `fs-0cea20d318ebfc179` | Observation only; no teardown command is issued by this replication work. |
