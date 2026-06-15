# Sentieon 202503.03 Runtime Cutover Ledger

Created: 2026-06-15T04:50:51Z

## Objective

Finish the DayOA/DYEC Sentieon 202503.03 cutover by:

- updating DYEC global Sentieon runtime config from `sentieon-genomics-202503.02` to `sentieon-genomics-202503.03`;
- syncing the full mounted Sentieon `202503.03` release from `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.03/` to `s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/sentieon-genomics-202503.03/` so new headnodes auto-mount it;
- verifying the exact `202503.03` runtime and model bundle paths referenced by active DayOA config;
- preserving evidence for source objects, destination objects, and any live FSx verification.

## Gate 0 Inventory

Controlling ledger: `docs/plans/20260615T045051Z_sentieon_20250303_runtime_cutover_ledger.md`

Repos:

- DYEC: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `jem-dev`, baseline `git status --short --branch` was clean at start: `## jem-dev...origin/jem-dev`.
- DayOA: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch `jem-dev`, baseline `git status --short --branch` included user/previous untracked plan dir `?? docs/plans/20260615T034314Z_hg003_ilmn30x_linear_sentd_1004/`.

Instruction files read:

- `/Users/jmajor/.agents/AGENTS.md`
- `/Users/jmajor/.agents/AGENTS-HOW-TO-RUN-DAYOA.md`
- `/Users/jmajor/.codex/AGENTS.md`
- `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`
- `/Users/jmajor/projects/lsmc/AGENTS.md`
- `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/AGENTS.md`
- `/Users/jmajor/projects/lsmc/daylily-omics-analysis/AGENTS.md`
- `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`

DayOA active config evidence:

- `config/daylily_cli_global.yaml` points to `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.03/`.
- `bin/dayoa_sentieon` default binary is `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.03/bin/sentieon`.
- Active DayOA envs pin `sentieon=202503.03`, `sentieon-cli==1.6.3`, and segdup envs pin `segdup-caller@v0.6.0`.
- Active DayOA `config/day_profiles/{slurm,local}/templates/rule_config.yaml` references 21 unique `sentieon-genomics-202503.03` paths, including `bin/sentieon`, `DNAscopeONT2.3.bundle`, `SentieonIlluminaPangenomeRealignWGS1.2.bundle`, `SentieonUltimaPangenomeRealignWGS1.3.bundle`, `SentieonIlluminaWGS2.2.bundle`, and hybrid/PacBio/Ultima bundle paths.

DYEC baseline gap:

- `config/daylily_cli_global.yaml` still pointed to `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/`.
- `daylily_ec/resources/payload/config/daylily_cli_global.yaml` still pointed to `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/`.
- DYEC `pyproject.toml` already pinned DayOA to `10.0.18`.

S3 baseline:

- `AWS_PROFILE=lsmc aws s3api list-objects-v2 --bucket lsmc-dayoa-references-usw2 --prefix runtime_assets/cached_envs/ --delimiter '/'` showed `runtime_assets/cached_envs/sentieon-genomics-202503.02/`, but no `sentieon-genomics-202503.03/` prefix.
- `AWS_PROFILE=daylily aws s3api list-objects-v2 --bucket daylily-dayoa-runtime-assets-usw2 --prefix cached_envs/sentieon-genomics-202503.03/` returned no objects.
- `AWS_PROFILE=lsmc aws s3api head-object` found segdup population VCF and TBI under `runtime_assets/tool_specific_resources/segdup-caller/pop_vcfs/`, but returned 404 for checked `202503.03` runtime/bundle keys in the LSMC reference bucket.

Upstream Sentieon bundle preflight:

- Current `sentieon_models.yaml` source refreshed directly from Sentieon GitHub, not from cluster files:
  - GitHub API URL: `https://api.github.com/repos/Sentieon/sentieon-models/contents/sentieon_models.yaml?ref=main`
  - GitHub HTML URL: `https://github.com/Sentieon/sentieon-models/blob/main/sentieon_models.yaml`
  - Raw download URL: `https://raw.githubusercontent.com/Sentieon/sentieon-models/main/sentieon_models.yaml`
  - Git blob SHA: `8a5e9bf6f47d42e8796fda5d182bd8b8a633c96b`
  - Raw file SHA-256: `41b03d047a81b94d12eb5ed0709146565f2ed8814ffd19a933ce28bb2d23139c`
  - Fetched snapshot: `docs/plans/20260615T045051Z_sentieon_models_github_main.yaml`
  - File declares `Updated on: "2026-06-01"`.
