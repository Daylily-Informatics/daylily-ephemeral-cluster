# Bucket Contract Release Validation Ledger

Controlling plan: 15-agent bucket contract release and `bucketsamok` validation.
Ledger path: `docs/plans/20260526T185422Z_bucket_contract_release_validation_ledger.md`
Created: 2026-05-26T18:54:22Z

## Gate 0 Baseline

- DayEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- DayEC branch/head: `codex/analysis-id-export-catalog-validation`, `22fb2780a25c0777678692aadcfb26b49e97a766`
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayOA branch/head: `codex/tstclu411c-hybrid-env-python`, `1c147d70d8b1082d7dafa51fa074e736a321800b`
- DayRef repo: `/Users/jmajor/projects/daylily/daylily-omics-references`
- DayRef branch/head: `codex/headnode-readiness-reference-verifier`, `eca57742496496f545a1841e9d287f4a4ca4b851`
- Ursa repo: `/Users/jmajor/projects/lsmc/daylily-ursa`
- Ursa branch/head: `main`, `b22b2d230fbf7eb47c33133d2a3668858d7fc61d`, behind `origin/main` by 26 commits at Gate 0.
- AWS identity: `AWS_PROFILE=lsmc`, account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Existing cluster: `splitdra-ref-20260526`, `CREATE_COMPLETE`, headnode `i-0229ac1e34347920e`, FSx `fs-0e0e1ff3780f15432`.
- Replacement cluster: `bucketsamok` does not exist at Gate 0.
- Live DRAs on `splitdra-ref-20260526`: `/references/ -> s3://lsmc-dayoa-references-usw2`; `/control_data/genomic_data/organism_reads_slim/ -> s3://lsmc-dayoa-control-data-usw2/genomic_data/organism_reads_slim/`; `/control_data/genomic_data/organism_reads/ -> s3://lsmc-dayoa-control-data-usw2/genomic_data/organism_reads/`; `/run_dir_mounts/rawseq-pca100-smoke/ -> s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/`; `/staging/staged_external_sequencing_data/remote_stage_20260526T155039Z/ -> s3://lsmc-dayoa-staging-usw2/staging/staged_external_sequencing_data/remote_stage_20260526T155039Z/`.
- S3 evidence: references runtime assets `82,376` objects, `42,702,062,929` bytes; slim reads `26` objects, `101,475,761,473` bytes; `s3://lsmc-ssf-sequencing-data/staged_external_data/` empty; validation results prefix empty.
- Version evidence: DayEC latest local non-v tag line includes `4.1.16`; DayOA latest local non-v semver tag `1.0.38`; DayRef latest local tag `0.3.5`; Ursa latest local major tag `3.0.0`.
- Destructive actions blocked: stopping jobs, deleting `splitdra-ref-20260526`, deleting any bucket/prefix, or deleting `bucketsamok` later require separate second explicit approval.

## Control Ledger

