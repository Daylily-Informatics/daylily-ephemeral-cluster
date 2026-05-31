# DYEC Catalog Metadata And Release Ledger

Created: 2026-05-31T06:15:28Z

## Objective

After a successful DayOA release, update DYEC so the command catalog records command
maturity, validated DayOA versions, reusable test-data profiles, current DayOA pins,
active technical docs, and DYEC self-pins; then validate locally and on `dyec-test`,
commit, tag, build, publish, and push the next DYEC release.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/dyec-dewey-registration-refactor-20260528` tracking origin |
| Baseline HEAD | `bcc7cb29` |
| Baseline tag | `5.1.3` |
| Dirty state | `git status --short --branch --untracked-files=all` returned only the clean branch line |
| Current DayOA catalog pin | `2.0.23` in source and packaged catalog |
| Current DYEC self-pin | `5.1.2` in `config/daylily_cli_global.yaml` and packaged copy; needs update after new DYEC commit/tag |
| Prior catalog validation | `docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_ledger.md`: 19 successes/exported, `hybrid_ultima_ont_snv` failed |
| Release target | Next DYEC tag `5.1.4`, annotated non-`v` tag if DayOA hard gate passes |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-001 | Catalog Model | Add command `type: prod|test|dev` and `validated_version` fields; fail hard on missing or invalid values. | OPEN | feature_implementation | Gate 1 | dyec-agent | Current model in `daylily_ec/repositories.py` forbids extra fields and lacks these keys. |  |  |
| DYEC-002 | Test Data Profiles | Add top-level reusable `test_data_profiles` and per-command `test_data_profile` references with validation. | OPEN | feature_implementation | Gate 1 | dyec-agent | Existing top-level `test_data_locations` records default reference/control roots only. |  |  |
| DYEC-003 | Catalog Content | Pin DayOA to the final DayOA release, classify `simple-test` as `test`, classify live-success rows as `prod`, and include source test-data locations for each command. | OPEN | config_or_startup_contract | Gate 2 | dyec-agent | Current catalog has 20 commands pinned to `2.0.23`. |  |  |
| DYEC-004 | Packaged Resources | Keep source and packaged catalogs and CLI global self-pin files byte-for-byte consistent where expected. | OPEN | contract_test | Gate 5 | dyec-agent | Existing tests compare packaged catalog with source catalog. |  |  |
| DYEC-005 | Docs | Update active user/operator/technical docs for current pins, DRA mount behavior, export receipts, BCL no-copy lane-split behavior, catalog metadata, pipeline-manager launch contracts, and latest validation state. | IN_PROGRESS | feature_implementation | Gate 5 | docs-agent | Stale active docs still mention DayOA `2.0.5`, `2.0.19`, and DYEC `5.1.2`. Added `docs/pipeline_manager_launches.md` with Snakemake 7 DayOA, Snakemake 8 repository, Nextflow, and future Cromwell/WDL launch contracts; linked it from `README.md`, `docs/overview.md`, and `docs/operations.md`. |  | Release-state, catalog metadata, and final validation notes still pending. |
| DYEC-006 | Local Validation | Run focused catalog/package/CLI/workflow tests, full pytest, ruff, and diff checks. | OPEN | contract_test | Gate 5 | orchestrator |  |  |  |
| DYEC-007 | Live Validation | Run final DYEC catalog validation on `dyec-test` against the new DayOA tag; all `type: prod` and `type: test` rows must be terminal success. | OPEN | contract_test | Gate 5 | orchestrator | Latest targeted branch dry-run `release20260531_hybrid_ultima_ont_snv_ef4da30_dryrun` completed `exit_code=1` before Snakemake because the DYEC launcher still attempted an older Hybrid Ultima/ONT Stage1 assertion runtime repair and failed with `Hybrid Ultima/ONT Stage1 assertion repair target not found in workflow/rules/sent_hybrid_ug_ont_modular.refactored.smk`. `dyec headnode jobs` showed no active Slurm jobs afterward. |  | Next action is to remove or hard-gate the stale DYEC hybrid runtime patch now that DayOA owns the source fix, then rerun dry-run and live validation. |
| DYEC-008 | Release | Commit DYEC changes, create annotated tag `5.1.4`, push branch/tag, build with `python -m build` from `TWINE`, and publish with `twup`. | OPEN | config_or_startup_contract | Gate 5 | release-agent |  |  |  |
| DYEC-009 | Bootstrap Env Caches | Verify the reference-bucket environment caches are exposed at the exact DayOA Snakemake `conda-prefix` and `singularity-prefix` paths; update headnode/compute bootstrap if not. | SUCCESS | config_or_startup_contract | Gate 2 | dyec-agent | DayOA Slurm/local profile templates use `/fsx/resources/environments/conda/USER_REGSUB/HOSTNAME` and `/fsx/resources/environments/containers/USER_REGSUB/HOSTNAME`; `bin/util/profile_freshness_warn.bash` substitutes those placeholders into active profile YAML before `bin/day_run` launches Snakemake. `dyec-test` readback command `99cec11a-f05a-493d-a0a7-561a425ded3b` showed active profile `conda-prefix: "/fsx/resources/environments/conda/ubuntu/ip-10-0-0-88"`, expected path exists, 75 conda entries, and cache symlinks resolve to `/fsx/references/runtime_assets/cached_envs/conda/*`. Source and packaged boot script now call `prepare_dayoa_environment_cache` before the HeadNode branch so HeadNode and ComputeFleet both seed rule-visible cache paths from `/fsx/references/runtime_assets/cached_envs`. `bash -n config/day_cluster/post_install_ubuntu_combined.sh`, focused headnode/resource tests, `cmp` source-vs-packaged script, and `git diff --check` passed. | Existing boot script seeded only the HeadNode branch; powered-down `idle~` compute hostnames on `dyec-test` were not resolvable for direct SSH readback. | Local source, packaged resource, tests, and live headnode readback satisfy the amendment. Release tagging and S3 boot-script publication remain tracked by release rows. |
| DYEC-010 | Bootstrap Shared Results Root | Make `/fsx/analysis_results/` itself `a+rwx` for `ubuntu` and other users, not just `/fsx/analysis_results/ubuntu/`. | SUCCESS | config_or_startup_contract | Gate 2 | dyec-agent | User amendment on 2026-05-31; current boot script only created user-specific result subdirs with `0775`. Source and packaged boot script now create `/fsx/analysis_results` with mode `0777` and `chmod a+rwx`; `dyec-test` readback command `8f9912e5-fae0-4ce6-95dc-fa48785c03cf` showed current `/fsx/analysis_results` already `drwxrwxrwx 777 root:root`. Focused bootstrap tests assert the parent directory creation and mode adjustment. | Other executing entities cannot reliably create their own analysis roots if the parent is not world writable. | Local source, packaged resource, tests, and live headnode readback satisfy the amendment. Release tagging and S3 boot-script publication remain tracked by release rows. |
| DYEC-011 | BCL Launch Contract | Stop applying the older DYEC runtime BCL lane-split rule patch when DayOA owns native lane splitting; require native DayOA BCL markers, inject zero barcode mismatches, and keep lane FASTQ merge off in active BCL config. | SUCCESS | config_or_startup_contract | Gate 2 | dyec-agent | `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` now hard-verifies `DAYOA_BCLCONVERT_LANE_SPLIT = True`, `BCL_MERGE_LANE_FASTQS`, `BCL_FASTQ_LIST_INPUT_FILES`, `run_bclconvert_lane_fastqs_ready`, `rule run_bclconvert_lane:`, and the native DayOA BCL helper script references before BCL launch. The active profile patch sets `barcode_mismatches_index1: "0"`, `barcode_mismatches_index2: "0"`, and `merge_lane_fastqs: "false"`, and no longer requires removed staging/scratch BCL profile keys. Focused launcher test `tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables` passed; `python -m ruff check daylily_ec/scripts/daylily_run_omics_analysis_headnode.py tests/test_script_entrypoints.py` and `git diff --check` passed. | Native DayOA BCL implementation supersedes the temporary DYEC runtime rule patch; leaving mismatch settings empty would suppress the requested zero-mismatch sample-sheet injection, and merging lane FASTQs is unnecessary for BWA streaming. | DYEC launcher now fails hard if DayOA lacks native no-merge lane split and prepares validation runs with zero barcode mismatches and no lane FASTQ stitch. |

## Assumptions

- DYEC pins the highest final working DayOA release tag produced by this plan.
- If DayOA validation stops before a releasable tag, this ledger stops before catalog pin/release rows.
- Historical ledgers and archive/quarantine docs are not rewritten as active documentation.
- The DayOA environment-cache contract is path-based: `profile_freshness_warn.bash` substitutes `USER_REGSUB` and `HOSTNAME` in the active Snakemake profile, so DYEC must seed `/fsx/resources/environments/{conda,containers}/<user>/<hostname>` from the read-only reference runtime cache before rules first need an environment.
