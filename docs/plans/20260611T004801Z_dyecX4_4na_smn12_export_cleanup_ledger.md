# dyecX4 4NA SMN12/GBA Export Cleanup Ledger

Created: 2026-06-11T00:48:01Z

## Scope

Implement the approved plan for cluster `dyecX4`, AWS profile `lsmc`, region `us-west-2`:

- Inventory `/fsx/analysis_results/ubuntu/*` on the headnode.
- Export every current analysis directory with `dyec export` through DRA to `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/<analysis-id>/`.
- Treat `fsx_export.yaml` receipts as export authority; do not preflight destination emptiness.
- Do not delete any FSx directory until every ledger-listed export succeeds and the user gives a second explicit destructive approval after seeing the exact path list.
- Prepare DayOA to dry-run 8 4NA hybrid chip-pair analyses with full SMN12 orthogonal callers plus Gauchian and Cyrius.
- Run `dy-r ... -p -T 0 -k -j 500 -n` dry-runs in persistent `ubuntu` tmux login panes.
- If all eight `-n` dry-runs exit `0`, immediately run the same targets live with the same flags minus `-n`.

## Gate 0 Baseline

| Item | Evidence |
| --- | --- |
| DYEC repo | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` |
| DYEC git status | `## jem-dev...origin/jem-dev`; untracked `docs/plans/20260610T213029Z_hyb_only_4na_smn_calls.md` |
| DYEC git describe | `10.0.13` |
| DYEC CLI version | `dyec --json version` -> `10.0.11` |
| DayOA repo | `/Users/jmajor/projects/lsmc/daylily-omics-analysis` |
| DayOA git status | dirty before this ledger; see row `G0-002` |
| DayOA git describe | `10.0.3-dirty` |
| Cluster | `dyecX4` `CREATE_COMPLETE`; compute fleet `RUNNING`; headnode `i-05815cdeec4a6dad8`; FSx `fs-04960a3a07c091cf3` |
| Mount policy | Existing DYEC mounts reported `read_only: true`; no mount conversion to read-write is in scope |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G0-001 | orchestration | Create ledger and record Gate 0 baseline | SUCCESS | plan_amendment | Gate 0 | orchestrator | This file; `headnode_inventory.result.json` |  | Gate 0 recorded. |
| G0-002 | DayOA | Preserve pre-existing dirty work boundary before edits | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | Initial `git status --short --branch`; DayOA commit `b0e35b9`, annotated tag `10.0.4`, pushed to `origin/jem-dev` |  | Dirty work was committed and tagged before any headnode dry-run launch. |
| EXP-001 | export | Inventory exactly `/fsx/analysis_results/ubuntu/*` on dyecX4 headnode | SUCCESS | feature_implementation | Gate 0 | agent-export | `headnode_inventory.stdout.txt`; `export_inventory.json`; `export_inventory.tsv` |  | 53 `ubuntu` analysis directories inventoried. |
| EXP-002 | export | Launch DRA exports to `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/<analysis-id>/` capped at 4 concurrent exports | BLOCKED | legitimate_safety_handling | Gate 1 | agent-export | `exports/*/stderr.txt`; `4na_source_check.stdout.txt` DRA section | FSx returned `You have reached the maximum allowed DRAs for this filesystem.` | Export runner was stopped after 28 failed receipts to avoid producing 53 identical failures. |
| EXP-003 | export | Validate every export receipt has `status: success`, `task_lifecycle: SUCCEEDED`, `detached: true`, `delete_data_in_file_system: false` | BLOCKED | contract_test | Gate 1 | agent-export | Failed receipts under `exports/*/fsx_export.yaml` | No successful receipts were produced; all attempted receipts have export failure status. | Cleanup eligibility remains zero. |
| DEL-001 | cleanup | Print exact FSx paths eligible for deletion and obtain second destructive approval | BLOCKED | legitimate_safety_handling | Destructive approval | orchestrator |  | No export receipts are successful; no FSx analysis directory is eligible for deletion. | No delete command has been run. |
| DEL-002 | cleanup | Delete only ledger-listed `/fsx/analysis_results/ubuntu/<analysis-id>` paths after approval | BLOCKED | legitimate_safety_handling | Destructive approval | agent-export |  | Waiting for export success and second explicit destructive approval | Cannot proceed until approval gate is satisfied |
| DRA-001 | DRA capacity | Obtain separate approval before detaching temporary output-export DRAs created by the interrupted export attempt | BLOCKED | legitimate_safety_handling | Destructive approval | orchestrator | `4na_source_check.stdout.txt` DRA section | Three output-export DRAs are consuming DRA slots and no detach/delete approval has been given. | Awaiting explicit approval before any AWS DRA detach/delete operation. |
| DAYOA-001 | DayOA HTD | Enable Gauchian active rule include and route through `produce_htd_calls` | SUCCESS | feature_implementation | Gate 1 | agent-dayoa | DayOA commit `b0e35b9`; tests `test_htd_callers_contract.py`, `test_workflow_catalog.py` |  | Gauchian active include and HTD output routing are committed/tagged. |
| DAYOA-002 | DayOA HTD | Keep SMN12/SMAca/sma-finder/HapSMA/Cyrius in HTD and SMN12 orthogonal targets | SUCCESS | feature_implementation | Gate 1 | agent-dayoa | DayOA commit `b0e35b9`; tests `test_htd_callers_contract.py`, `test_workflow_catalog.py` |  | `produce_smn12_orthogonal_calls` and `produce_htd_calls` cover the requested caller set. |
| DAYOA-003 | DayOA resources | Increase supported threaded HTD/segdup rules to 128/192-class resources without adding unsupported tool flags | SUCCESS | feature_implementation | Gate 1 | agent-dayoa | DayOA commit `b0e35b9`; tests `test_sentdhiomr_resource_tuning.py`, `test_htd_callers_contract.py` |  | Threaded callers and HiOMR segdup resources tuned; single-thread Gauchian left without unsupported thread flag. |
| DAYOA-004 | DayOA model | Verify Sentieon HiOMR segdup LR model remains `DNAscopeONT2.3.bundle` | SUCCESS | contract_test | Gate 1 | agent-dayoa | DayOA focused pytest: `67 passed`; `test_sentieon_model_bundle_config.py` |  | Model contract covered by focused tests. |
| TEST-001 | tests | Run focused DayOA pytest/compile checks | SUCCESS | contract_test | Gate 2 | agent-validation | `python -m pytest -q ...` -> `67 passed in 0.52s`; `python -m compileall -q workflow/scripts/htd_calls_mqc.py workflow/scripts/smn12_orthogonal_calls_mqc.py` |  | Focused source checks passed before tag `10.0.4`. |
| STAGE-001 | 4NA setup | Derive 4NA sample/barcode/chip-pair inputs from existing manifests and create 8 dry-run analysis configs | BLOCKED | config_or_startup_contract | Gate 3 | agent-runs | `4na_inputs/4na_intended_analyses.tsv`; `4na_source_check.stdout.txt`; prior source docs `docs/smn12_and_friends_solo_Ailmn_ds_files_multiqc.md`, `docs/ONT_ILMN_SOLO_CMD_LOG.md` | dyecX4 does not have `/fsx/analysis_results/4_nas_ds_to_20x`, `/fsx/analysis_results/ubuntu/4_nas_ds_to_20x_realcopy`, or `/fsx/run_dir_mounts/ont-4coriells-chip{1..4}`. DRA max blocks creating staging/mount DRAs. | Eight intended `analysis_samples.tsv` files were generated locally, but no precheck/config/stage was run against missing sources. |
| RUN-001 | dry-run | Execute 8 `dy-r produce_smn12_orthogonal_calls produce_htd_calls produce_sentdhiomr_segdup -p -T 0 -k -j 500 -n` dry-runs in persistent tmux panes | BLOCKED | config_or_startup_contract | Gate 4 | agent-runs | `4na_source_check.stdout.txt` | Required 4NA source paths are not visible on the headnode. | No tmux workflow dry-runs launched. |
| RUN-002 | live-run | If all 8 dry-runs exit `0`, execute 8 live `dy-r produce_smn12_orthogonal_calls produce_htd_calls produce_sentdhiomr_segdup -p -T 0 -k -j 500` runs in the same persistent tmux workflow contract | BLOCKED | config_or_startup_contract | Gate 4b | agent-runs | User instruction on 2026-06-10: "if commands with -n run, please run w/out next" | Waiting for `RUN-001` to launch and pass for all eight analyses. | Authorized next step after dry-run success; no live runs launched yet. |
| FINAL-001 | final | Ledger has no `OPEN`, `IN_PROGRESS`, or `ATTEMPTING_BUGFIX` rows | BLOCKED | legitimate_safety_handling | Gate 5 | orchestrator | This ledger | Export cleanup and dry-run launch are blocked on the DRA capacity/destructive-approval gate. | Current state has no `OPEN`, `IN_PROGRESS`, or `ATTEMPTING_BUGFIX`; blocked rows remain. |

