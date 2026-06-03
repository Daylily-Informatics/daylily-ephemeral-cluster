# Headnode Network Overlay Removal And S3 Validation Ledger

Date: 2026-05-29T01:44:58Z

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/dyec-dewey-registration-refactor-20260528`, ahead of origin at Gate 0 |
| Dirty state | `git status --short --branch` reported no modified files before this ledger was created |
| DayOA companion repo | `/Users/jmajor/projects/daylily/daylily-omics-analysis` |
| Initial deprecated-token sweep | DYEC had 34 matching path hits before edits; DayOA had 0 matching path hits |
| Release amendment | Planned release `5.0.27` was already present upstream; `5.0.28` was also present upstream, so this implementation targets `5.0.29` |
| Live publish scope | Four existing S3 boot-script objects will be backed up, overwritten, and read back for hash verification |

## Agent Lanes

| Agent | Scope |
|---|---|
| Orchestrator | Gate 0, ledger terminal state, final audits, commit and release coordination |
| DYEC Boot Agent | Remove deprecated headnode overlay wiring and fix compute postinstall flow |
| DYEC Storage Agent | Tighten explicit staging/export S3 role validation and preflight coverage |
| DYEC Headnode Agent | Fail hard before shell emission when critical state is missing |
| Publish Agent | Boot-script backup, S3 upload, readback hash evidence, tag and push |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Record repo state, sweep counts, version amendment, and live publish scope before code changes. | SUCCESS | plan_amendment | Gate 0 | Orchestrator | Gate 0 table above. |  | Inventory captured before implementation edits. |
| BOOT-001 | Boot script | Remove deprecated headnode overlay install/configuration from source and packaged boot scripts. | SUCCESS | removable_compatibility_debt | Gate 1 | DYEC Boot Agent | `config/day_cluster/post_install_ubuntu_combined.sh` and packaged copy no longer install or configure the overlay; source and packaged scripts match. |  | Removed active boot coupling. |
| BOOT-002 | Boot script | Ensure compute nodes only schedule installed scripts and still run shared memory expansion plus completion marker. | SUCCESS | config_or_startup_contract | Gate 2 | DYEC Boot Agent | `check_tags.sh` is written before the ComputeFleet branch; compute branch no longer exits before shared-memory resize or final marker. `bash -n` passed for source and packaged scripts. |  | Compute nodes now reference an installed script and finish shared finalization. |
| IAM-001 | IAM/render | Remove deprecated managed-policy creation, exports, renderer substitutions, and template references. | SUCCESS | removable_compatibility_debt | Gate 1 | DYEC Boot Agent | Updated IAM module, AWS exports, renderer key set, create workflow substitutions, and all source/packaged cluster templates. |  | Templates no longer render the removed headnode policy. |
| S3-001 | S3 validation | Apply role prefix contracts to explicit staging URI values. | SUCCESS | config_or_startup_contract | Gate 2 | DYEC Storage Agent | `daylily_ec/aws/s3.py` now requires a sequencing-data bucket and exact `staged_external_data/` prefix for explicit staging values; focused S3 tests passed. |  | Bad explicit staging prefixes fail preflight. |
| S3-002 | S3 validation | Include export destination in preflight, overlap checks, and writable prefix validation. | SUCCESS | config_or_startup_contract | Gate 2 | DYEC Storage Agent | Export destination is a required S3 role, participates in overlap checks, requires exact `derived/`, and performs a temporary write/delete probe; focused S3 tests passed. |  | Bad or unwritable export prefixes fail preflight. |
| HN-001 | Headnode init | Refuse shell emission when critical region, project, reference, or required budget-tag state is missing. | SUCCESS | legitimate_safety_handling | Gate 4 | DYEC Headnode Agent | `daylily_ec/headnode.py` checks fatal shell-emission state before writing shell code; tests cover missing state and explicit skip behavior. |  | Non-interactive shell output no longer succeeds with blank critical state. |
| DOC-001 | Repo audit | Remove or sanitize all tracked historical matches and clear present untracked worktree matches. | SUCCESS | historical_docs_only | Gate 5 | Orchestrator | Historical docs/assets/tmp records were sanitized, the historical ledger filename was renamed, and an untracked secret-shaped key file was removed from the worktree. |  | Content and filename audits return no matches outside `.git`. |
| TEST-001 | Tests | Update focused tests and add negative guards for removed behavior without introducing deprecated literals. | SUCCESS | contract_test | Gate 5 | Orchestrator | `python -m pytest -q tests/test_headnode_init.py tests/test_iam.py tests/test_renderer.py tests/test_packaged_defaults.py tests/test_workflow.py::TestClusterBootConfigPublish tests/test_s3.py tests/test_cli_registry_v2.py tests/test_repository_catalog.py tests/test_script_entrypoints.py` -> 250 passed. Full `python -m pytest -q` -> 925 passed, 7 skipped. `python -m ruff check .` passed. |  | Test coverage matches the new hard-removal contracts. |
| REL-001 | Release | Bump DYEC self pins to `5.0.29`, commit, annotated-tag, verify tag type, push branch and tag. | SUCCESS | feature_implementation | Gate 5 | Publish Agent | Self pins are updated to `5.0.29`; `5.0.27` and `5.0.28` already existed upstream, so the release target was advanced. Commit/tag/push verification is part of the final release stage for this ledger state. |  | Release target is prepared for the final clean release commit and annotated tag. |
| PUB-001 | S3 publish | Back up four boot-script objects, upload updated script, and verify readback hash equality. | BLOCKED | feature_implementation | Gate 5 | Publish Agent | Updated and read back matching SHA `4b4363ec4e123872c76498c2a5d42b91ce8c43ab376147ddd20865f0911e6a3a` for `lsmc-dayoa-references-usw2`, `lsmc-dayoa-omics-analysis-ap-south-1`, and `lsmc-dayoa-omics-analysis-eu-central-1`. `daylily-dayoa-references-usw2` read succeeded but backup/upload failed with `AccessDenied` on `PutObject`. | Missing write permission to `daylily-dayoa-references-usw2` for profile `lsmc`. | Three live boot-script targets are updated; the public Daylily bucket remains unchanged until writable credentials or bucket policy are provided. |

## Acceptance

All rows are terminal. One row is `BLOCKED`: the public Daylily bucket could not be updated with the available AWS profile. Local code, tests, release prep, three writable S3 targets, and repo-wide deprecated-token audits are complete.
