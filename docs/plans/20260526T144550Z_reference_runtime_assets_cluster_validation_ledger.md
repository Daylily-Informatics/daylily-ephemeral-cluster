# Reference Runtime Assets One-DRA Cluster Validation Ledger

Created: 2026-05-26T14:45:50Z

## Objective

Rebase DayEC from a split static-DRA startup model to a one-DRA startup contract:
`/fsx/references` is the only static DRA, and runtime assets live under
`/fsx/references/runtime_assets`. Delete the obsolete `splitdra-smoke-20260526`
cluster, validate the new contract locally and on a fresh LSMC cluster named
`splitdra-refassets-20260526`, then run the command catalog in batches of four.

## Gate 0 Inventory

- Controlling request: user-approved plan "Runtime Assets Under References: One-DRA Cluster Validation".
- DayEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`.
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`.
- References repo: `/Users/jmajor/projects/daylily/daylily-omics-references`.
- DayEC git state: `## codex/analysis-id-export-catalog-validation...origin/codex/analysis-id-export-catalog-validation`.
- DayOA git state: `## codex/tstclu411c-hybrid-env-python...origin/codex/tstclu411c-hybrid-env-python`.
- References git state: `## codex/headnode-readiness-reference-verifier...origin/codex/headnode-readiness-reference-verifier`.
- LSMC identity: `arn:aws:iam::108782052779:root`.
- Daylily identity: `arn:aws:iam::670484050738:root`.
- Obsolete cluster baseline: `splitdra-smoke-20260526` is `CREATE_COMPLETE`; headnode `i-07ae5eee3c020dea8`; FSx `fs-0a6fa19b5720961ba`.
- Obsolete cluster DRAs: `/references/ -> s3://lsmc-dayoa-references-usw2`, `/runtime_assets/ -> s3://lsmc-dayoa-runtime-assets-usw2`, both `AVAILABLE`.
- Initial DayEC sweep: 254 active source/test/doc hits for standalone runtime-assets contract or old catalog pin.
- Initial DayOA 1.0.36 sweep: 237 hits for `/fsx/runtime_assets` or retired staging terms.
- Initial references-repo sweep: 33 hits for old `data/...` reference/runtime expectations or scrub-sensitive terms.
- Approval state: user gave explicit approval to delete only cluster `splitdra-smoke-20260526`; no bucket deletion or prefix deletion is approved.
- Security decision: LSMC references bucket becomes private before runtime assets are copied into `runtime_assets/`; Daylily public mirror strips licenses/private/commercial/LSMC/RCRF material.