## Export Inventory

Frozen inventory count: `53`

Inventory files:

- `docs/plans/20260611T004801Z_dyecX4_4na_smn12_export_cleanup_logs/export_inventory.json`
- `docs/plans/20260611T004801Z_dyecX4_4na_smn12_export_cleanup_logs/export_inventory.tsv`

Destination pattern:

`s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/<analysis-id>/`

## Export Receipts

Attempted receipts: `28`

Outcome: blocked. The common failure was:

`Unable to create export data repository association: An error occurred (BadRequest) when calling the CreateDataRepositoryAssociation operation: You have reached the maximum allowed DRAs for this filesystem.`

The export runner was stopped before trying all 53 directories.

No successful receipt currently satisfies all cleanup prerequisites:

- `status: success`
- `task_lifecycle: SUCCEEDED`
- `detached: true`
- `delete_data_in_file_system: false`

## DRA Capacity Blocker

Read-only DRA inventory found ten associations on `fs-04960a3a07c091cf3`, including three temporary output-export associations from the interrupted export attempt:

| DRA | Lifecycle | FSx path | S3 path |
| --- | --- | --- | --- |
| `dra-017fbd3485261fb2c` | `CREATING` | `/analysis_results/ubuntu/ccv_dryrun_hybrid_ilmn_ont_snv_20260609T063015Z/` | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/ccv_dryrun_hybrid_ilmn_ont_snv_20260609T063015Z/` |
| `dra-0f9ff9f59c7a64530` | `CREATING` | `/analysis_results/ubuntu/ccv_dryrun_complete_genomics_mgi_snv_concordance_20260609T063015Z/` | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/ccv_dryrun_complete_genomics_mgi_snv_concordance_20260609T063015Z/` |
| `dra-0af1b3871d0ec466d` | `AVAILABLE` | `/analysis_results/ubuntu/ccv_dryrun_hybrid_ilmn_ont_snv_20260609T083613Z/` | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/ccv_dryrun_hybrid_ilmn_ont_snv_20260609T083613Z/` |

No DRA detach/delete operation has been run. Separate destructive approval is required before removing these associations.

## 4NA Dry-Run Analyses

Blocked before staging/launch.

Prepared local intent files:

- `docs/plans/20260611T004801Z_dyecX4_4na_smn12_export_cleanup_logs/4na_inputs/4na_intended_analyses.tsv`
- Eight per-analysis `analysis_samples.tsv` files under `docs/plans/20260611T004801Z_dyecX4_4na_smn12_export_cleanup_logs/4na_inputs/`

Prepared analysis ids:

| Analysis ID | Sample | Chip pair |
| --- | --- | --- |
| `hybonly_hybrid_hiomr_smn12_gba_na00232_chip1chip2_dryrun_20260611T004801Z` | `NA00232` | `chip1-chip2` |
| `hybonly_hybrid_hiomr_smn12_gba_na00232_chip3chip4_dryrun_20260611T004801Z` | `NA00232` | `chip3-chip4` |
| `hybonly_hybrid_hiomr_smn12_gba_na09677_chip1chip2_dryrun_20260611T004801Z` | `NA09677` | `chip1-chip2` |
| `hybonly_hybrid_hiomr_smn12_gba_na09677_chip3chip4_dryrun_20260611T004801Z` | `NA09677` | `chip3-chip4` |
| `hybonly_hybrid_hiomr_smn12_gba_na03986_chip1chip2_dryrun_20260611T004801Z` | `NA03986` | `chip1-chip2` |
| `hybonly_hybrid_hiomr_smn12_gba_na03986_chip3chip4_dryrun_20260611T004801Z` | `NA03986` | `chip3-chip4` |
| `hybonly_hybrid_hiomr_smn12_gba_na05164_chip1chip2_dryrun_20260611T004801Z` | `NA05164` | `chip1-chip2` |
| `hybonly_hybrid_hiomr_smn12_gba_na05164_chip3chip4_dryrun_20260611T004801Z` | `NA05164` | `chip3-chip4` |

Known source evidence:

- ILMN 20x S3 prefix: `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/4_nas_ds_to_20x_realcopy/`
- ONT chip S3 sources and historical mount paths are documented in `docs/ONT_ILMN_SOLO_CMD_LOG.md`.

dyecX4 source visibility check found these required pass-through paths missing:

- `/fsx/analysis_results/4_nas_ds_to_20x`
- `/fsx/analysis_results/ubuntu/4_nas_ds_to_20x_realcopy`
- `/fsx/run_dir_mounts/ont-4coriells-chip1`
- `/fsx/run_dir_mounts/ont-4coriells-chip2`
- `/fsx/run_dir_mounts/ont-4coriells-chip3`
- `/fsx/run_dir_mounts/ont-4coriells-chip4`

Because `dyec samples stage --config-only` requires all rows to use `STAGE_DIRECTIVE=pass_through` or `mounted_readonly`, and because S3 staging/mount creation requires additional DRAs, the eight dry-runs cannot be launched until DRA capacity is freed and the required data is made visible.

## Final Report

Current terminal state: blocked, not complete.

Completed:

- DayOA source prep committed and pushed as `10.0.4`.
- Focused source tests passed.
- Export inventory captured.
- Headnode source visibility captured.

Blocked:

- DRA export cannot proceed because FSx is at the DRA limit.
- No FSx analysis directory is eligible for deletion.
- 4NA dry-run staging/launch cannot proceed because required pass-through/mounted inputs are absent and DRA capacity is exhausted.