| ID | Agent | Area | Requirement | Status | Category | Approval Gate | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| BKT-001 | Orchestrator | Gate 0 | Record repo, AWS, cluster, DRA, S3, and version baseline. | SUCCESS | feature_implementation | Gate 0 | Baseline section above. |  | Gate 0 recorded before new implementation edits. |
| BKT-002 | Safety | destructive gates | Require second approval before stopping jobs or deleting `splitdra-ref-20260526`. | BLOCKED | legitimate_safety_handling | Destructive approval | User requested implementation but no post-restatement second approval has been collected. | Destructive approval required. | Live cleanup is blocked until explicit second approval is received. |
| BKT-003 | AWS Cleanup | live cleanup | Export completed analysis dirs, cancel jobs, and delete only approved cluster. | BLOCKED | feature_implementation | Destructive approval | Existing cluster and FSx identified in Gate 0. | Destructive approval required. | Must restate exact effect before live stop/delete. |
| BKT-004 | S3 Layout | bucket/prefix evidence | Verify runtime assets, slim reads, staging, and result prefixes. | SUCCESS | contract_test | Gate 0 | S3 object counts in Gate 0. |  | Required prefixes verified without mutation. |
| BKT-005 | DayEC Config | public interface | Replace public `*_bucket` config/flags with `*_s3_uri`. | SUCCESS | feature_implementation | Gate 1 | Active public scan for old keys/flags returned no hits after README/example cleanup; internal AWS `BucketName` substitutions renamed to `REGSUB_S3_CONTROL_DATA_BUCKET` and `REGSUB_S3_STAGE_BUCKET`; focused DayEC suite -> `381 passed`. |  | Public config now uses explicit S3 URI names while true AWS bucket-name substitutions remain internal. |
| BKT-006 | DayEC DRA | mount policy | Enforce exactly one startup DRA, `/references/`. | SUCCESS | contract_test | Gate 1 | `validate_startup_dra_contract` checks rendered DRA paths equal `["/references/"]`; `tests/test_workflow.py` covers rejection of extra `/control_data/`; focused DayEC suite -> `381 passed`. |  | Startup DRA policy is enforced locally. |
| BKT-007 | DayEC Payloads | setup/headnode scripts | Update source and packaged setup/readiness/docs. | SUCCESS | feature_implementation | Gate 1 | Headnode readiness requires `/fsx/references/runtime_assets` and rejects `/fsx/runtime_assets` and `/fsx/data`; source and packaged templates updated; focused DayEC suite -> `381 passed`. |  | Payload/readiness contract validated locally. |
| BKT-008 | DayEC Catalog | catalog pins | Pin DayOA after DayOA release and verify catalog dry-run/live wiring. | SUCCESS | config_or_startup_contract | Release gate | DayOA `2.0.0` tag pushed and GitHub Release created; source and packaged repository catalogs now use `default_ref: 2.0.0` and command `git_tag: 2.0.0`; focused DayEC suite with catalog tests -> `389 passed`. |  | Catalog pins are ready for DayEC `5.0.0`. |
| BKT-009 | DayOA Paths | workflow/runtime paths | Remove active stale `/fsx/data`, `/fsx/runtime_assets`, and old monolith assumptions. | SUCCESS | feature_implementation | Gate 1 | Companion DayOA ledger rows DAYOA-BKT-001..003 terminal; active scan clean; focused DayOA tests -> `34 passed`. |  | DayOA active code/docs/tests are ready for `2.0.0` release commit. |
| BKT-010 | DayOA Release | release inclusion | Commit all dirty DayOA work and release from `1.0.38` baseline as `2.0.0`. | BLOCKED | feature_implementation | Release gate | DayOA companion ledger owns release; latest baseline `1.0.38`. | Requires PR/merge/tag sequence. | Implementation side complete; release gate remains. |
| BKT-011 | DayRef | public references | Update DayRef expected layout and public-scrub validation. | SUCCESS | feature_implementation | Gate 1 | DayRef companion ledger rows DAYREF-BKT-001..004 terminal; constants and shell helper use `runtime_assets/...`, top-level `genomic_data/...`, and `genomic_data/organism_reads_slim/`; tests -> `21 passed`. |  | DayRef layout is ready for release commit. |
| BKT-012 | Ursa Contract | API/UI/staging | Update Ursa to DayEC `*_s3_uri` contract and new stage target. | SUCCESS | feature_implementation | Gate 1 | Ursa branch `codex/bucket-contract-dayec-5`; focused Ursa suite -> `114 passed`; active scan only finds explicit negative `/fsx/data` rejection guards/tests. |  | Ursa is ready for final upstream pins after DayOA/DayEC releases. |
| BKT-013 | Versioning | release train | PR-merge/tag DayRef, DayOA, DayEC, then Ursa with next major tags. | IN_PROGRESS | config_or_startup_contract | Release gate | DayRef `1.0.0` merged/tagged/released; DayOA `2.0.0` merged/tagged/released; DayEC catalog now pins DayOA `2.0.0`. | Awaiting DayEC and Ursa merge/tag sequence. | Continue from DayEC release, then final Ursa pin/release. |
| BKT-014 | Cluster Create | `bucketsamok` | Create new cluster from final released pins in clean env. | BLOCKED | feature_implementation | Release and live approval | `bucketsamok` absent at Gate 0. | Requires prior release tags and old cluster cleanup approval. | Do not create until local/release gates pass. |
| BKT-015 | Live Validation | command catalog | Run catalog max 3 active, export each success, delete exported FSx dirs. | BLOCKED | contract_test | Live gate | Requires `bucketsamok` cluster. | Cluster not created. |  |

## Acceptance Checks

- Active DayEC scans must have no public `*_bucket=s3://...` interface, no old CLI flags, and no startup DRA except `/references/`. Remaining `_BUCKET` symbols are internal AWS bucket-name substitutions for S3 API/IAM fields.
- Local DayEC focused tests passed after DayOA pin update: `389 passed`.
- Live cleanup and new cluster creation remain blocked until the required gates are terminal or explicitly approved.