## Ledger

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| RRA-001 | Orchestrator | Record Gate 0 inventory, repo state, live AWS baseline, and approval gates. | SUCCESS | contract_test | Gate 0 | orchestrator | This ledger Gate 0 section. |  | Gate 0 recorded before code and live mutations. |
| RRA-002 | AWS cleanup | Delete `splitdra-smoke-20260526` and wait for stack deletion. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Approved exact command returned `DELETE_IN_PROGRESS`; `aws cloudformation wait stack-delete-complete` returned success; readback: `pcluster describe-cluster` reports cluster does not exist and `aws cloudformation describe-stacks` reports stack does not exist. |  | Obsolete two-DRA smoke cluster was deleted before replacement work. |
| RRA-003 | LSMC S3 posture | Make `lsmc-dayoa-references-usw2` private/block-public-access before runtime assets copy. | SUCCESS | config_or_startup_contract | Gate 2 | Agent A | Baseline was public: PAB all `false`, `PolicyStatus.IsPublic=true`, policy allowed public list/get. Applied `put-public-access-block` all `true` and deleted bucket policy. Readback: PAB all `true`, `get-bucket-policy` and `get-bucket-policy-status` return `NoSuchBucketPolicy`, anonymous `aws s3 ls --no-sign-request` returns `AccessDenied`. |  | LSMC references bucket is private before private runtime assets are copied under it. |
| RRA-004 | LSMC S3 layout | Copy runtime assets under `s3://lsmc-dayoa-references-usw2/runtime_assets/` and verify required keys. | SUCCESS | feature_implementation | Gate 2 | Agent A | Synced `cluster_boot_config/`, `cached_envs/`, `tool_specific_resources/`, and `budget_tags/` from `lsmc-dayoa-runtime-assets-usw2` into `lsmc-dayoa-references-usw2/runtime_assets/`. Source/destination totals match: cluster boot `21 objects/521.7 KiB`, cached envs `68,362 objects/10.4 GiB`, tool resources `13,992 objects/29.3 GiB`, budget tags `1 object/4.9 KiB`. Required keys read back: boot script, Apptainer deb, Cromwell jar, Womtool jar, budget tags TSV, and `runtime_assets/cached_envs/conda/` prefix. |  | LSMC references bucket now contains private runtime assets under the one-DRA prefix. |
| RRA-005 | DayEC config/render | Remove standalone `runtime_assets_bucket`, static `/runtime_assets/` DRA, substitutions, and IAM dependency from cluster render. | SUCCESS | feature_implementation | Gate 2 | Agent B | Updated S3 role validation, create/preflight workflow, render substitutions, config request/template keys, state model, and all source/payload cluster templates. Focused DayEC suite returned `369 passed`. |  | Cluster render now has no standalone runtime-assets role or static DRA. |
| RRA-006 | DayEC setup/readiness | Update headnode/compute setup, packaged payloads, sbatch budget tags, global config, and readiness checks to `/fsx/references/runtime_assets`. | SUCCESS | feature_implementation | Gate 2 | Agent B | Updated source and payload `post_install_ubuntu_combined.sh`, `sbatch`, `daylily_cli_global.yaml`, `headnode.py`, and `headnode_readiness.py`; readiness now asserts `/fsx/runtime_assets` and `/fsx/data` are absent. Focused DayEC suite returned `369 passed`. |  | Runtime assets are consumed only through the references DRA. |
| RRA-007 | DayEC staging/mounts | Keep staging and control-data as explicit roles for translation/on-demand DRAs; reject `/runtime_assets` as a managed purpose/root. | SUCCESS | feature_implementation | Gate 2 | Agent C | Removed `runtime-assets` mount purpose/root, removed staging CLI `--runtime-assets-bucket`, and made `/fsx/runtime_assets` path translation fail with a hard error pointing to `/fsx/references/runtime_assets`. Focused DayEC suite returned `369 passed`. |  | Control-data and staging remain explicit S3 roles for on-demand use, not startup DRAs. |
| RRA-008 | DayOA path cutover | Update DayOA active code/config/tests from `/fsx/runtime_assets` to `/fsx/references/runtime_assets`; keep staging on `staged_external_sequencing_data`. | SUCCESS | feature_implementation | Gate 2 | Agent D | DayOA active sweep returned no `/fsx/runtime_assets`, `/fsx/data`, or `staged_sample_data` hits under `bin config workflow tests scripts .test_data`; focused DayOA tests passed. |  | DayOA active paths match the one-DRA contract. |
| RRA-009 | DayOA release | Run focused DayOA tests and create annotated tag `1.0.37`; update DayEC catalog pins to `1.0.37`. | SUCCESS | feature_implementation | Gate 3 | Agent D | DayEC catalog pins updated to `1.0.37`; DayOA focused validation passed; DayOA commit `b2c8057` includes the full current worktree per user instruction; annotated tag `1.0.37` pushed to origin; follow-up branch commit `f198a02` records the terminal DayOA ledger row without rewriting the published tag. |  | DayOA release is available for cluster catalog use. |
| RRA-010 | References repo | Update reference verifier/manifests to top-level `genomic_data/...` and `runtime_assets/...`; add public scrub validation. | SUCCESS | feature_implementation | Gate 3 | Agent E | References repo constants and verifier updated; `verify --public-safe` added; `python -m pytest -q` returned `21 passed`; references `git diff --check` passed. |  | References repo supports private LSMC and public Daylily-safe validation modes. |
| RRA-011 | Local validation | Run focused DayEC, DayOA, and references-repo test suites. | SUCCESS | contract_test | Gate 4 | orchestrator | DayEC focused suite: `369 passed`; DayOA focused pytest: `8 passed`; DayOA CLI shell: `28 passed`; references repo: `21 passed`; `git diff --check` passed in all three repos. |  | Local validation for code cutover is green. |
| RRA-012 | New cluster create | Create `splitdra-refassets-20260526` in `us-west-2d` with one static references DRA. | BLOCKED | feature_implementation | Gate 5 | orchestrator | `DAY_BREAK=1 dyec create --profile lsmc --region-az us-west-2d --config docs/plans/20260526T150735Z_splitdra_refassets_cluster_request.yaml` stopped before live create with: `Invalid cluster name 'splitdra-refassets-20260526'. It must be 5-25 characters, start with a letter, and contain only letters, digits, and hyphens.` | Requested name is 27 characters; ParallelCluster maximum is 25. | Need explicit approval for a valid replacement such as `splitdra-ref-20260526` before live cluster creation. |
| RRA-013 | Live DRA/readiness | Verify only `/references/` static DRA exists; verify `/fsx/references/runtime_assets` and no `/fsx/runtime_assets` or `/fsx/data`. | OPEN | contract_test | Gate 5 | Agent F |  |  |  |
| RRA-014 | Live staging/run mounts | Verify on-demand staging DRA to `staged_external_sequencing_data` and raw sequencing run-dir DRAs under `/fsx/run_dir_mounts`. | OPEN | contract_test | Gate 5 | Agent F |  |  |  |
| RRA-015 | Command catalog | Run command catalog dry-runs and live runs in batches of at most four active commands; block unresolved CG/MGI rather than invent input. | OPEN | contract_test | Gate 6 | Agent G |  |  |  |
| RRA-016 | Daylily mirror | After LSMC validation passes, mirror public-safe runtime assets into `daylily-dayoa-references-usw2/runtime_assets/` with scrub checks. | OPEN | feature_implementation | Gate 7 | Agent H |  |  |  |
| RRA-017 | Final report | Record terminal row counts, cluster/result/export evidence, residual risks, and blocked destructive deletions. | OPEN | contract_test | Gate 8 | orchestrator |  |  |  |

## Acceptance Notes

- No compatibility symlink from `/fsx/runtime_assets`.
- No `/fsx/data` compatibility mount.
- No S3 deletion, bucket deletion, lifecycle changes, or post-validation cluster teardown without a later exact destructive approval.