- `DNAscopeONT2.3.bundle`: source present in `s3://sentieon-release/other/`, size `925744416`, ETag `"12fee33cbd345c800c2f14579fa03145-127"`.
- `SentieonIlluminaPangenomeRealignWGS1.2.bundle`: source present, size `1217079274`, ETag `"3b2a262dac2a8b2ced98ec735d4fe837-146"`. This differs from the older `202503.02` LSMC copy size `1210174610`.
- `SentieonUltimaPangenomeRealignWGS1.3.bundle`: source present, size `919927022`, ETag `"8f0866ef980f681cd5105581957f8348-126"`.
- `SentieonIlluminaPangenomeRealignWGS1.0.bundle`: source present, size `252722776`, ETag `"d2a033572260a48f596f1e5bcc4ddb04-35"`.
- Several other active model bundle sources were present in `s3://sentieon-release/other/`; `HybridIlluminaPacBio2.3.bundle` and `HybridUltimaONT1.1.model.bundle` returned 403 from upstream HEAD preflight. Current upstream `sentieon_models.yaml`, updated 2026-06-01, names `HybridIlluminaPacBio1.1.bundle` and `HybridUltimaONT1.1.bundle` instead.

Live FSx target:

- `daylily-ec --json cluster-info --profile lsmc --region us-west-2` showed `dyecX4` and `altairval` in `CREATE_COMPLETE`.
- `daylily-ec --json headnode info --profile lsmc --region us-west-2 --cluster dyecX4` resolved headnode `i-05815cdeec4a6dad8`, state `running`.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SNT-001 | DYEC config | Update repo global Sentieon install config to `sentieon-genomics-202503.03`. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Changed `config/daylily_cli_global.yaml:9`; stale grep for active DYEC config returned no hits. |  | Repo-level global config now points to the new Sentieon runtime. |
| SNT-002 | DYEC payload config | Update packaged payload global Sentieon install config to `sentieon-genomics-202503.03`. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Changed `daylily_ec/resources/payload/config/daylily_cli_global.yaml:9`; stale grep for active DYEC payload config returned no hits. |  | Packaged headnode payload config now points to the new Sentieon runtime. |
| SNT-003 | Source bundles | Preflight upstream source bundles needed for active DayOA `202503.03` model paths. | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | Source HEADs succeeded for current ONT, pangenome, WGS, MGI, PacBio, and hybrid bundle names. Current upstream YAML showed the two failed HEAD names were stale DayOA config names, not current model names. |  | Upstream current model naming was reconciled with DayOA config. |
| SNT-004 | LSMC S3 runtime assets | Make or verify exact LSMC reference-bucket `runtime_assets/cached_envs/sentieon-genomics-202503.03/` runtime and bundle paths. | SUCCESS | config_or_startup_contract | Gate 5 | orchestrator | Direct headnode `aws s3 sync` failed with `AccessDenied` for role `dyecX4-RoleHeadNode-MnfdTOlVjuad`. FSx export task `task-0f33f34da3c713f91` on `fs-04960a3a07c091cf3` exported `/references/runtime_assets/cached_envs/sentieon-genomics-202503.03/`, lifecycle `SUCCEEDED`, `99/99` succeeded, `0` failed. S3 prefix now lists total size `7038072250`; selected HEADs passed for `bin/sentieon`, `DNAscopeONT2.3.bundle`, ILMN pangenome `1.2`, Ultima pangenome `1.3`, prior ILMN `1.0`, `SentieonIlluminaWGS2.2.bundle`, `DNAscopeMGIWGS2.1.bundle`, `HybridIlluminaPacBio1.1.bundle`, and `HybridUltimaONT1.1.bundle`. |  | LSMC reference bucket now has the mounted Sentieon 202503.03 release for new-headnode auto-mount. |
| SNT-005 | Daylily S3 runtime assets | Make or verify exact Daylily runtime-assets `cached_envs/sentieon-genomics-202503.03/` runtime and bundle paths. | NO_LONGER_NEEDED | config_or_startup_contract | Gate 5 | orchestrator | User clarified the target was the `runtime_assets/cached_envs/sentieon-genomics-202503.03` S3 bucket location used for LSMC reference auto-mounts. |  | Superseded by the LSMC reference-bucket export row. |
| SNT-006 | Live FSx | Verify current `dyecX4` `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.03` runtime and active bundle paths as `ubuntu` through supported SSM helper path. | SUCCESS | config_or_startup_contract | Gate 5 | orchestrator | `docs/plans/20260615T045051Z_sentieon_20250303_runtime_cutover_ssm.py` via DYEC SSM helper resolved `dyecX4` headnode `i-05815cdeec4a6dad8` and reported `__SOURCE_FILE_COUNT__=71`, `__SOURCE_DU_KB__=6883211`, `__MISSING_ACTIVE_PATHS__=0`. |  | Live mounted release has the physical runtime and bundle files needed by active DayOA config after stale bundle-name correction. |
| SNT-007 | Validation | Run focused local validation for DYEC config cutover and record final status counts. | SUCCESS | contract_test | Gate 5 | orchestrator | DYEC: `python -m pytest -q tests/test_repository_catalog.py tests/test_lsmc_bio_fork_contract.py` -> `15 passed`; DayOA: `python -m pytest -q tests/test_sentieon_model_bundle_config.py tests/test_complete_genomics_sentieon.py` -> `5 passed`; `git diff --check` passed in both repos. |  | Focused local validation passed. |
| SNT-008 | DayOA model names | Correct active DayOA config names that referenced non-current/non-exported top-level hybrid bundles. | SUCCESS | config_or_startup_contract | Gate 5 | orchestrator | Updated DayOA `config/day_profiles/local/templates/rule_config.yaml`: `HybridIlluminaPacBio2.3.bundle` to `HybridIlluminaPacBio1.1.bundle`, and `HybridUltimaONT1.1.model.bundle` to `HybridUltimaONT1.1.bundle`; updated DayOA `config/day_profiles/slurm/templates/rule_config.yaml`: `HybridUltimaONT1.1.model.bundle` to `HybridUltimaONT1.1.bundle`. DayOA `tests/test_sentieon_model_bundle_config.py` now asserts the corrected hybrid bundle names and rejects stale names. Grep for the stale names in active templates returned no hits. |  | Active DayOA templates now name the current Sentieon hybrid bundles present in the mounted/exported release. |
| SNT-009 | LSMC active bundle objects | Back up and replace any active `202503.03` bundle objects whose exported size differed from current `s3://sentieon-release/other/` objects named by current GitHub `sentieon_models.yaml`. | SUCCESS | config_or_startup_contract | Gate 5 | orchestrator | Helper: `docs/plans/20260615T051631Z_sentieon_upstream_model_bundle_sync.py`. Dry-run evidence: `docs/plans/20260615T051631Z_sentieon_upstream_model_bundle_sync_dryrun.json` reported `10` matches, `1` missing object, and `6` backup-and-replace objects. Execute evidence: `docs/plans/20260615T051631Z_sentieon_upstream_model_bundle_sync_execute.json` used source HEADs from `s3://sentieon-release/other/`, backed up six pre-existing objects under `s3://lsmc-dayoa-references-usw2/runtime_assets/backups/sentieon-genomics-202503.03/20260615T051631Z/bundles/`, copied source objects with `CopySourceIfMatch`, and verified changed destination `ContentLength` values. Final verification evidence: `docs/plans/20260615T051631Z_sentieon_upstream_model_bundle_sync_verify.json` reported `17` matches, `0` missing, `0` backup-and-replace remaining. `GetObjectAttributes` checksum retrieval was not permitted by IAM/source access, so independent checksum comparison was not available. |  | Active LSMC `sentieon-genomics-202503.03/bundles/` now has all current GitHub-listed Sentieon bundle objects copied from the Sentieon release bucket and matching upstream sizes. |

## Amendments

- 2026-06-15T04:57Z: User clarified that the full Sentieon `202503.03` release should be moved into the LSMC reference bucket path `runtime_assets/cached_envs/sentieon-genomics-202503.03/` for auto-mount on new headnodes. Interpreting "move" as non-destructive sync/copy from the verified mounted FSx release; do not delete the FSx source.
- 2026-06-15T05:16Z: User approved correcting active bundle-object discrepancies against `s3://sentieon-release/other/` by backing up the current LSMC object and replacing it with the Sentieon release-bucket version.

## Final Status

- Terminal rows: 9/9.
- Success: 8.
- No longer needed: 1.
- Failed/blocked/open: 0.
- Objective complete: yes, for the LSMC reference-bucket auto-mount path and active DayOA/DYEC config alignment.
- Final active-bundle note: after the corrective sync, final comparison against current GitHub `sentieon_models.yaml` and `s3://sentieon-release/other/` reported all `17/17` bundle objects matching by `ContentLength`; no missing or replacement actions remain.
- Final local repo note: during execution DYEC branch state advanced to `10.0.32`; the DYEC global config files now contain `sentieon-genomics-202503.03` in `HEAD`. This turn's durable evidence artifacts are this ledger, the SSM verification helper, the GitHub Sentieon YAML snapshot, and the Sentieon bundle-sync helper/evidence JSON files.
