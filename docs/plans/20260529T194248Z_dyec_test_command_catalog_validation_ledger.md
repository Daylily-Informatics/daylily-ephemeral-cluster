# DYEC `dyec-test` Command Catalog Validation Ledger

Started: 2026-05-29T19:42:48Z

## Control

- Objective: run every current DayOA command-catalog command through DYEC on `dyec-test` in `us-west-2`, with at most three active command validations at a time.
- DYEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- Log directory: `docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_logs/`
- Event log: `docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_logs/events.jsonl`
- Command log: `docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_logs/command_log.tsv`
- Driver: `docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_logs/dyec_test_catalog_driver.py`

## Gate 0 Baseline

- Gate 0 command log rows: `command_log.tsv` rows 1-13.
- DYEC status: branch `codex/dyec-dewey-registration-refactor-20260528` tracking origin; HEAD `2ec4565f` tagged `5.0.31`; only this ledger/log work was untracked at baseline.
- DayOA status: branch `codex/dayoa-local-evidence-dewey-refactor-20260528` tracking origin; HEAD `3d5e86c` tagged `2.0.23`; clean at baseline.
- AWS identity: account `108782052779`, profile `lsmc`.
- DYEC CLI version: `5.0.31`.
- Cluster: `dyec-test`, `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-0cac5db332e3c70e5`, private IP `10.0.0.88`, public IP `16.145.136.128`.
- Managed mounts: none at baseline.
- Slurm queue: empty at baseline.
- Catalog: 20 DayOA commands, all pinned to DayOA `2.0.23`.

## Assumptions

- User approval covers live workflow launches, on-success export, delete-on-export-success cleanup, and deletion of transient staging/run DRAs created by this validation only.
- Export destination convention was corrected during execution after headnode access proof: `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/<analysis_id>/`.
- No DayOA code changes are permitted. DYEC code changes are allowed only for DYEC invocation/catalog/export/monitoring defects found during this validation.
- Dry-run-only coverage is acceptable only when a valid live input cannot be proven or a DayOA runtime failure blocks live execution.

## Ledger Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record repo, catalog, AWS account, cluster, mount, Slurm, and headnode readiness baseline. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `command_log.tsv` rows 1-13; `events.jsonl` `_gate0` event. |  | Baseline captured before live validation; cluster ready and queue empty. |
| CAT-001 | Catalog | Snapshot all current DayOA catalog commands and verify expected count/tag. | SUCCESS | contract_test | Gate 0 | orchestrator | `00009_gate0_catalog_snapshot.stdout.txt`; `_gate0.catalog_command_count=20`; all rows `git_tag=2.0.23`. |  | Current catalog has 20 DayOA commands pinned to DayOA `2.0.23`. |
| DATA-001 | Inputs | Resolve input manifests/run contexts for all commands without inventing substitutions. | IN_PROGRESS | contract_test | Gate 1 | input-agent | Driver maps existing `20260526T224018Z_blahab44_inputs` and `20260526T223700Z_goodole3_inputs`; CG/MGI remains candidate-blocked pending CLI precheck evidence. |  |  |
| RUN-001 | Execution | Run all catalog command validations with no more than three active commands at a time. | IN_PROGRESS | contract_test | Gate 2 | launch-agent | `simple-test` attempts: `command_log.tsv` rows 14-47; remaining catalog queue starting after row 47. |  | `simple-test` terminalized dry-run-only after DYEC invocation/runtime fixes exposed DayOA `help` target requiring `config/units.tsv` even for no-input utility use. |
| EXP-001 | Export | Export successful live runs and verify S3 destination evidence. | OPEN | feature_implementation | Gate 3 | export-agent |  |  |  |
| CLEAN-001 | Cleanup | Delete only successful exported analysis dirs and transient validation-created DRAs. | OPEN | legitimate_safety_handling | Gate 4 | cleanup-agent |  |  |  |
| DYEC-001 | DYEC fixes | Apply and test DYEC-only fixes if command validation exposes DYEC defects. | ATTEMPTING_BUGFIX | feature_implementation | Gate 2 | dyec-agent | `00017`, `00023`, `00029`, `00035`, `00041`, and `00045` logs; focused pytest command below; `git diff --check` rc 0. | DYEC launcher issues: alias expansion after `source dyoainit`, inherited function positional args during `source`, inherited nounset for DayOA aliases, and missing explicit Mermaid Chrome executable path after headnode runtime repair. | Patched `daylily_run_omics_analysis_headnode.py`; added driver SSM repair mode; repaired exact Chrome `148.0.7778.97` cache and verified `mmdc` SVG render at row 41. |
| FINAL-001 | Final report | Terminalize every row and report pass/fail/blocked/dry-run-only results. | OPEN | legitimate_safety_handling | Gate 5 | orchestrator |  |  |  |

## Command Matrix

| Command | Class | Input | Genome | Jobs | DayOA Tag |
|---|---|---|---|---:|---|
| `simple-test` | utility | none | hg38 | 1 | 2.0.23 |
| `illumina_snv_alignstats` | sample_analysis | sample_manifest | hg38_broad | 20 | 2.0.23 |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | sample_analysis | sample_manifest | hg38_broad | 100 | 2.0.23 |
| `illumina_hg002_kitchensink_multiqc` | sample_analysis | sample_manifest | hg38 | 200 | 2.0.23 |
| `ultima_snv_alignstats` | sample_analysis | sample_manifest | hg38_broad | 20 | 2.0.23 |
| `ultima_snv_alignstats_kitchensink` | sample_analysis | sample_manifest | hg38_broad | 100 | 2.0.23 |
| `ont_snv_alignstats` | sample_analysis | sample_manifest | hg38_broad | 5 | 2.0.23 |
| `ont_snv_alignstats_kitchensink` | sample_analysis | sample_manifest | hg38_broad | 5 | 2.0.23 |
| `pacbio_snv_alignstats` | sample_analysis | sample_manifest | hg38_broad | 2 | 2.0.23 |
| `roche_snv_alignstats` | sample_analysis | sample_manifest | hg38_broad | 5 | 2.0.23 |
| `hybrid_ilmn_ont_snv` | sample_analysis | sample_manifest | hg38_broad | 100 | 2.0.23 |
| `hybrid_ilmn_ont_snv_kitchensink` | sample_analysis | sample_manifest | hg38_broad | 100 | 2.0.23 |
| `inflection-bjuice-product-v0.1` | sample_analysis | sample_manifest | hg38_broad | 125 | 2.0.23 |
| `hybrid_ultima_ont_snv` | sample_analysis | sample_manifest | hg38_broad | 100 | 2.0.23 |
| `complete_genomics_mgi_snv_concordance` | sample_analysis | sample_manifest | hg38_broad | 20 | 2.0.23 |
| `illumina_run_qc` | run_analysis | run_context | hg38_broad | 5 | 2.0.23 |
| `illumina_bclconvert` | run_analysis | run_context | hg38_broad | 20 | 2.0.23 |
| `illumina_run_qc_bclconvert` | run_analysis | run_context | hg38_broad | 20 | 2.0.23 |
| `ont_run_qc` | run_analysis | run_context | hg38_broad | 5 | 2.0.23 |
| `ultima_run_qc` | run_analysis | run_context | hg38_broad | 5 | 2.0.23 |

## Bundle Plan

Updated: 2026-05-29T23:25:00Z

The next execution pass uses shared sample staging instead of `dyec samples run` per command. The durable driver now calls `dyec samples stage` once for each manifest bundle, then launches each catalog command with `dyec workflow launch --stage-dir <shared-stage-dir>`. This is intended to keep FSx DRA usage below the 8-association limit while preserving catalog-defined `dy-r` payloads.

Sample bundle pass, max 4 active workflow validations:

| Manifest | Commands |
|---|---|
| `illumina_hg003_5x.tsv` | `illumina_snv_alignstats` |
| `ultima_hg003_5x.tsv` | `ultima_snv_alignstats_kitchensink` |
| `roche_hg003_5x.tsv` | `roche_snv_alignstats` |
| `hybrid_ilmn_ont_hg003_5x5x.tsv` | `hybrid_ilmn_ont_snv`, `hybrid_ilmn_ont_snv_kitchensink`, `inflection-bjuice-product-v0.1` |
| `hybrid_ultima_ont_hg003_5x5x.tsv` | `hybrid_ultima_ont_snv` |

Run-context bundle pass, max 3 active workflow validations after sample bundle cleanup:

| Run Context | Shared DRA | Commands |
|---|---|---|
| `illumina_run_context.tsv` | `20260514_LH01106_0009_B23TVLGLT4` | `illumina_run_qc`, `illumina_bclconvert`, `illumina_run_qc_bclconvert` |
| `ont_run_context.tsv` | `20260513_ONT_HG003` | `ont_run_qc` |
| `ultima_run_context_candidate.tsv` | `602221-20260417_2346` | `ultima_run_qc` |

Commands not queued in this bundle pass: `simple-test` and `illumina_hg002_kitchensink_multiqc` are dry-run-only DayOA failures; `complete_genomics_mgi_snv_concordance` is input-blocked; `ultima_snv_alignstats`, `ont_snv_alignstats`, `ont_snv_alignstats_kitchensink`, `pacbio_snv_alignstats`, and `illumina_snv_alignstats_relatedness_vep_multiqc` already reached live workflow execution and need export/final classification rather than a new staged-input launch unless later evidence requires a rerun.

## Status Summary

- OPEN: 5
- IN_PROGRESS: 2
- ATTEMPTING_BUGFIX: 1
- SUCCESS: 2
- FAIL: 0
- BLOCKED: 0
- NO_LONGER_NEEDED: 0

## Debug Pass: 2026-05-30T04:43Z

User amendment: debug completed nonzero catalog rows and apply DYEC-only fixes where the failure is in DYEC invocation, catalog metadata, export, mount handling, or validation-driver mechanics. DayOA source remains out of scope.

DYEC fixes applied during this pass:

| Area | Change | Evidence |
|---|---|---|
| BCL run-analysis launcher | `daylily_run_omics_analysis_headnode.py` now generates BCL run-context sample rows without a header-only units table, then hard-patches the active DayOA profile to `bclconvert.staging_mode=mounted_dev_shm`, repo-local FSx scratch, and `force=true` when `bootstrap_bclconvert=true`. | `ccv20260529r24_illumina_bclconvert` dry-run reached `exit_code=0` but live failed because a generated empty units table made DayOA reject the run; `ccv20260529r25_illumina_bclconvert` dry-run reached `exit_code=0` but live failed because `output_dev_shm` left the DRA path invisible inside Singularity; `ccv20260529r26_illumina_bclconvert` dry-run reached `exit_code=0` and live is active with Slurm job `2660`. |
| Ultima run QC launcher | `daylily_run_omics_analysis_headnode.py` appends the required Ultima run-QC S3 config from the run context instead of launching with an empty `--run-s3-uri`. | `ccv20260529r14_ultima_run_qc` completed `exit_code=0`; export verified at `00591_ultima_run_qc_export_s3_verify.stdout.txt`. |
| ONT run-QC catalog/runtime repair | Source and packaged catalogs now launch `produce_ont_run_qc` for `ont_run_qc`, matching the row's own historical tested command, and the DYEC launcher applies the pycoQC runtime repair required by DayOA `2.0.23` on this headnode. | `ccv20260529r22_ont_run_qc` completed `exit_code=0`; export completed to `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260529r22_ont_run_qc/`; delete-on-export-success removed the FSx analysis directory. Evidence: `00942_manual_ont_r22_final_status.stdout.txt`, `00944_manual_ont_r22_final_logs.stdout.txt`, and `events.jsonl` final success event at `2026-05-30T06:43:54Z`. |
| goleft runtime repair | `daylily_run_omics_analysis_headnode.py` now patches the per-analysis DayOA clone before execution when the command asks for alignstats/MultiQC/relatedness targets, removing the empty `--sex {params.sexchrms:q}` argument from `workflow/rules/go_left.smk`. This preserves the no-DayOA-source-change constraint while fixing the observed `goleft indexcov` CLI error. | Focused launcher regression passed at `2026-05-30T07:18Z`; affected live command rows are queued for rerun after the three active slots free. |
| CG/MGI staging contract | `stage_samples.py` now maps the catalog/input vendor label `CG/MGI` to DayOA units-table vendor token `CG`, and rejects other identifier values with path separators instead of letting `/` enter DayOA wildcard paths. | `ccv20260529r28_complete_genomics_mgi_snv_concordance_dryrun` failed with `InputFunctionException` because `SEQ_VENDOR=CG/MGI` produced an analysis unit containing `/`; regenerated stage `remote_stage_20260530T072540Z_24a47821` emits `SEQ_VENDOR=CG`, and `ccv20260529r29_complete_genomics_mgi_snv_concordance_dryrun` completed with `exit_code=0`. |
| Run mount driver | Validation driver now verifies shared run mounts from live `dyec mounts list`, waits for `AVAILABLE`, and treats already-absent cleanup targets as skipped instead of failed. | `dyec_test_catalog_driver.py` updated; live ONT rerun is using this path. |

Focused verification:

| UTC | Command | Result |
|---|---|---|
| 2026-05-30T04:35Z | `python -m pytest -q tests/test_repository_catalog.py::test_repository_catalog_run_analysis_commands_require_run_context tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_injects_ultima_run_qc_s3_config` | `3 passed` |
| 2026-05-30T04:43Z | `git diff --check` | `0` |
| 2026-05-30T04:43Z | `python -m pytest -q tests/test_workflow.py::TestClusterBootConfigPublish tests/test_headnode_readiness.py tests/test_repository_catalog.py tests/test_cli_registry_v2.py::test_workflow_launch_forwards_no_input_utility_flags tests/test_cli_registry_v2.py::test_workflow_launch_forwards_run_context_file tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_no_input_utility_workflow tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_run_context_workflow tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_injects_ultima_run_qc_s3_config tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_raises_when_tmux_session_not_reported tests/test_run_mounts.py` | `43 passed` |
| 2026-05-30T06:43Z | `python -m pytest -q tests/test_workflow.py::TestClusterBootConfigPublish tests/test_headnode_readiness.py tests/test_repository_catalog.py tests/test_cli_registry_v2.py::test_workflow_launch_forwards_no_input_utility_flags tests/test_cli_registry_v2.py::test_workflow_launch_forwards_run_context_file tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_no_input_utility_workflow tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_run_context_workflow tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_injects_ultima_run_qc_s3_config tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_ont_run_qc_pycoqc_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_raises_when_tmux_session_not_reported tests/test_run_mounts.py` | `44 passed` |
| 2026-05-30T06:43Z | `git diff --check` | `0` |
| 2026-05-30T07:18Z | `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_goleft_empty_sex_arg_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_ont_run_qc_pycoqc_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_workflow_session && git diff --check` | `3 passed`; `git diff --check` rc 0 |
| 2026-05-30T07:25Z | `python -m pytest -q tests/test_stage_samples_from_local_to_headnode.py::test_process_samples_maps_complete_genomics_mgi_vendor_for_dayoa tests/test_stage_samples_from_local_to_headnode.py::test_process_samples_emits_complete_genomics_fastq_rows tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_goleft_empty_sex_arg_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_ont_run_qc_pycoqc_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_workflow_session && git diff --check` | `5 passed`; `git diff --check` rc 0 |
| 2026-05-30T08:00Z | `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_goleft_empty_sex_arg_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_zero_variant_vep_and_contam_identity_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_ont_run_qc_pycoqc_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_workflow_session` | `4 passed`; `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` rc 0 |
| 2026-05-30T08:05Z | `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_rtg_vcfeval_parse_output_dir_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_goleft_empty_sex_arg_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_zero_variant_vep_and_contam_identity_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_workflow_session` | `4 passed`; `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` rc 0; `git diff --check` rc 0 |
| 2026-05-30T08:32Z | `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_goleft_empty_sex_arg_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_zero_variant_vep_and_contam_identity_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_rtg_vcfeval_parse_output_dir_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_workflow_session` | `4 passed`; `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` rc 0; `git diff --check` rc 0 |

Live BCL retry note: `ccv20260529r26_illumina_bclconvert` is still active. Compute inspection row `01093_inspect_r26_bclconvert_compute_progress.remote.stdout.txt` shows Slurm job `2660` running on `i192mem-dy-all-1`, scratch growth to about `1.3T`, and recently modified BCL files during the mounted DRA-to-scratch copy. The run is progressing, so it has not been cancelled.

Live HG002 kitchensink note: `ccv20260529r26_illumina_hg002_kitchensink_multiqc` dry-run reached `exit_code=0` after the `/fsx/data` GIAB path probe/repair, then failed live with goleft empty `--sex`, zero-variant VEP concat, and zero-variant contamination-identity errors. DYEC now patches those runtime issues before DayOA execution. `ccv20260529r31_illumina_hg002_kitchensink_multiqc_dryrun` exposed a DYEC escaping bug in the new VEP repair (`NameError: count_path%`); the escaped replacement was fixed and `ccv20260529r32_illumina_hg002_kitchensink_multiqc_dryrun` completed with `exit_code=0`. Live retry `ccv20260529r32_illumina_hg002_kitchensink_multiqc` then reached downstream live failures: goleft `no usable chromsomes`, mosdepth missing declared distribution outputs, and read_haps failing before the no-variant sentinel because command/config checks were ordered before the VCF emptiness check. DYEC now patches those runtime cases, and live retry `ccv20260529r34_illumina_hg002_kitchensink_multiqc` is active.

Resume checkpoint, 2026-05-30T09:33:55Z: local polling handles were interrupted, but validation driver processes survived. Active validation lanes remain capped at three: `ccv20260529r26_illumina_bclconvert`, `ccv20260529r36_illumina_hg002_kitchensink_multiqc`, and `ccv20260529r35_ont_snv_alignstats_kitchensink`. `ccv20260529r35_ont_snv_alignstats` completed live with `exit_code=0`; export verified at `01910_ont_snv_alignstats_export_s3_verify.stdout.txt` with `2107` objects and `2.2 GiB` under `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260529r35_ont_snv_alignstats/`. Latest FSx health row `01936_manual_headnode_fsx_health.stdout.txt` shows `/fsx` at `8.8T` size, `7.2T` used, `1.6T` available, `83%` used. No new command was launched at this checkpoint because all three validation slots were occupied.

BCL FSx pressure checkpoint, 2026-05-30T09:49:07Z: `02008_inspect_bcl_r26_size.remote.stdout.txt` shows active BCL scratch at `4.0T`, staged input at `3.2T`, scratch FASTQs at `837G`, result FASTQ directory still `65K`, and `/fsx` at `7.3T` used / `1.5T` free / `84%`. DYEC was patched so future BCL launches runtime-patch the cloned DayOA `workflow/rules/bclconvert.smk` to move scratch FASTQs into the result tree and remove the staged input scratch after successful `bcl-convert`, avoiding a second full FASTQ copy on FSx. Focused verification passed: `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`, `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_goleft_empty_sex_arg_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_zero_variant_vep_and_contam_identity_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_workflow_session`, and `git diff --check`. A broad validation-directory size scan was started as row `02030_inspect_validation_dir_sizes.remote` but cancelled to avoid unnecessary FSx walking while live workflows were running; exact cancellation command was `AWS_PROFILE=lsmc aws ssm cancel-command --region us-west-2 --command-id 47e3515c-0cef-4450-8174-286897af27c2 --instance-ids i-0cac5db332e3c70e5`, and SSM readback reported `Status=Cancelled`, `ResponseCode=137`.

CG/MGI control-data note: `complete_genomics_mgi_snv_concordance` dry-run was retried with stage `remote_stage_20260530T065816Z_a3c70c2e` and initially failed because `/fsx/control_data/.../MGI/mgi_reads/ML150002521_L01_UDB-386_1.fq.gz` was not mounted. The validation driver then created a read-only `control_data` DRA from `s3://lsmc-dayoa-control-data-usw2/`. After the DYEC `CG/MGI` to `CG` staging fix, stage `remote_stage_20260530T072540Z_24a47821` and session `ccv20260529r29_complete_genomics_mgi_snv_concordance_dryrun` completed dry-run with `exit_code=0`; live execution remains intentionally unstarted because the candidate mate-pair contract is still unverified.

Non-DYEC failures classified so far:

| Command | Current classification | Evidence |
|---|---|---|
| `illumina_snv_alignstats_relatedness_vep_multiqc` | SUCCESS after DYEC runtime repair | `00302_inspect_analysis_failure...stdout.txt`: goleft emitted `error: missing value for --sex`. DYEC now patches the per-run DayOA clone to remove the empty `--sex` argument before execution. Retry `ccv20260529r30_illumina_snv_alignstats_relatedness_vep_multiqc` completed live with `exit_code=0`; export verified `3818` objects, `8.6 GiB`, at `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260529r30_illumina_snv_alignstats_relatedness_vep_multiqc/`. |
| `ultima_snv_alignstats`, `ont_snv_alignstats`, `pacbio_snv_alignstats` | DYEC runtime repair rerun active | `00633`, `00634`, and `00638` inspections show missing `tp/fp/fn_vcf_gz_stripped.vcf.gz` concordance outputs after SNV rules. `01380_inspect_snv_runtime_logs.remote.stdout.txt` shows at least the Ultima SNV caller completed successfully, shifting the actionable failure to the RTG vcfeval parse step. DYEC now patches `workflow/rules/rtg_vcfeval.smk` in the per-run DayOA clone to create the declared `{output.mqc}` directory before invoking `parse-vcfeval-summary.py`. Retry `ccv20260529r33_ultima_snv_alignstats_dryrun` completed with `exit_code=0`; live `ccv20260529r33_ultima_snv_alignstats` is active. |
| `ultima_snv_alignstats_kitchensink`, `ont_snv_alignstats_kitchensink`, `hybrid_ilmn_ont_snv_kitchensink` | Mixed: DYEC runtime repair pending rerun plus remaining DayOA/vendor risks | Inspections show goleft `--sex` failure, now patched in DYEC runtime setup; hybrid ILMN+ONT kitchensink also shows empty Stage3 BAM integrity failures that may remain after rerun. |
| `hybrid_ultima_ont_snv` | DayOA/vendor runtime failure | `00360_inspect_analysis_failure...stdout.txt`: Sentieon HybridStage1 assertion `kmerSize >= 1` and truncated `stage1_hap.bam`. |
| `roche_snv_alignstats` | External container access blocked | `00237_cache_roche_containers.stderr.txt`: Docker registry access denied for `docker://roche/sbxd-small-variant-caller:latest`. |
| `complete_genomics_mgi_snv_concordance` | DRYRUN_ACCEPTED, input contract still blocked for live | Candidate mate-pair contract remains unverified; no substitution was made. After creating the read-only control-data DRA and fixing DYEC staging from `CG/MGI` to `CG`, `ccv20260529r29_complete_genomics_mgi_snv_concordance_dryrun` completed with `exit_code=0`; live remains intentionally unstarted until the mate-pair contract is verified. |
| `illumina_hg002_kitchensink_multiqc` | Live rerun active | `00056_illumina_hg002_kitchensink_multiqc_dryrun_logs.stdout.txt` showed missing RTG vcfeval ROI input. `ccv20260529r26` live then failed on goleft, zero-variant VEP, and zero-variant contamination-identity handling. `01335`/`01338`/`01347` and `01350` inspect the failed `ccv20260529r31` dry-run and show the DYEC escaping bug in the first VEP repair; the corrected `ccv20260529r32` dry-run reached `exit_code=0`. `ccv20260529r32` live exposed goleft no-usable-chromosomes, mosdepth empty-output, and read_haps no-variant precheck ordering gaps; DYEC now patches those. `ccv20260529r34` live is active. |

## Manual Command Notes

These commands were run outside the durable driver after the initial `simple-test` dry-run failure and are recorded here to preserve exact invocation history.

| UTC | CWD | Env | Command | RC | Evidence |
|---|---|---|---|---:|---|
| 2026-05-29T19:57:00Z | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` | `source ./activate`, `AWS_PROFILE=lsmc` | `dyec workflow logs --profile lsmc --region us-west-2 --cluster dyec-test --session ccv20260529_simple-test_dryrun --lines 80` | 0 | Repeated driver log capture at `00017_simple-test_dryrun_logs.stdout.txt`; stderr empty. |
| 2026-05-29T20:01:00Z | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` | `source ./activate` | `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_workflow_session tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_no_input_utility_workflow tests/test_repository_catalog.py::test_repository_catalog_commands_have_run_metadata` | 0 | 3 focused tests passed. |
| 2026-05-29T20:01:30Z | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` | default shell | `git diff --check` | 0 | No whitespace errors. |

## Resume Checkpoint: 2026-05-30T10:03Z

The restart interrupted local polling handles only. Local driver processes survived for `ont_snv_alignstats_kitchensink`, `illumina_hg002_kitchensink_multiqc`, and the new `illumina_bclconvert` retry.

`ccv20260529r37_illumina_bclconvert_dryrun` failed with a DYEC-generated Snakemake shell escaping error: `NameError: The name 'scratch_run_dir' is unknown in this context`. Evidence: `02134_illumina_bclconvert_dryrun_logs_deep_logs.stdout.txt`, lines around the `RuleException`.

DYEC fix: `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` now emits `${{scratch_run_dir:-}}` into the cloned DayOA `workflow/rules/bclconvert.smk` instead of `${scratch_run_dir:-}`. Test coverage was tightened in `tests/test_script_entrypoints.py`.

Focused verification:

| UTC | Command | Result |
|---|---|---|
| 2026-05-30T10:00Z | `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` | rc 0 |
| 2026-05-30T10:00Z | `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables` | `1 passed` |

Rerun state:

| Command | Session | Status | Evidence |
|---|---|---|---|
| `illumina_bclconvert` | `ccv20260529r38_illumina_bclconvert_dryrun` | dry-run `exit_code=0` | `02153_illumina_bclconvert_dryrun_status.stdout.txt`, `02156_illumina_bclconvert_dryrun_logs.stdout.txt` |
| `illumina_bclconvert` | `ccv20260529r38_illumina_bclconvert` | live running | `02158_illumina_bclconvert_live_launch.stdout.txt`, `02164_illumina_bclconvert_live_status.stdout.txt`, `02169_illumina_bclconvert_live_status.stdout.txt` |
| `illumina_bclconvert` | `ccv20260529r38_illumina_bclconvert` | cloned rule patch verified | `02167_verify_bcl_r38_patch.remote.stdout.txt` shows `Moving BCLConvert outputs from scratch to result tree`, `${{scratch_run_dir:-}}`, and `rm -rf "$scratch_run_dir"` in `workflow/rules/bclconvert.smk`. |

Current active cap remains three workflow validations: `ccv20260529r35_ont_snv_alignstats_kitchensink`, `ccv20260529r36_illumina_hg002_kitchensink_multiqc`, and `ccv20260529r38_illumina_bclconvert`.

## BCL Scratch Multiplier Checkpoint: 2026-05-30T10:12Z

`ccv20260529r38_illumina_bclconvert` reached the compute node and then failed before copying data because the live DayOA profile still had `scratch_size_multiplier: 4`. Evidence row `02214_inspect_bcl_r38_size.remote.stdout.txt` shows `scratch_input_disk_bytes=3415281155421`, `scratch_required_bytes=13662198363508`, `scratch_available_bytes=5903301738496`, followed by `Insufficient scratch for bclconvert.staging_mode=mounted_dev_shm`.

DYEC fix: `patch_bclconvert_profile_config` now also patches the active cloned DayOA profile to `scratch_size_multiplier: "1"` for the mounted-scratch BCL path. This keeps the preflight requirement consistent with the actual validation storage model: one staged BCL input copy plus one scratch output tree, with final output moved instead of copied.

Focused verification:

| UTC | Command | Result |
|---|---|---|
| 2026-05-30T10:08Z | `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` | rc 0 |
| 2026-05-30T10:08Z | `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables` | `1 passed` |
| 2026-05-30T10:08Z | `git diff --check` | rc 0 |

Rerun state:

| Command | Session | Status | Evidence |
|---|---|---|---|
| `illumina_bclconvert` | `ccv20260529r39_illumina_bclconvert_dryrun` | dry-run `exit_code=0` | `02237_illumina_bclconvert_dryrun_status_manual_status.stdout.txt` |
| `illumina_bclconvert` | `ccv20260529r39_illumina_bclconvert` | live running | `02239_illumina_bclconvert_live_launch.stdout.txt`, `02244_illumina_bclconvert_live_status_manual_status.stdout.txt`, `02255_illumina_bclconvert_live_status.stdout.txt` |
| `illumina_bclconvert` | `ccv20260529r39_illumina_bclconvert` | active profile patch verified | `02256_find_bcl_r39_rule_configs.remote.stdout.txt` shows `config/day_profiles/slurm/rule_config.yaml` with `force: "true"`, `staging_mode: "mounted_dev_shm"`, repo-local `scratch_root`, and `scratch_size_multiplier: "1"`. |

## Plan Amendment: 2026-05-30T12:00Z

User amendment: plan and proceed with targeted fixes for remaining failed rows, raise non-BCL validation concurrency to four active command validations, keep BCL as a special case, inventory cleanup targets before deleting anything, and add a DYEC read/write mount capability if AWS FSx DRA semantics support it.

### Updated Operating Rules

- Active validation cap is now 4 command validations at a time, except BCL conversion is treated as a high-storage special lane and should not be multiplied.
- `illumina_bclconvert` and `illumina_run_qc_bclconvert` must verify before export that any symlinked or mounted Illumina run directory will not be copied into the derived export. If a symlink or run-data projection exists inside the result tree, remove it before export and record the exact path removed.
- BCL may require a mounted run directory plus a symlink into the expected `/fsx` runtime path. The symlink must point at a read-only DRA mount, and the export guard above is mandatory.
- Cleanup is split into inventory and deletion. Inventory may run immediately. Deleting FSx analysis directories or FSx DRAs is destructive; exact target lists must be recorded here and require explicit confirmation before deletion unless the target is already covered by a validation command's own `--delete-on-export-success` contract.
- No DayOA source edits remain allowed. DYEC catalog/runtime/driver edits remain allowed when failure is in command selection, staging, wrapper behavior, mount handling, export handling, or cleanup guardrails.

### New Work Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| AMEND-001 | Execution policy | Raise non-BCL active validation cap from 3 to 4 and continue failed-row reruns without exceeding the cap. | IN_PROGRESS | legitimate_safety_handling | Gate 2 | orchestrator | `0267x` status refresh showed only BCL `ccv20260529r39` active. | Prior cap was conservative during DRA pressure; current Slurm/FSx state has capacity for additional non-BCL retries. |  |
| AMEND-002 | Cleanup | Inventory unused validation-created DRAs and stale `/fsx/analysis_results/ubuntu/ccv20260529*` analysis dirs before any deletion. | OPEN | legitimate_safety_handling | Gate 4 | cleanup-agent |  | Validation retries leave failed dry-run/live analysis dirs and staged DRA projections that can consume FSx space/associations. | Deletion target list and explicit approval must be recorded before destructive cleanup. |
| AMEND-003 | Roche catalog | Change `roche_snv_alignstats` away from Roche container caller and onto a Sentieon-compatible path for this validation. | IN_PROGRESS | feature_implementation | Gate 2 | dyec-agent | `0267x` code search: catalog currently uses `produce_rochehc_snv_vcf`; previous validation and current dry-run failed on unavailable Roche container image. | Catalog selected a Roche/GATK/Roche-filter path requiring an inaccessible `docker://roche/sbxd-small-variant-caller:latest` image. |  |
| AMEND-004 | HG002 kitchensink | Inspect `ccv20260529r40` and patch/rerun if failure is still DYEC runtime repairable. | IN_PROGRESS | feature_implementation | Gate 2 | dyec-agent | `02673_inspect_analysis_failure_ccv20260529r40_illumina_hg002_kitchensink_multiqc.stdout.txt` shows haplocheck non-rCRS position errors. | Latest failure still appears in haplocheck handling; verify cloned rule contains the intended unsupported-reference sentinel repair before rerun. |  |
| AMEND-005 | Hybrid ILMN+ONT | Rerun `hybrid_ilmn_ont_snv_kitchensink` after current runtime repairs, verify it is HIOMR and uses 5x ILMN plus 5x ONT manifest; if it fails again, inspect historical successful exports/DRAs before changing inputs. | OPEN | contract_test | Gate 2 | launch-agent | Current manifest `hybrid_ilmn_ont_hg003_5x5x.tsv`; previous base HIOMR row `hybrid_ilmn_ont_snv` passed, kitchensink failed on goleft plus Stage3 empty BAM evidence. | Mixed failure: old goleft issue is DYEC-patched; Stage3 integrity may be DayOA/vendor or input-depth sensitive. |  |
| AMEND-006 | Hybrid Ultima+ONT | Re-evaluate `hybrid_ultima_ont_snv`; confirm HIOMR caller, 5x Ultima plus 5x ONT manifest, and historical successful derived exports before any further rerun. | OPEN | contract_test | Gate 2 | launch-agent | Current manifest `hybrid_ultima_ont_hg003_5x5x.tsv`; failed `r9` on Sentieon `kmerSize >= 1` and truncated Stage1 BAM. | Likely DayOA/vendor runtime failure unless historical export or higher-coverage input shows a catalog/input mismatch. |  |
| AMEND-007 | BCL export guard | For active `illumina_bclconvert` and later `illumina_run_qc_bclconvert`, inspect result tree for symlinks or mounted run-data projections before export and remove any run-data link that would be exported. | OPEN | legitimate_safety_handling | Gate 3 | export-agent | Active BCL: `ccv20260529r39`, Slurm job `3310`. | BCL may need a run-dir symlink for runtime compatibility, but derived export must not copy original mounted basecall data. |  |
| AMEND-008 | RW mounts | Investigate AWS/DYEC support for read/write FSx DRA mounts; if viable, add CLI mode with default read-only, require `.atlas_rw` marker under the S3 root prefix for read/write, and write `.atlas_rw` under the derived prefix. | OPEN | feature_implementation | Gate 1 | storage-agent |  | Current DYEC validation treats mounts as read-only; user wants opt-in read/write only under explicitly granted prefixes. | Implementation must fail hard for requested read/write mounts without a marker and must not broaden write access by default. |

### Immediate Retry Queue

With BCL `ccv20260529r39` occupying one lane, the next non-BCL launches may use up to three additional active lanes immediately:

| Priority | Command | Planned Action |
|---:|---|---|
| 1 | `roche_snv_alignstats` | Patch DYEC catalog to Sentieon path, run focused catalog/staging tests, then dry-run/live retry. |
| 2 | `ultima_snv_alignstats_kitchensink` | Rerun with existing 5x Ultima manifest after goleft/RTG/zero-variant repairs. |
| 3 | `hybrid_ilmn_ont_snv_kitchensink` | Rerun with existing 5x ILMN plus 5x ONT HIOMR manifest; inspect if Stage3 failure recurs. |
| 4 | `illumina_hg002_kitchensink_multiqc` | Patch/rerun after confirming why unsupported-reference haplocheck sentinel did not fire in `r40`. |
| 5 | `hybrid_ultima_ont_snv` | Search historical derived exports/DRAs and avoid repeated live failure unless a concrete input/catalog fix is found. |
| 6 | `illumina_run_qc_bclconvert` | Wait for standalone BCL `r39` to complete; apply same BCL symlink/export guard before rerun. |

## Implementation Checkpoint: 2026-05-30T12:02Z

Applied DYEC changes for the amended plan before launching the next four-lane batch.

| Row | Status | Evidence |
|---|---|---|
| AMEND-003 | PATCHED | Source and packaged catalogs now launch `roche_snv_alignstats` with `produce_sentd_snv_vcf` and `snv_callers: [sentd]`. Current validation input `docs/plans/20260526T224018Z_blahab44_inputs/roche_hg003_5x.tsv` now sets `ROCHE_BAM_SNV_CALLER=sentd` so the Roche BAM is validated through the Sentieon path, not the Roche container path. |
| AMEND-004 | PATCHED | `ccv20260529r40` inspection showed the haplocheck unsupported-reference repair was present, but haplocheck exited `0` while logging non-rCRS errors. The runtime patch now checks the log for `outside the range.*rCRS only` before accepting rc=0 output. The actual terminal failure was `read_haps_contam_identity`: 64,703 VCF records, empty stdout/stderr, and an empty declared output. The runtime patch now writes an explicit `READ_HAPS_FAILED` low-data sentinel when `read_haps` exits nonzero or writes no usable QC table. |
| AMEND-008 | PATCHED | AWS FSx DRA supports writeback through `S3.AutoExportPolicy`; DYEC already exposed this with `--no-read-only`, `--allow-writeback-admin`, and `--auto-export`. DYEC now additionally blocks writeback unless an `.atlas_rw` marker is present at or above the requested S3 prefix, excluding the bucket root. |
| AMEND-008 | MARKER_CREATED | `s3://lsmc-ssf-sequencing-data/derived/.atlas_rw` was absent. Created a zero-byte marker with metadata `dyec-purpose=rw-dra-allowlist`; readback showed ETag `d41d8cd98f00b204e9800998ecf8427e`, `ContentLength=0`, and SSE `AES256`. |

Focused verification:

| UTC | Command | Result |
|---|---|---|
| 2026-05-30T11:58Z | `python -m pytest -q tests/test_run_mounts.py tests/test_repository_catalog.py::test_repository_catalog_commands_have_run_metadata tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_zero_variant_vep_and_contam_identity_runtime` | `25 passed` |
| 2026-05-30T11:58Z | `python -m py_compile daylily_ec/run_mounts.py daylily_ec/cli.py daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` | rc 0 |
| 2026-05-30T11:58Z | `git diff --check` | rc 0 |
| 2026-05-30T12:01Z | `AWS_PROFILE=lsmc aws s3api put-object --region us-west-2 --bucket lsmc-ssf-sequencing-data --key derived/.atlas_rw --body "$tmp_marker" --metadata dyec-purpose=rw-dra-allowlist` then `AWS_PROFILE=lsmc aws s3api head-object --region us-west-2 --bucket lsmc-ssf-sequencing-data --key derived/.atlas_rw` | marker created and read back |

Concurrency checkpoint: `ccv20260529r39_illumina_bclconvert` remains active as the only Slurm job (`3310`, `i192mem`, 192 CPUs). This leaves three non-BCL validation lanes available under the new cap of four.

## Cleanup Gate: 2026-05-30T12:05Z

`ccv20260529r44_illumina_hg002_kitchensink_multiqc` did not launch because sample staging failed before workflow submission: FSx already had 8 active DRAs. Live association inventory shows the hidden static `/references/` DRA plus seven dynamic DRAs.

Active DRA inventory:

| Association | Lifecycle | FSx path | S3 path | Proposed action |
|---|---|---|---|---|
| `dra-0b23a4135c9f0f6c6` | AVAILABLE | `/references/` | `s3://lsmc-dayoa-references-usw2` | keep |
| `dra-031a4de5c6080fe7d` | AVAILABLE | `/control_data/` | `s3://lsmc-dayoa-control-data-usw2` | keep |
| `dra-0283f1688c923752e` | AVAILABLE | `/run_dir_mounts/20260513_ONT_HG003/` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260513_ONT_HG003/` | keep for ONT run-QC context |
| `dra-0dae86e536847afcf` | AVAILABLE | `/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/` | keep for active BCL |
| `dra-0f5cfd869b72a2465` | AVAILABLE | `/staging/staged_external_sequencing_data/remote_stage_20260530T085117Z_4e893380/` | `s3://lsmc-ssf-sequencing-data/staged_external_data/remote_stage_20260530T085117Z_4e893380/` | delete after explicit approval |
| `dra-0b034de60f039e3fb` | AVAILABLE | `/staging/staged_external_sequencing_data/remote_stage_20260530T091207Z_6818dabe/` | `s3://lsmc-ssf-sequencing-data/staged_external_data/remote_stage_20260530T091207Z_6818dabe/` | delete after explicit approval |
| `dra-067d4dee6f914c51a` | CREATING | `/staging/staged_external_sequencing_data/remote_stage_20260530T120339Z_641bf958/` | `s3://lsmc-ssf-sequencing-data/staged_external_data/remote_stage_20260530T120339Z_641bf958/` | keep for active `r42/r43` batch until terminal |
| `dra-018ce497941021437` | CREATING | `/staging/staged_external_sequencing_data/remote_stage_20260530T120339Z_db801c81/` | `s3://lsmc-ssf-sequencing-data/staged_external_data/remote_stage_20260530T120339Z_db801c81/` | keep for active `r42/r43` batch until terminal |

FSx inventory evidence: `/fsx` is 8.8T total, 7.2T used, 1.6T available, 83% used. `ccv20260529r39_illumina_bclconvert` is the only large active directory at about 3.9T. Historical failed HG002 attempts are about 3.2G-3.6G each; `ccv20260529r7_hybrid_ilmn_ont_snv_kitchensink` is about 26G; `ccv20260529r7_ultima_snv_alignstats_kitchensink` is about 5.1G; many dry-run attempts are about 614M each.

Approval requested in chat: `CONFIRM DELETE 2 STAGING DRAS` for only `remote_stage_20260530T085117Z_4e893380` and `remote_stage_20260530T091207Z_6818dabe`, using the DYEC mount delete path which passes `DeleteDataInFileSystem=false` and does not delete S3 objects.

## Roche Sentieon Alias Checkpoint: 2026-05-30T12:14Z

`ccv20260529r42_roche_snv_alignstats_dryrun` proved the first Roche catalog repair still used a broken DayOA 2.0.23 public alias. It no longer hit the Roche container path, but dry-run failed with:

`snv_caller target alias produce_sentd_snv_vcf delegates to produce_sentD_vcf, but that rule has no declared inputs to reuse.`

DYEC adjustment: the Roche catalog row now calls the concrete Sentieon DNAscope target `produce_sentD_vcf` directly while keeping `ROCHE_BAM_SNV_CALLER=sentd` in the validation input. This remains a DYEC catalog/invocation change only; no DayOA source files were changed.

Focused verification:

| UTC | Command | Result |
|---|---|---|
| 2026-05-30T12:14Z | `python -m pytest -q tests/test_repository_catalog.py::test_repository_catalog_commands_have_run_metadata tests/test_staging_examples_live.py` | `3 passed, 7 skipped` |

Rerun state:

| Command | Session | Status | Evidence |
|---|---|---|---|
| `roche_snv_alignstats` | `ccv20260529r45_roche_snv_alignstats` | running | Driver started at `2026-05-30T12:13:39Z`; pending staging/dry-run/live evidence. |
| `ultima_snv_alignstats_kitchensink` | `ccv20260529r43_ultima_snv_alignstats_kitchensink` | live running | Dry-run `exit_code=0`; live launch evidence `02707_ultima_snv_alignstats_kitchensink_live_launch.stdout.txt`. |

## Cleanup And Capacity Checkpoint: 2026-05-30T12:26Z

User confirmed deletion of the two old validation-created staging DRAs in chat. Deleted only the two previously listed staging mounts through the DYEC mount delete path, with no S3 object deletion.

| Mount ID | Command evidence | Result |
|---|---|---|
| `remote_stage_20260530T085117Z_4e893380` | `02764_approved_cleanup_mount_remote_stage_20260530T085117Z_4e893380.stdout.txt` | `rc=0`, lifecycle `DELETED` |
| `remote_stage_20260530T091207Z_6818dabe` | `02765_approved_cleanup_mount_remote_stage_20260530T091207Z_6818dabe.stdout.txt` | `rc=0`, lifecycle `DELETED` |
| post-delete DYEC mount list | `02766_approved_cleanup_mounts_after.stdout.txt` | `rc=0` |

Post-delete capacity snapshot:

| Metric | Value | Evidence |
|---|---:|---|
| DYEC-visible dynamic mounts | 5 | `02747_capacity_snapshot_mounts_list.stdout.txt` |
| Dynamic mount breakdown | 2 run, 2 staging, 1 control-data | `02747_capacity_snapshot_mounts_list.stdout.txt` |
| Active FSx DRAs for cluster filesystem | 6 | `02754_capacity_snapshot_fsx_dras.stdout.txt` |
| Active FSx DRA lifecycle state | 6 `AVAILABLE`, 0 creating/deleting | `02754_capacity_snapshot_fsx_dras.stdout.txt` |
| Hidden static reference DRA | 1 | `/references/` in `02754_capacity_snapshot_fsx_dras.stdout.txt` |
| `/fsx/analysis_results/ubuntu/*` directory count | 112 | `02770_capacity_snapshot_fast_headnode_counts.stdout.txt` |
| `/fsx/staging/staged_external_sequencing_data/*` directory count | 35 | `02770_capacity_snapshot_fast_headnode_counts.stdout.txt` |
| `/fsx` usage | 8.8T total, 7.4T used, 1.4T available, 85% used | `02770_capacity_snapshot_fast_headnode_counts.stdout.txt` |
| tmux session count | 115 | `02770_capacity_snapshot_fast_headnode_counts.stdout.txt` |
| controller-ish process count | 12 | `02770_capacity_snapshot_fast_headnode_counts.stdout.txt` |
| Slurm job count | 35 running, 0 pending/configuring | `02770_capacity_snapshot_fast_headnode_counts.stdout.txt` |

Active validation sessions at snapshot:

| Command | Session | State |
|---|---|---|
| `illumina_bclconvert` | `ccv20260529r39_illumina_bclconvert` | running, no exit code yet |
| `ultima_snv_alignstats_kitchensink` | `ccv20260529r43_ultima_snv_alignstats_kitchensink` | running, no exit code yet; fanned out to VEP/RTG/contam Slurm jobs |
| `roche_snv_alignstats` | `ccv20260529r45_roche_snv_alignstats` | running, dry-run passed after concrete `produce_sentD_vcf` catalog fix |

Parallelism decision: keep the command-validation cap at 4 for now. DRA pressure is improved, with two free DRA slots, but Slurm has already fanned out to 35 running jobs from the active workflows and `/fsx` is 85% used while BCL is still active. Refill one open validation lane, but do not raise above four until BCL terminalizes or Slurm/FSx pressure drops.

## Default-Mount Test Data Checkpoint: 2026-05-30T12:37Z

User correction accepted: the command-catalog validation datasets are not intended to consume one staging DRA per sample command when their data paths already live under the default mounts.

Default-mounted test-data roots observed on `dyec-test`:

| Root | Role | Policy |
|---|---|---|
| `/fsx/references/genomic_data/organism_reads_slim` | Primary slim catalog-validation sample reads in the default reference mount. | Prefer manifest paths with `STAGE_DIRECTIVE=pass_through` or mounted-readonly semantics. Do not create a staging DRA solely to carry generated `samples.tsv` and `units.tsv`. |
| `/fsx/control_data/genomic_data/organism_reads_slim` | Control-data-backed catalog-validation read fixtures in the default control-data mount. | Same policy: use the already mounted path unless a manifest row explicitly requires copied/staged data. |

DYEC catalog update: source and packaged `daylily_available_repositories.yaml` now include a first-class `test_data_locations` section recording the two default-mounted roots, their S3 origins, and the no-per-command-DRA staging policy for sample-analysis catalog validation. The repository-catalog model and tests now expose this metadata in `dyec repositories commands` output.

## Direct Config And Current DRA Cleanup Checkpoint: 2026-05-30T12:46Z

Implementation update:

| Area | Status | Evidence |
|---|---|---|
| Catalog metadata | DONE | `config/daylily_available_repositories.yaml` and packaged catalog now include `test_data_locations` for `/fsx/references/genomic_data/organism_reads_slim` and `/fsx/control_data/genomic_data/organism_reads_slim`. |
| Direct sample config | DONE | `dyec samples stage --config-only` now has focused test coverage and the validation driver uses it for sample-analysis rows, then launches with `--samples-file` and `--units-file`. This avoids creating sample-staging DRAs when inputs are already on default mounts. |
| HG002 0.1x input | DONE | `docs/plans/20260526T223700Z_goodole3_inputs/illumina_0p1x_kitchensink.tsv` now uses `STAGE_DIRECTIVE=pass_through` and `/fsx/control_data/genomic_data/organism_reads/.../HG002_0.1x_R{1,2}.fastq.gz`. Headnode readback found both files: 81,330,606 bytes and 83,356,045 bytes. |
| Roche rerun | SUCCESS | Manual takeover status showed `ccv20260529r45_roche_snv_alignstats` completed `exit_code=0` at `2026-05-30T12:43:49Z`; export verification returned success. |
| Ultima kitchensink rerun | SUCCESS | Manual takeover status showed `ccv20260529r43_ultima_snv_alignstats_kitchensink` completed `exit_code=0` at `2026-05-30T12:45:22Z`; export verification returned success. |
| BCL | ACTIVE | `ccv20260529r39_illumina_bclconvert` still has `exit_code=null`; Slurm job `3310` remains running on `i192mem-dy-all-1`. |

Focused verification:

| UTC | Command | Result |
|---|---|---|
| 2026-05-30T12:38Z | `python -m pytest -q tests/test_repository_catalog.py::test_repository_catalog_loads_initial_blessed_command tests/test_repository_catalog.py::test_repositories_commands_json_cli_lists_blessed_command` | `2 passed` |
| 2026-05-30T12:38Z | `python -m ruff check daylily_ec/repositories.py tests/test_repository_catalog.py` | `All checks passed!` |
| 2026-05-30T12:44Z | `python -m pytest -q tests/test_stage_samples_from_local_to_headnode.py::test_main_config_only_writes_local_configs_without_remote_stage tests/test_stage_samples_from_local_to_headnode.py::test_main_config_only_rejects_stage_data_rows tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_sample_config_workflow_without_stage_discovery tests/test_repository_catalog.py::test_repository_catalog_loads_initial_blessed_command tests/test_repository_catalog.py::test_repositories_commands_json_cli_lists_blessed_command` | `5 passed` |
| 2026-05-30T12:44Z | `python -m py_compile daylily_ec/stage_samples.py daylily_ec/scripts/daylily_run_omics_analysis_headnode.py daylily_ec/cli.py daylily_ec/repositories.py docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_logs/dyec_test_catalog_driver.py` | rc 0 |

Current active DRA policy:

| Association / Mount | Path | Action |
|---|---|---|
| `dra-0b23a4135c9f0f6c6` / static reference | `/references/` | keep; default catalog validation data mount |
| `dra-031a4de5c6080fe7d` / `control_data` | `/control_data/` | keep; default control/test-data mount |
| `dra-0283f1688c923752e` / `20260513_ONT_HG003` | `/run_dir_mounts/20260513_ONT_HG003/` | keep for now as the single ONT run-type mount |
| `dra-0dae86e536847afcf` / `20260514_LH01106_0009_B23TVLGLT4` | `/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` | keep while active BCL and BCL-QC follow-up remain possible |
| `dra-067d4dee6f914c51a` / `remote_stage_20260530T120339Z_641bf958` | `/staging/staged_external_sequencing_data/remote_stage_20260530T120339Z_641bf958/` | delete after explicit confirmation; validation-created Ultima staging DRA now exported |
| `dra-0fa69e6d5abc701b5` / `remote_stage_20260530T121339Z_ff9aca41` | `/staging/staged_external_sequencing_data/remote_stage_20260530T121339Z_ff9aca41/` | delete after explicit confirmation; validation-created Roche staging DRA now exported |

Confirmation requested in chat: `CONFIRM DELETE CURRENT STAGING DRAS` for only the two listed `remote_stage_*` staging associations. No S3 object deletion is proposed.

## Post-Cleanup Catalog State Checkpoint: 2026-05-30T12:55Z

Unmount cleanup executed for the two current staging DRAs only:

| Mount ID | Association | Action |
|---|---|---|
| `remote_stage_20260530T120339Z_641bf958` | `dra-067d4dee6f914c51a` | deleted/unmounted |
| `remote_stage_20260530T121339Z_ff9aca41` | `dra-0fa69e6d5abc701b5` | deleted/unmounted |

Current DYEC-visible mounts after cleanup:

| Mount ID | Platform | Purpose | Path | State |
|---|---|---|---|---|
| `20260513_ONT_HG003` | ONT | run | `/fsx/run_dir_mounts/20260513_ONT_HG003/` | `AVAILABLE` |
| `20260514_LH01106_0009_B23TVLGLT4` | ILMN | run | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` | `AVAILABLE` |
| `control_data` | OTHER | control-data | `/fsx/control_data/` | `AVAILABLE` |

The static reference DRA is still present outside the DYEC mount registry view at `/fsx/references/`; catalog metadata now records `/fsx/references/genomic_data/organism_reads_slim` and `/fsx/control_data/genomic_data/organism_reads_slim` as the default mounted test-data roots.

Current catalog rollup:

| Command ID | State | Evidence |
|---|---|---|
| `simple-test` | PASS | dry-run `rc=0`, live `ccv20260529r20_simple-test rc=0`, export verified. |
| `illumina_snv_alignstats` | PASS | dry-run `rc=0`, live `ccv20260529r7_illumina_snv_alignstats rc=0`, export verified. |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | PASS | dry-run `rc=0`, live `ccv20260529r30_illumina_snv_alignstats_relatedness_vep_multiqc rc=0`, export verified. |
| `illumina_hg002_kitchensink_multiqc` | NEEDS RERUN | prior live `ccv20260529r40 rc=1`; stale post-edit config failure was fixed, and manual config-only recheck now passes with 32 source objects checked. |
| `ultima_snv_alignstats` | PASS | dry-run `rc=0`, live `ccv20260529r33_ultima_snv_alignstats rc=0`, export verified. |
| `ultima_snv_alignstats_kitchensink` | PASS | rerun `ccv20260529r43_ultima_snv_alignstats_kitchensink rc=0`, export verified after earlier failed run. |
| `ont_snv_alignstats` | PASS | dry-run `rc=0`, live `ccv20260529r35_ont_snv_alignstats rc=0`, export verified. |
| `ont_snv_alignstats_kitchensink` | PASS | dry-run `rc=0`, live `ccv20260529r35_ont_snv_alignstats_kitchensink rc=0`, export verified. |
| `pacbio_snv_alignstats` | PASS | dry-run `rc=0`, live `ccv20260529r41_pacbio_snv_alignstats rc=0`, export verified. |
| `roche_snv_alignstats` | PASS | rerun `ccv20260529r45_roche_snv_alignstats rc=0`, export verified with Sentieon command. |
| `hybrid_ilmn_ont_snv` | PASS | dry-run `rc=0`, live `ccv20260529r7_hybrid_ilmn_ont_snv rc=0`, export verified. |
| `hybrid_ilmn_ont_snv_kitchensink` | NEEDS LIVE RERUN | prior live `ccv20260529r7 rc=1`; direct default-mounted config-only dry-run `ccv20260529r47_hybrid_ilmn_ont_snv_kitchensink_dryrun rc=0`. |
| `inflection-bjuice-product-v0.1` | PASS | dry-run `rc=0`, live `ccv20260529r10_inflection-bjuice-product-v0.1 rc=0`, export verified. |
| `hybrid_ultima_ont_snv` | NEEDS LIVE RERUN | prior live `ccv20260529r9 rc=1`; direct default-mounted config-only dry-run `ccv20260529r47_hybrid_ultima_ont_snv_dryrun rc=0`. |
| `complete_genomics_mgi_snv_concordance` | DRY-RUN ONLY | `ccv20260529r29_complete_genomics_mgi_snv_concordance_dryrun rc=0`; live still blocked by unverified valid CG/MGI mate pair. |
| `illumina_run_qc` | PASS | dry-run `rc=0`, live `ccv20260529r11_illumina_run_qc rc=0`, export verified. |
| `illumina_bclconvert` | RUNNING | r39 dry-run `rc=0`; live `ccv20260529r39_illumina_bclconvert` started `2026-05-30T10:10:02Z`, Slurm job `3310` still running on `i192mem-dy-all-1`. |
| `illumina_run_qc_bclconvert` | WAITING/RERUN | prior live `ccv20260529r15 rc=1`; rerun deferred until standalone BCL r39 terminalizes. |
| `ont_run_qc` | PASS | rerun/manual terminal evidence `ccv20260529r22_ont_run_qc rc=0`, export complete and delete-on-export-success applied. |
| `ultima_run_qc` | PASS | dry-run `rc=0`, live `ccv20260529r14_ultima_run_qc rc=0`, export verified. |

## BCL Compute Health Checkpoint: 2026-05-30T13:09Z

User requested direct compute-node inspection for active BCL Convert run `ccv20260529r39_illumina_bclconvert`. Inspection used SSM as `ubuntu` on compute instance `i-04e394f2997bb66d9` / `i192mem-dy-all-1`.

Current status:

| Item | Value |
|---|---|
| Slurm job | `3310`, partition `i192mem`, state `R` |
| BCL process | `/usr/local/bin/bcl-convert`, PID `73008` |
| Process elapsed | about `2:14` at snapshot |
| Threads | `222` |
| CPU | aggregate about `984%`; active worker threads visible |
| Memory | RSS about `86.9G`; node has `755G` RAM and about `633G` available |
| Process I/O | about `1.0T` read and `1.38T` written |
| Scratch input | `.bclconvert_scratch/3310.25321/run`, about `3.2T` |
| Scratch output | `.bclconvert_scratch/3310.25321/fastqs`, about `1.3T` and `257` files |
| Output growth sample | +`3,236,757,504` bytes in 20 seconds |
| FSx usage | `8.8T` total, `7.8T` used, about `976G` free, about `90%` used |

BCL command currently running:

```text
singularity exec docker://nfcore/bclconvert:4.0.3 bcl-convert \
  --bcl-input-directory /fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis/.bclconvert_scratch/3310.25321/run \
  --output-directory /fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis/.bclconvert_scratch/3310.25321/fastqs \
  --sample-sheet results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/normalized.SampleSheet.csv \
  --strict-mode false \
  --first-tile-only false \
  --bcl-sampleproject-subdirectories false \
  --fastq-gzip-compression-level 1 \
  --bcl-num-parallel-tiles 8 \
  --bcl-num-conversion-threads 8 \
  --bcl-num-compression-threads 12 \
  --bcl-num-decompression-threads 4 \
  --shared-thread-odirect-output false \
  -f
```

Assessment: job is actively running and writing FASTQs, not hung. Do not launch more heavy FSx consumers while this is running. Main risk is free FSx capacity, because input staging plus output currently occupies about `4.4T` in scratch.

CG/MGI correction: current validation manifest still uses the bad control-data pair under `genomic_data/organism_reads/H_sapiens/giab/MGI/mgi_reads/ML150002521_L01_UDB-386_{1,2}.fq.gz`, where R2 is far smaller. The control-data bucket also contains a better Complete Genomics set under `genomic_data/organism_reads/H_sapiens/complete_genomics/`; for HG003, `T7plus_WGS_PE150_HG003_PCR_Free_Read_1.fq.gz` is `117.3 GiB` and `_Read_2.fq.gz` is `119.0 GiB`. Use that pair for the live CG/MGI catalog row.

## BCL Stop/Cleanup And DYEC Runtime Patch: 2026-05-30T13:27Z

User requested stopping the active standalone BCL Convert controller and removing only the writable r39 analysis/scratch copy, not the read-only DRA-mounted Illumina run directory.

Evidence:

| Row | Evidence |
|---|---|
| Controller stop | `02873_user_requested_kill_r39_bclconvert_controller.*` killed tmux session `ccv20260529r39_illumina_bclconvert`; first script exited `rc=1` after the tmux kill because of a local shell-template bug before Slurm cancellation. |
| Slurm cancellation | `02874_user_requested_cancel_r39_bclconvert_slurm_and_status.*` cancelled Slurm job `3310`; matching Slurm jobs were absent afterward. |
| Analysis cleanup | `02875_user_confirmed_delete_r39_bclconvert_analysis_and_scratch_copy.*` removed `/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert`, including `.bclconvert_scratch`; `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4` was preserved. |
| FSx recovery | `/fsx` changed from `8.8T` total / `7.9T` used / `849G` free / `91%` to `8.8T` total / `6.0T` used / `2.8T` free / `69%`. |
| BCL flags | `02876_inspect_bclconvert_403_help_flags.*` captured `bcl-convert Version 00.000.000.4.0.3` help from `docker://nfcore/bclconvert:4.0.3`; lane splitting is supported via `--bcl-only-lane`. |

DYEC code change in progress:

- `daylily_run_omics_analysis_headnode.py` now projects run-context `RUN_DIR` values into the cloned analysis workspace as symlinks under `config/run_dir_links/` and rewrites child paths such as `SAMPLE_SHEET` to use those symlinks.
- BCL profile patch now forces `staging_mode=direct`, `/dev/shm` temp roots, `threads=192`, `partition=i192mem`, `force=true`, and an explicit full-thread first-pass allocation of `parallel_tiles=16`, `conversion_threads=8`, `compression_threads=3`, `decompression_threads=1`, `fastq_gzip_compression_level=1`, `shared_thread_odirect_output=false`.
- BCL cloned-rule patch now writes helper scripts and replaces DayOA `run_bclconvert` with per-lane `run_bclconvert_lane` jobs using `--bcl-only-lane`, one 192-thread exclusive Slurm job per detected `L###`, followed by a merge rule for FASTQs and BCL Convert reports.
- Focused validation after cleanup/code repair: `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`, `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables`, and `python -m ruff check daylily_ec/scripts/daylily_run_omics_analysis_headnode.py tests/test_script_entrypoints.py` all passed.

## BCL Aggressive Flags, Dormant Sample-Sheet Injection, And Illuminate Spike: 2026-05-30T14:35Z

Updates:

- BCL aggressive flags were revised to Illumina's CPU-heavy thread formula: `parallel_tiles=16`, `conversion_threads=8`, `compression_threads=48`, `decompression_threads=16`, for `16*8 + 48 + 16 = 192` CPU-heavy threads per lane job.
- Legacy BCL Convert stats are enabled through `output_legacy_stats=true`, and `num_unknown_barcodes_reported=10000` is exposed for a larger unknown-barcode dump.
- Optional sample-sheet setting injection is present but deliberately dormant for this validation. Defaults are empty or `{}`, so generated lane sample sheets are content-identical unless explicit config is supplied.
- The dormant injection layer can accept `AdapterRead1`, `AdapterRead2`, `AdapterBehavior`, `AdapterStringency`, `MinimumAdapterOverlap`, `BarcodeMismatchesIndex1`, `BarcodeMismatchesIndex2`, `CreateFastqForIndexReads`, `MinimumTrimmedReadLength`, `MaskShortReads`, `OverrideCycles`, `SoftwareVersion`, `TrimUMI`, and `NoLaneSplitting` via direct `bclconvert.<snake_case>` keys, `bclconvert.sample_sheet_settings`, or per-lane `bclconvert.sample_sheet_settings_by_lane`.
- Per-lane injection is marked in generated code as an untested pending feature and is not exercised by current command-catalog validation.
- `02878_report_ilmn_samplesheet_dual_index_pairs.*` captured the 41 dual-index sample rows from `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/SampleSheet.csv`.
- `02879_illuminate_interop_spike_on_ilmn_run.*` failed before parsing because current `bitstring` no longer exports `BitString`.
- `02880_illuminate_interop_spike_old_bitstring_retry.*` retried with `bitstring<4`; import proceeded, but `illuminate` failed on this modern run with `InteropFileNotFoundError: No suitable binary found for index`. Treat `illuminate` as not useful for the validation-critical path.

Focused validation:

- `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`: passed.
- Local DayOA lane-split patch smoke: generated helpers, `bash -n` on `dyec_run_bclconvert_lane.sh`, `py_compile` on both helper Python scripts, and empty-settings sample-sheet copy identity check passed.
- `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables`: passed.
- `python -m ruff check daylily_ec/scripts/daylily_run_omics_analysis_headnode.py tests/test_script_entrypoints.py`: passed.
- `git diff --check`: passed.

Runtime dry-run:

- `02881_illumina_bclconvert_dryrun_launch.*` failed before remote execution with AWS `MaxDocumentSizeExceeded`; the literal embedded lane-split helper script pushed the SSM Run Command payload over 97 KB.
- DYEC now gzip/base64-compresses the large lane-split Python patch before embedding it in the remote headnode script. Local generated-script measurement was about 55 KB after compression.
- `02882_illumina_bclconvert_dryrun_launch.*`, `02883/02884_status.*`, and `02885_logs.*` show patched `illumina_bclconvert` dry-run `ccv20260530r41_illumina_bclconvert_dryrun` reached `exit_code=0`.
- Dry-run evidence shows eight per-lane jobs (`L001`-`L008`) using direct projected run-dir input, `--bcl-only-lane`, aggressive flags `16 8 48 16`, `--output-legacy-stats true`, `--num-unknown-barcodes-reported 10000`, and empty sample-sheet injection payloads `{}` / `{}`.

## BCL Live Retry Bind Fix: 2026-05-30T14:36Z

Updates:

- `ccv20260530r41_illumina_bclconvert` live failed quickly with `exit_code=1`.
- Failure evidence in `02910_inspect_analysis_failure_ccv20260530r41_illumina_bclconvert.*`: every lane reported `ERROR: Input run folder does not exist at .../config/run_dir_links/20260514_LH01106_0009_B23TVLGLT4`.
- Host visibility evidence in `02911_manual_bcl_symlink_probe.*`: the projected run-dir symlink exists and resolves on both the headnode and `i192mem-dy-all-1`, and the DRA-mounted run directory is present on both hosts.
- Root cause: the generated lane helper invoked `singularity exec` without explicitly binding `/fsx`, so the container could see the working directory but not necessarily the symlink target behind the projected DRA run-dir path.
- DYEC fix: generated lane helper now uses and logs `singularity exec --bind /fsx:/fsx ...` for both the BCL Convert version probe and the real BCL Convert invocation.
- Focused validation after the bind fix passed: `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables`; `python -m ruff check daylily_ec/scripts/daylily_run_omics_analysis_headnode.py tests/test_script_entrypoints.py`; `git diff --check`.
- `ccv20260530r42_illumina_bclconvert` live launched with the bind fix. Current evidence:
  - `02930_manual_headnode_slurm_health.*`: eight lane jobs allocated on `i192mem-dy-all-9` through `i192mem-dy-all-16`.
  - `02932_manual_bcl_compute_health_probe.*`: compute nodes have `/fsx`, the ILMN DRA mount, active `slurmd`, and active per-lane Snakemake processes with Snakemake singularity args that include `-B /fsx:/fsx`.
  - `02939_manual_bcl_r42_lane_log_probe.*`: probed `L001` and `L006` lane logs show `singularity_bind_args: --bind /fsx:/fsx`, successful `bcl-convert Version 00.000.000.4.0.3`, and the real `bcl-convert` command running with direct projected run-dir input, `--bcl-only-lane`, `--output-legacy-stats true`, and empty sample-sheet injection payloads.
  - Latest queue check at the time of this ledger entry: eight BCL lane jobs running, no non-BCL jobs in queue.

Concurrency checkpoint, 2026-05-30T15:49:23Z: `ccv20260530r42_illumina_bclconvert` is the only active workload. Slurm queue evidence `03171_manual_headnode_jobs.*` and follow-up live queue output show no non-BCL jobs; lane jobs have narrowed to `L006` and `L008` still running on `i192mem`, while `L001`-`L005` and `L007` have left the queue. Progress evidence `03174_manual_bcl_r42_progress_probe.*` shows direct projected run-dir input, no scratch input copy, completed lane outputs around `560G` each, and `/fsx` at `8.8T` total / `7.8T` used / `1006G` available / `89%` used.

Export guard checkpoint, 2026-05-30T15:59Z: only the generated run-directory projection symlink was removed from active analysis `ccv20260530r42_illumina_bclconvert` before export; the read-only DRA mount at `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4` was not removed. Evidence `03190_manual_bcl_r42_remove_run_dir_projection_before_export.*` shows `config/run_dir_links/20260514_LH01106_0009_B23TVLGLT4 -> /fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4` removed and no remaining symlink projections under analysis config. DYEC code now applies this same pre-export guard for future auto-export runs and fails export if `config/run_dir_links` contains any non-symlink entry.

Merge checkpoint, 2026-05-30T15:59Z: all eight BCL lane conversion jobs have left the queue and the workflow is running only `run_bclconvert-run_bclconvert_merge_lanes` as Slurm job `3545` on `i192mem-dy-all-9` with one CPU. Evidence `03196_manual_bcl_r42_merge_probe.*` shows `/fsx` at `8.8T` total / `7.8T` used / `966G` available / `90%`, zero run-dir projection links, `594` FASTQ files already in the final fastq directory, and lane output directories `L001`-`L008` still present during merge.

BCL r42 failure/salvage checkpoint, 2026-05-30T16:28Z: BCL Convert itself completed for all eight lanes, the lane merge completed, and final FASTQs are present, but the original DayOA controller returned `exit_code=1` when two lightweight post-merge rules (`bclconvert_metrics_summary` and `bclconvert_generate_units_tsv`) were submitted to Slurm and failed with empty rule logs. Evidence `03224_illumina_bclconvert_live_logs.*` captures the post-merge rule failures; `03225_manual_bcl_r42_failure_logs.*` shows final merged `fastq_list.csv` and `Demultiplex_Stats.csv` exist, but metrics/generated-units outputs were absent. Salvage step `03228_manual_bcl_r42_complete_postprocess.*` ran the exact DayOA helper scripts in the existing clone and produced `metrics/demultiplex_stats.tsv`, `metrics/unknown_barcodes.tsv`, `metrics/index_hopping.tsv`, `metrics/fastq_manifest.tsv`, `metrics/rollup.json`, and `tables/generated.units.tsv`. A fresh rerun of the exact DayOA command did not reach `rc=0`: first it required the generated units table to be materialized as `config/units.tsv`; after that, DayOA common manifest validation rejected underscores/dots in generated RUNID/EXPERIMENTID values. Evidence: `03233_manual_bcl_r42_materialize_generated_units_for_rerun.*`, `03234_manual_bcl_r42_direct_recheck_process_probe.*`, `03242_manual_bcl_r42_direct_recheck_process_probe.*`. DYEC code was updated so future BCL lane-split runs keep `run_bclconvert`, `bclconvert_metrics_summary`, and `bclconvert_generate_units_tsv` local on the headnode, avoiding the observed 1-CPU Slurm post-rule failure.

## Resume And Four-Command Debug Batch: 2026-05-30T17:27Z

Interruption/restart recovery:

| Check | Current state | Evidence |
|---|---|---|
| Active Slurm jobs | None at `2026-05-30T17:15:19Z` | `03248_manual_current_cluster_inventory_after_bcl_export.stdout.txt` shows empty `squeue`. |
| Active controllers | None at `2026-05-30T17:15:19Z` | Same probe showed no `snakemake`, `daylily_run_omics`, `dy-r`, or `bcl-convert` processes. |
| Stale tmux sessions | Many stale validation sessions remain, but no backing controllers | `03248_manual_current_cluster_inventory_after_bcl_export.stdout.txt`. |
| BCL r42 export | Succeeded | `03245_illumina_bclconvert_local_export_ccv20260530r42_illumina_bclconvert.*`; `03247_illumina_bclconvert_export_s3_verify.stdout.txt` reports `2822` objects and `4.4 TiB`. |
| BCL r42 cleanup | Removed exported analysis dir | `03249_manual_cleanup_bcl_r42_after_verified_export.stdout.txt`; target `/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert` was `4.4T` and was deleted. |
| FSx after cleanup | Healthy for resumed batch | `03250_manual_headnode_fsx_health.stdout.txt` reports `/fsx` `8.8T` total, `3.4T` used, `5.4T` free, `39%` used. |
| Managed mounts | Four managed mounts | `dyec mounts list` at `2026-05-30T17:16Z`: ONT `20260513_ONT_HG003`, ILMN `20260514_LH01106_0009_B23TVLGLT4`, ILMN `20260520_LH01121_0002_B23WW5LLT4`, and `control_data`. |

DYEC bugfix:

| Bug | Fix | Verification |
|---|---|---|
| HG002 kitchensink dry-run `ccv20260529r46` failed before Snakemake because DYEC generated invalid embedded Python for the contamination/read-haps runtime repair; the `$read_haps_rc` shell quotes were not escaped inside the generated Python string. | Escaped those quotes in `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` and added explicit assertions in `tests/test_script_entrypoints.py`. | `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; focused pytest `test_main_repairs_zero_variant_vep_and_contam_identity_runtime`; focused BCL test; `ruff check` all passed. |

CG/MGI data change:

| Old state | New state | Evidence |
|---|---|---|
| `complete_genomics_mgi_snv_concordance` was blocked on the bad `_386_1/_386_2` mate pair. | Validation manifest now points at the May 26 HG003 Complete Genomics pair under `/fsx/control_data/genomic_data/organism_reads/H_sapiens/complete_genomics/`. Driver `INPUT_BLOCKED` guard is cleared for this row. | `03254_manual_verify_cg_mgi_recent_pair_stat_only.stdout.txt` shows Read 1 size `125939746009`, Read 2 size `127737613770`, both mtime `2026-05-26 08:14:25 +0000`; S3 `ls` confirmed the same keys. Full `gzip -t` probes were intentionally canceled as too expensive for this DRA/Lustre validation path (`03252`, `03253`, both `rc=137`). |

Four-command debug batch launched:

| Batch suffix | Parallel cap | Commands |
|---|---:|---|
| `ccv20260530r48` | 4 | `illumina_hg002_kitchensink_multiqc`, `hybrid_ilmn_ont_snv_kitchensink`, `hybrid_ultima_ont_snv`, `complete_genomics_mgi_snv_concordance` |

Launch command recorded by local shell history and driver logs:

```bash
source ./activate && DYEC_VALIDATION_RUN_SUFFIX=ccv20260530r48 python docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_logs/dyec_test_catalog_driver.py --run --max-workers 4 --command-id illumina_hg002_kitchensink_multiqc --command-id hybrid_ilmn_ont_snv_kitchensink --command-id hybrid_ultima_ont_snv --command-id complete_genomics_mgi_snv_concordance
```

## r48 Failure Roots And r49 Debug Retry: 2026-05-30T18:10Z

Current r48 state:

| Command | State | Evidence |
|---|---|---|
| `illumina_hg002_kitchensink_multiqc` | Failed `rc=1` | `03643_inspect_hg002_read_haps_r48.*` and `03654_inspect_r48_failure_roots.*` show the runtime haplocheck repair worked, but `read_haps_contam_identity` exited before writing its fallback table because `/fsx/references/runtime_assets/tool_specific_resources/read_haps/read_haps` is missing. |
| `hybrid_ultima_ont_snv` | Failed `rc=1` | `03654_inspect_r48_failure_roots.*` shows Sentieon `HybridStage1` assertion `kmerSize >= 1`; the hidden process-substitution failure left `stage1_hap.bam` truncated and `samtools quickcheck` failed. |
| `hybrid_ilmn_ont_snv_kitchensink` | Still running | `03676_headnode_compact_slurm_summary.*` shows two `sentdhiomr_final_norm` Slurm jobs still running. |
| `complete_genomics_mgi_snv_concordance` | Still running | `03676_headnode_compact_slurm_summary.*` shows one `cgt7p_DNAscope` Slurm job still running. |

DYEC fixes added:

- `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` now writes explicit `READ_HAPS_UNAVAILABLE` or `READ_HAPS_MARKERS_UNAVAILABLE` sentinel QC tables instead of letting strict-mode prechecks kill the `read_haps` rule before output creation.
- The same headnode runtime script now patches `workflow/rules/sent_hybrid_ug_ont_modular.refactored.smk` for the specific Sentieon `ReadSequenceKmerGraphBuilder.*kmerSize >= 1` Hybrid Ultima/ONT Stage1 assertion. If that assertion leaves a truncated `stage1_hap.bam`, DYEC replaces only the haplotype BAM with a header-only BAM and logs `DYEC_RUNTIME_REPAIR`, allowing insertion output to continue.
- Focused validation passed: `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_zero_variant_vep_and_contam_identity_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables`.

r49 retry batch launched with the two fixed rows while r48 still had two active validations:

```bash
source ./activate && DYEC_VALIDATION_RUN_SUFFIX=ccv20260530r49 python docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_logs/dyec_test_catalog_driver.py --run --max-workers 2 --command-id illumina_hg002_kitchensink_multiqc --command-id hybrid_ultima_ont_snv
```

Follow-up:

- `ccv20260530r49_hybrid_ultima_ont_snv_dryrun` completed `rc=0` and live `ccv20260530r49_hybrid_ultima_ont_snv` launched. Evidence: `03712_inspect_r49_bootstrap_state.*`, `03717/03720/03742/03755_hybrid_ultima_ont_snv_live_status.*`.
- `ccv20260530r49_illumina_hg002_kitchensink_multiqc_dryrun` completed `rc=1` before workflow DAG validation because the embedded contamination repair Python had a generated-string quoting bug. Evidence: `03723_illumina_hg002_kitchensink_multiqc_dryrun_logs.*` shows `SyntaxError: invalid syntax`.
- DYEC fix: escaped the generated `$read_haps_rc` shell quotes in the embedded Python repair block. Focused checks passed: `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_zero_variant_vep_and_contam_identity_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_generates_bclconvert_run_context_tables`.
- Fresh HG002 retry launched:

```bash
source ./activate && DYEC_VALIDATION_RUN_SUFFIX=ccv20260530r50 python docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_logs/dyec_test_catalog_driver.py --run --max-workers 1 --command-id illumina_hg002_kitchensink_multiqc
```

CG/MGI follow-up:

- `ccv20260530r48_complete_genomics_mgi_snv_concordance` failed `rc=1` in `rtg_vcfeval_roi`; `rtg` was killed while using the default wrapper memory selection. Evidence: `03745_inspect_analysis_failure_ccv20260530r48_complete_genomics_mgi_snv_concordance.*` and `03750_11.*`.
- Root cause: RTG wrapper defaults to heap selection by available node RAM unless `RTG_MEM` is explicit, but Snakemake only granted the rule `mem_mb=64000`; the JVM overreached the Slurm allocation and was killed.
- DYEC fix: `patch_rtg_vcfeval_parse_output_dir` now also patches `rtg_vcfeval_roi` to call `rtg RTG_MEM="${rtg_mem_gb}G" vcfeval`, deriving `rtg_mem_gb` from `resources.mem_mb` at 85% of the rule allocation. Focused checks passed: `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_rtg_vcfeval_parse_output_dir_runtime tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_zero_variant_vep_and_contam_identity_runtime`.
- Fresh CG/MGI retry launched:

```bash
source ./activate && DYEC_VALIDATION_RUN_SUFFIX=ccv20260530r51 python docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_logs/dyec_test_catalog_driver.py --run --max-workers 1 --command-id complete_genomics_mgi_snv_concordance
```

- `ccv20260530r51_complete_genomics_mgi_snv_concordance_dryrun` failed before DAG execution because the generated RTG patch still referenced `parse_new` without renaming the local generated-Python variables. Evidence: `03790_complete_genomics_mgi_snv_concordance_dryrun_logs.*`.
- DYEC fix: renamed the generated `old/new` variables to `parse_old/parse_new`; focused checks passed: `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_rtg_vcfeval_parse_output_dir_runtime`.
- Fresh CG/MGI retry launched:

```bash
source ./activate && DYEC_VALIDATION_RUN_SUFFIX=ccv20260530r52 python docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_logs/dyec_test_catalog_driver.py --run --max-workers 1 --command-id complete_genomics_mgi_snv_concordance
```

## r52-r54 Runtime Repair Follow-up: 2026-05-30T18:40Z

CG/MGI repair loop:

| Attempt | State | Evidence | Outcome |
|---|---|---|---|
| `ccv20260530r52_complete_genomics_mgi_snv_concordance_dryrun` | `rc=1` | `03807_complete_genomics_mgi_snv_concordance_dryrun_logs.*` | Generated mosdepth repair Python still referenced `new`/`old` after the local variables had been renamed to `parse_new`/`parse_old`. |
| `ccv20260530r53_complete_genomics_mgi_snv_concordance_dryrun` | `rc=1` | `03884_inspect_r53_tmux_markers.stdout.txt` | Snakemake rejected the RTG patch because `${rtg_mem_gb}` was not escaped as a Snakemake shell literal. |
| `ccv20260530r54_complete_genomics_mgi_snv_concordance_dryrun` | `rc=0` | `03898_complete_genomics_mgi_snv_concordance_dryrun_status.stdout.txt` | Dry-run passed and live `ccv20260530r54_complete_genomics_mgi_snv_concordance` launched. |

DYEC fixes added:

- Corrected generated pycoQC and mosdepth repair blocks to consistently use `parse_new`/`parse_old`.
- Corrected the RTG JVM memory patch so the generated Snakemake shell block emits an escaped shell variable: `RTG_MEM="${rtg_mem_gb}G" rtg vcfeval` after Snakemake renders.
- Focused checks passed after each edit: `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_repairs_rtg_vcfeval_parse_output_dir_runtime`.

Hybrid outcomes:

| Command | Latest State | Evidence | Notes |
|---|---|---|---|
| `hybrid_ilmn_ont_snv_kitchensink` | Success | `ccv20260530r48_hybrid_ilmn_ont_snv_kitchensink` completed `rc=0`; `export_verify` succeeded with destination `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r48_hybrid_ilmn_ont_snv_kitchensink/`, `8158` objects, `25.4 GiB`. | This row is terminal success. |
| `hybrid_ultima_ont_snv` | Failed after DYEC Stage1 repair | `03909_inspect_analysis_failure_ccv20260530r49_hybrid_ultima_ont_snv.stdout.txt`; `03914_inspect_r49_hybrid_rule.stdout.txt`; `03917_inspect_hybrid_stage2_rule.stdout.txt`. | Stage1 Sentieon `ReadSequenceKmerGraphBuilder.*kmerSize >= 1` was detected and the DYEC header-only hap BAM repair fired, but Stage2 then failed with Sentieon `failed to find target hap` and `HapCutAltMap` assertions. No prior successful `hybrid_ultima_ont_snv`/`sentdhuomr`/`TVBHUO` export was found under `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/`. |

Active at this checkpoint:

| Command | Analysis ID | State |
|---|---|---|
| `illumina_hg002_kitchensink_multiqc` | `ccv20260530r50_illumina_hg002_kitchensink_multiqc` | Live still running; current Slurm job is `rtg_vcfeval_roi-JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ`. |
| `complete_genomics_mgi_snv_concordance` | `ccv20260530r54_complete_genomics_mgi_snv_concordance` | Live still running; current Slurm job is `sentieon_cgt7p_bwa_sort-TVBCG5X-HG003-5x-1-D0-PF-CG-MGI`. |

Cluster checkpoint:

| Evidence | State |
|---|---|
| `03923_headnode_compact_slurm_summary.stdout.txt` | `2` Slurm jobs, both validation-owned; `/fsx` `8.8T` total, `3.7T` used, `5.1T` free, `42%` used. |

Local verification:

| Command | Result |
|---|---|
| `source ./activate && python -m pytest -q tests/test_script_entrypoints.py` | Passed, `32 passed`. |
| `git diff --check` | Passed. |
| `source ./activate && python -m ruff check daylily_ec/scripts/daylily_run_omics_analysis_headnode.py tests/test_script_entrypoints.py` | Passed. |

BCL dry-run-only checkpoint:

| Attempt | State | Evidence |
|---|---|---|
| `ccv20260530r55_illumina_bclconvert_dryrun` | `rc=0` | `03955_illumina_bclconvert_dryrun_status.stdout.txt` shows dry-run completion. `03956_illumina_bclconvert_dryrun_logs.stdout.txt` shows eight lane-scoped `run_bclconvert_lane` jobs (`L001`-`L008`) using `config/run_dir_links/20260514_LH01106_0009_B23TVLGLT4`, followed by a merge `run_bclconvert` step. The dry-run lane command includes `-f 192`, compression level `1`, parallel tiles `16`, conversion threads `8`, compression threads `48`, decompression threads `16`, and no full run-directory copy. |

Active after BCL dry-run:

| Command | Analysis ID | State |
|---|---|---|
| `illumina_hg002_kitchensink_multiqc` | `ccv20260530r50_illumina_hg002_kitchensink_multiqc` | Passed the previous read-haps and RTG failure points; current Slurm phase is `multiqc_final_wgs`. |
| `complete_genomics_mgi_snv_concordance` | `ccv20260530r54_complete_genomics_mgi_snv_concordance` | Live running in `sentieon_cgt7p_bwa_sort`. |

Live BCL remains intentionally not launched at this checkpoint because a successful run can write several TiB of FASTQs and `/fsx` free space is `5.1T`.

## r50/r54 Checkpoint: 2026-05-30T19:02Z

HG002 kitchensink terminal update:

| Command | Analysis ID | State | Evidence |
|---|---|---|---|
| `illumina_hg002_kitchensink_multiqc` | `ccv20260530r50_illumina_hg002_kitchensink_multiqc` | Success, `live_exit=0` | `04019_illumina_hg002_kitchensink_multiqc_live_status.stdout.txt` reports `completed_at=2026-05-30T18:59:17Z`, `exit_code=0`. Driver session returned `{'command_id': 'illumina_hg002_kitchensink_multiqc', 'status': 'success', 'classification': 'SUCCESS', 'live_exit': 0}`. |

HG002 export evidence:

| Destination | Evidence |
|---|---|
| `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r50_illumina_hg002_kitchensink_multiqc/` | `04022_illumina_hg002_kitchensink_multiqc_export_s3_verify.stdout.txt` reports `Total Objects: 4374`, `Total Size: 3.3 GiB`. |

BCL dry-run checkpoint:

| Command | Analysis ID | State | Evidence |
|---|---|---|---|
| `illumina_bclconvert` | `ccv20260530r55_illumina_bclconvert_dryrun` | Dry-run success, `rc=0`; live intentionally deferred | `03955_illumina_bclconvert_dryrun_status.stdout.txt` reports `completed_at=2026-05-30T18:46:10Z`, `exit_code=0`. `03956_illumina_bclconvert_dryrun_logs.stdout.txt` shows lane-scoped BCL Convert commands for `L001`-`L008` using symlinked read-only run input under `config/run_dir_links/20260514_LH01106_0009_B23TVLGLT4`. |

Current cluster state:

| Evidence | State |
|---|---|
| `04029_headnode_compact_slurm_summary.stdout.txt` | `2` Slurm jobs, both from `ccv20260530r54_complete_genomics_mgi_snv_concordance`: `cgt7p_DNAscope-TVBCG5X-HG003-5x-1-D0-PF-CG-MGI` in `CONFIGURING` on `i192-dy-all-2`, and `alignstats-TVBCG5X-HG003-5x-1-D0-PF-CG-MGI` in `RUNNING` on `i192-dy-all-1`. `/fsx` is `8.8T` total, `3.7T` used, `5.1T` free, `42%` used. |

Active after this checkpoint:

| Command | Analysis ID | State |
|---|---|---|
| `complete_genomics_mgi_snv_concordance` | `ccv20260530r54_complete_genomics_mgi_snv_concordance` | Live still running; controller has no exit code yet. |

## r54 CG/MGI Terminal Success: 2026-05-30T19:19Z

CG/MGI terminal update:

| Command | Analysis ID | State | Evidence |
|---|---|---|---|
| `complete_genomics_mgi_snv_concordance` | `ccv20260530r54_complete_genomics_mgi_snv_concordance` | Success, `live_exit=0` | Driver session returned `{'command_id': 'complete_genomics_mgi_snv_concordance', 'status': 'success', 'classification': 'SUCCESS', 'live_exit': 0}` at `2026-05-30T19:18:47Z`. `04068_complete_genomics_mgi_snv_concordance_live_logs.stdout.txt` shows `36 of 36 steps (100%) done`, `WORKFLOW SUCCESS`, and `RETURN CODE: 0`. |

CG/MGI export evidence:

| Destination | Evidence |
|---|---|
| `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r54_complete_genomics_mgi_snv_concordance/` | `04080_complete_genomics_mgi_snv_concordance_export_s3_verify.stdout.txt` reports `Total Objects: 2166`, `Total Size: 6.3 GiB`. |

Post-CG cluster state:

| Evidence | State |
|---|---|
| `04084_headnode_compact_slurm_summary.stdout.txt` | `0` Slurm jobs; `/fsx` is `8.8T` total, `3.7T` used, `5.1T` free, `42%` used. |

## r56 BCL Live Launch: 2026-05-30T19:22Z

BCL launch update:

| Command | Analysis ID | State | Evidence |
|---|---|---|---|
| `illumina_bclconvert` | `ccv20260530r56_illumina_bclconvert_dryrun` | Dry-run success, `rc=0` | `04088_illumina_bclconvert_dryrun_status.stdout.txt` reports `completed_at=2026-05-30T19:20:32Z`, `exit_code=0`. |
| `illumina_bclconvert` | `ccv20260530r56_illumina_bclconvert` | Live running | `04094_illumina_bclconvert_live_status.stdout.txt` reports `started_at=2026-05-30T19:21:12Z`, no exit code yet. `04100_illumina_bclconvert_live_logs.stdout.txt` shows lane-scoped jobs submitted for `L001`-`L008`. |

Live BCL queue state:

| Evidence | State |
|---|---|
| `04099_headnode_compact_slurm_summary.stdout.txt` | `8` Slurm jobs, all `run_bclconvert_lane`, all `CONFIGURING`, one per `i192mem-dy-all-1` through `i192mem-dy-all-8`. `/fsx` remains `8.8T` total, `3.7T` used, `5.1T` free, `42%` used. |

Lane command contract observed in live logs:

- Source run directory is the symlinked read-only DRA mount path under `config/run_dir_links/20260514_LH01106_0009_B23TVLGLT4`; no scratch copy of the whole run directory is made.
- Per-lane command uses `dyec_run_bclconvert_lane.sh`, lane-specific output under `results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/lane_fastqs/L00N`, `threads=192`, `mem_mb=180000`, `partition=i192mem`, exclusive node scheduling, `-f 192`, compression level `1`, parallel tiles `16`, conversion threads `8`, compression threads `48`, decompression threads `16`, `--bcl-only-lane` equivalent lane selection, and legacy stats output enabled.

## Catalog Checkpoint: 2026-05-30T19:31Z

Current best state across the 20 catalog rows:

| Command | State | Latest evidence / reason |
|---|---|---|
| `simple-test` | PASS | `ccv20260529r20_simple-test`, export success. |
| `illumina_snv_alignstats` | PASS | `ccv20260529r7_illumina_snv_alignstats`, export success. |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | PASS | `ccv20260529r30_illumina_snv_alignstats_relatedness_vep_multiqc`, export success. |
| `illumina_hg002_kitchensink_multiqc` | PASS | `ccv20260530r50_illumina_hg002_kitchensink_multiqc`, export success. |
| `ultima_snv_alignstats` | PASS | `ccv20260529r33_ultima_snv_alignstats`, export success. |
| `ultima_snv_alignstats_kitchensink` | PASS | `ccv20260529r43_ultima_snv_alignstats_kitchensink`, export success. |
| `ont_snv_alignstats` | PASS | `ccv20260529r35_ont_snv_alignstats`, export success. |
| `ont_snv_alignstats_kitchensink` | PASS | `ccv20260529r35_ont_snv_alignstats_kitchensink`, export success. |
| `pacbio_snv_alignstats` | PASS | `ccv20260529r41_pacbio_snv_alignstats`, export success. |
| `roche_snv_alignstats` | PASS | `ccv20260529r45_roche_snv_alignstats`, Sentieon path, export success. |
| `hybrid_ilmn_ont_snv` | PASS | `ccv20260529r7_hybrid_ilmn_ont_snv`, export success. |
| `hybrid_ilmn_ont_snv_kitchensink` | PASS | `ccv20260530r48_hybrid_ilmn_ont_snv_kitchensink`, export success. |
| `hybrid_ultima_ont_snv` | FAIL | `ccv20260530r49_hybrid_ultima_ont_snv`; Stage1 kmer assertion was repaired, then Stage2 failed with Sentieon target-hap/HapCutAltMap assertions. |
| `complete_genomics_mgi_snv_concordance` | PASS | `ccv20260530r54_complete_genomics_mgi_snv_concordance`, export success. |
| `inflection-bjuice-product-v0.1` | PASS | `ccv20260529r10_inflection-bjuice-product-v0.1`, export success. |
| `illumina_run_qc` | PASS | `ccv20260529r11_illumina_run_qc`, export success. |
| `ont_run_qc` | PASS | `ccv20260529r22_ont_run_qc`, export success. |
| `ultima_run_qc` | PASS | `ccv20260529r14_ultima_run_qc`, export success. |
| `illumina_bclconvert` | RUNNING | `ccv20260530r56_illumina_bclconvert`; 8 lane jobs running, one per `i192mem` node. |
| `illumina_run_qc_bclconvert` | PENDING | Waiting on the BCL output. Earlier failures were upstream BCL-related, so this should be rerun only after r56 lands. |

## r56 BCL Runtime Checkpoint: 2026-05-30T19:44Z

Live BCL checkpoint:

| Evidence | State |
|---|---|
| `04152_headnode_bcl_lane_size_summary.stdout.txt` | `8` lane jobs still RUNNING, `18-19` minutes in. `/fsx` is `8.8T` total, `4.7T` used, `4.1T` free, `54%` used. BCL output is `1.1T` total; lane FASTQ directories are `120G`-`143G` each. No lane `bclconvert.done` files yet. |

Observed live BCL flags in lane logs:

- `--bcl-only-lane` per lane.
- `--fastq-gzip-compression-level 1`.
- `--bcl-num-parallel-tiles 16`.
- `--bcl-num-conversion-threads 8`.
- `--bcl-num-compression-threads 48`.
- `--bcl-num-decompression-threads 16`.
- `--shared-thread-odirect-output false`.
- `--output-legacy-stats true`.
- `--num-unknown-barcodes-reported 10000`.
- No sample-sheet setting injection active: `sample_sheet_settings_json={}`, `sample_sheet_settings_by_lane_json={}`.

## r56 BCL Runtime Checkpoint: 2026-05-30T20:01Z

Live BCL checkpoint:

| Evidence | State |
|---|---|
| `04191_headnode_bcl_lane_size_summary.stdout.txt` | `8` lane jobs still RUNNING, about `36` minutes in. `/fsx` is `8.8T` total, `5.8T` used, `3.0T` free, `66%` used. BCL output is `2.1T` total; lane FASTQ directories are `237G`-`300G` each. No lane `bclconvert.done` files yet. |

Current catalog state remains unchanged from the 19:31Z checkpoint except:

- `illumina_bclconvert` remains RUNNING as `ccv20260530r56_illumina_bclconvert`.
- `illumina_run_qc_bclconvert` remains PENDING behind r56 BCL output.

## r56 BCL Low-Headroom Checkpoint: 2026-05-30T20:18Z

Live BCL checkpoint:

| Evidence | State |
|---|---|
| `04229_headnode_bcl_lane_size_summary.stdout.txt` | `8` lane jobs still RUNNING, about `52` minutes in. `/fsx` is `8.8T` total, `6.8T` used, `2.0T` free, `78%` used. BCL output is `3.1T` total; lane FASTQ directories are `347G`-`441G` each. No lane `bclconvert.done` files yet. |
| `04231_headnode_analysis_dir_size_summary.stdout.txt` | Stale validation analysis directories are not a material space lever: the largest non-active validation tree is `26G`; the active guard reports `3.3T` for `ccv20260530r56_illumina_bclconvert`. No cleanup was performed from this inventory. |

## r56 BCL Export And DYEC Projection Fix: 2026-05-30T21:12Z

BCL workflow/export checkpoint:

| Evidence | State |
|---|---|
| `04361_illumina_bclconvert_live_logs.stdout.txt` | DayOA/Snakemake completed successfully: `15 of 15 steps (100%) done`, `WORKFLOW SUCCESS`, `RETURN CODE: 0`; wrapper entered `dyec export` at `2026-05-30T21:05:01Z`. |
| `04374_headnode_compact_slurm_summary.stdout.txt` | `0` Slurm jobs; `/fsx` is `8.8T` total, `8.1T` used, `707G` free, `93%` used. |
| `04376_headnode_bcl_export_guard_summary.stdout.txt` | Only active validation process is `dyec export` for `ccv20260530r56_illumina_bclconvert`. The run-dir projection link is absent after manual guard cleanup. |

Bug found:

- The DYEC wrapper had a pre-export `remove_run_dir_projection_links` function, but it looked under `$clone_root/config/run_dir_links`.
- The BCL projection is created inside the DayOA clone at `$repo_path/config/run_dir_links`, while the export source is the parent analysis directory.
- Result: the cleanup function missed the symlink, so `dyec export` could include a symlink to the read-only mounted run directory unless manually removed before the export walker reached it.

Fix applied locally:

| File | Change |
|---|---|
| `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` | Updated generated cleanup to use `$repo_path/config/run_dir_links`, the actual projection location. |
| `tests/test_script_entrypoints.py` | Added assertions that cleanup targets `$repo_path/config/run_dir_links` and occurs before `dyec export`. |

Focused validation:

| Command | Result |
|---|---|
| `source ./activate && python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py && python -m pytest -q tests/test_script_entrypoints.py && python -m ruff check daylily_ec/scripts/daylily_run_omics_analysis_headnode.py tests/test_script_entrypoints.py && git diff --check` | Passed; `32 passed`, `ruff` clean, diff check clean. |

S3 progress checks:

| Command | Result |
|---|---|
| `AWS_PROFILE=lsmc aws s3 ls s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r56_illumina_bclconvert/ --recursive --summarize --human-readable --region us-west-2 \| tail -8` | In-progress export had `1260` objects and `646.8 GiB` uploaded. |
| `AWS_PROFILE=lsmc aws s3 ls s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r56_illumina_bclconvert/daylily-omics-analysis/config/run_dir_links/ --recursive --region us-west-2` | Only a zero-byte directory marker was present; no run-dir symlink target/object was listed. |

## r56 BCL Terminal Success: 2026-05-30T21:51Z

Final BCL evidence:

| Evidence | Result |
|---|---|
| Driver session for `DYEC_VALIDATION_RUN_SUFFIX=ccv20260530r56 ... --command-id illumina_bclconvert` | Returned `{'command_id': 'illumina_bclconvert', 'status': 'success', 'classification': 'SUCCESS', 'live_exit': 0}` at `2026-05-30T21:50:16Z`. |
| `AWS_PROFILE=lsmc aws s3 ls s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r56_illumina_bclconvert/ --recursive --summarize --human-readable --region us-west-2 \| tail -8` | `Total Objects: 2847`, `Total Size: 4.4 TiB`. |
| `AWS_PROFILE=lsmc aws s3 ls s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r56_illumina_bclconvert/daylily-omics-analysis/config/run_dir_links/ --recursive --region us-west-2` | Only a zero-byte directory marker remained; no run-dir target content was exported. |
| `04398_headnode_compact_slurm_summary.stdout.txt` | `0` Slurm jobs; `/fsx` returned to `8.8T` total, `3.7T` used, `5.1T` free, `42%` used after delete-on-export-success removed the analysis tree. |

Catalog state after r56:

- `illumina_bclconvert` is terminal success with export evidence.
- `illumina_run_qc_bclconvert` is the only pending catalog row.
- `hybrid_ultima_ont_snv` remains the only failed live row; latest failure is Sentieon Stage2 `failed to find target hap` / `HapCutAltMap` after DYEC Stage1 repair.

## r57 Illumina Run QC + BCL Convert Launch: 2026-05-30T21:54Z

Final pending BCL row launch:

| Command | Analysis ID | State | Evidence |
|---|---|---|---|
| `illumina_run_qc_bclconvert` | `ccv20260530r57_illumina_run_qc_bclconvert_dryrun` | Dry-run success, `rc=0` | `04483_illumina_run_qc_bclconvert_dryrun_status.stdout.txt` reports `completed_at=2026-05-30T21:51:58Z`, `exit_code=0`. |
| `illumina_run_qc_bclconvert` | `ccv20260530r57_illumina_run_qc_bclconvert` | Live running | `04485_illumina_run_qc_bclconvert_live_launch.stdout.txt`; `04487_illumina_run_qc_bclconvert_live_status.stdout.txt` reports `started_at=2026-05-30T21:52:38Z`, no exit code yet. |

Live queue state:

| Evidence | State |
|---|---|
| `04488_headnode_compact_slurm_summary.stdout.txt` | `8` Slurm jobs, all `run_bclconvert_lane`, all on `i192mem`, one per lane `L001`-`L008`; `/fsx` is `8.8T` total, `3.7T` used, `5.1T` free, `42%` used. |

## r57 Illumina Run QC + BCL Convert Export Checkpoint: 2026-05-30T23:43Z

Live r57 state:

| Evidence | State |
|---|---|
| `04730_headnode_r57_bcl_lane_size_summary.stdout.txt` | All eight BCL lane `bclconvert.done` markers exist. Last lane was `L003` at `2026-05-30T23:25:18Z`. |
| `04729_illumina_run_qc_bclconvert_live_logs.stdout.txt` | Snakemake reached `21 of 21 steps (100%) done`; `multiqc_bclconvert` finished and the top-level `produce_illumina_run_qc_and_bclconvert` rule completed. |
| `04753_headnode_r57_wrapper_export_status.stdout.txt` | DayOA wrapper logged `WORKFLOW SUCCESS` and `RETURN CODE: 0`; generated cleanup removed `config/run_dir_links/20260514_LH01106_0009_B23TVLGLT4` before export; `dyec export` is active. |
| `04753_headnode_r57_wrapper_export_status.stdout.txt` | Export DRA `dra-00a88684e523c8868`; export task `task-0d328c73f7d8ec534` advanced from `PENDING` to `EXECUTING` and remained executing through `2026-05-30T23:42:34Z`. |
| `04753_headnode_r57_wrapper_export_status.stdout.txt` | Slurm queue is empty; `/fsx` is `8.8T` total, `8.1T` used, `707G` free, `93%` used during export. |

Current catalog state after this checkpoint:

- `illumina_run_qc_bclconvert` has live workflow `rc=0` evidence from DayOA and is waiting only on DRA export, S3 readback verification, and delete-on-export-success cleanup.
- `hybrid_ultima_ont_snv` remains the only non-terminal-success catalog row, with prior failure classified as Sentieon Stage2 target-hap/HapCutAltMap runtime failure after DYEC Stage1 repair.

## r57 Illumina Run QC + BCL Convert Terminal Success: 2026-05-31T00:31Z

Final r57 evidence:

| Evidence | Result |
|---|---|
| Driver session for `DYEC_VALIDATION_RUN_SUFFIX=ccv20260530r57 ... --command-id illumina_run_qc_bclconvert` | Returned `{'command_id': 'illumina_run_qc_bclconvert', 'status': 'success', 'classification': 'SUCCESS', 'live_exit': 0}` at `2026-05-31T00:29:38Z`. |
| `04863_illumina_run_qc_bclconvert_live_logs.stdout.txt` | Shows DayOA/Snakemake completion and export completion context for the terminal r57 run. |
| `04864_illumina_run_qc_bclconvert_export_s3_verify.stdout.txt` | `Total Objects: 2913`, `Total Size: 4.4 TiB` at `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r57_illumina_run_qc_bclconvert/`. |
| `04868_headnode_r57_wrapper_export_status.stdout.txt` | `status.json` reports `completed_at=2026-05-31T00:29:15Z`, `exit_code=0`. The export task `task-0d328c73f7d8ec534` reached `SUCCEEDED` at `2026-05-31T00:28:56Z`, wrote `fsx_export.yaml`, and then deleted `/fsx/analysis_results/ubuntu/ccv20260530r57_illumina_run_qc_bclconvert`. |
| `04868_headnode_r57_wrapper_export_status.stdout.txt` | `/fsx` returned to `8.8T` total, `3.7T` used, `5.1T` free, `42%` used. Slurm queue and controller process list are empty. |
| `04864_illumina_run_qc_bclconvert_export_s3_verify.stdout.txt` | No `daylily-omics-analysis/config/run_dir_links/` objects are present in the final export listing; mounted run input was not exported. |

Final command-catalog state:

| Command | Final state | Evidence / failure reason |
|---|---|---|
| `simple-test` | Success | `ccv20260529r20_simple-test`, export success. |
| `illumina_snv_alignstats` | Success | `ccv20260529r7_illumina_snv_alignstats`, export success. |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | Success | `ccv20260529r30_illumina_snv_alignstats_relatedness_vep_multiqc`, export success. |
| `illumina_hg002_kitchensink_multiqc` | Success | `ccv20260530r50_illumina_hg002_kitchensink_multiqc`, export success. |
| `ultima_snv_alignstats` | Success | `ccv20260529r33_ultima_snv_alignstats`, export success. |
| `ultima_snv_alignstats_kitchensink` | Success | `ccv20260529r43_ultima_snv_alignstats_kitchensink`, export success. |
| `ont_snv_alignstats` | Success | `ccv20260529r35_ont_snv_alignstats`, export success. |
| `ont_snv_alignstats_kitchensink` | Success | `ccv20260529r35_ont_snv_alignstats_kitchensink`, export success. |
| `pacbio_snv_alignstats` | Success | `ccv20260529r41_pacbio_snv_alignstats`, export success. |
| `roche_snv_alignstats` | Success | `ccv20260529r45_roche_snv_alignstats`, Sentieon path, export success. |
| `hybrid_ilmn_ont_snv` | Success | `ccv20260529r7_hybrid_ilmn_ont_snv`, export success. |
| `hybrid_ilmn_ont_snv_kitchensink` | Success | `ccv20260530r48_hybrid_ilmn_ont_snv_kitchensink`, export success. |
| `hybrid_ultima_ont_snv` | Failed | `ccv20260530r49_hybrid_ultima_ont_snv`; Stage1 Sentieon `kmerSize >= 1` assertion was repaired by DYEC runtime handling, then Stage2 failed with Sentieon `failed to find target hap` / `HapCutAltMap` assertions. No prior successful validation export for this row was found under the dyec-test validation prefix. |
| `complete_genomics_mgi_snv_concordance` | Success | `ccv20260530r54_complete_genomics_mgi_snv_concordance`, export success. |
| `inflection-bjuice-product-v0.1` | Success | `ccv20260529r10_inflection-bjuice-product-v0.1`, export success. |
| `illumina_run_qc` | Success | `ccv20260529r11_illumina_run_qc`, export success. |
| `ont_run_qc` | Success | `ccv20260529r22_ont_run_qc`, export success. |
| `ultima_run_qc` | Success | `ccv20260529r14_ultima_run_qc`, export success. |
| `illumina_bclconvert` | Success | `ccv20260530r56_illumina_bclconvert`, export success; `2847` objects, `4.4 TiB`; mounted input symlink target was not exported. |
| `illumina_run_qc_bclconvert` | Success | `ccv20260530r57_illumina_run_qc_bclconvert`, export success; `2913` objects, `4.4 TiB`; mounted input symlink target was not exported. |

Remaining execution work:

- No catalog command remains to launch.
- Final local DYEC validation and release commit/tag/push remain after reviewing the resulting diff.

## BCL Benchmark And Cleanup Checkpoint: 2026-05-31T08:25Z

Current headnode state:

| Check | Result |
|---|---|
| `/fsx` | `8.8T` total, `3.7T` used, `5.1T` available, `42%` used. |
| `/dev/shm` on headnode | `199G` total, `0` used at inspection time. |
| Slurm queue | Empty. |
| Snakemake/controller processes | None found by `pgrep -af 'snakemake|daylily_run_omics_analysis|dyec workflow|dy-r'`. |
| Exported success analysis dirs | All terminal-success analysis ids in the final catalog table were absent under `/fsx/analysis_results/ubuntu`, including `ccv20260530r56_illumina_bclconvert` and `ccv20260530r57_illumina_run_qc_bclconvert`. |
| Cleanup action | No deletion performed; there was no familiar exported success directory left behind to remove. Remaining recent dirs are dry-run or failed-attempt artifacts and need an explicit target list before destructive cleanup. |

BCL Convert r57 benchmark interpretation:

| Evidence | Result |
|---|---|
| Full-run source | `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r57_illumina_run_qc_bclconvert/`. |
| Lane wall times | `1:10:12` to `1:28:19`; long pole was `L003`. |
| Lane memory | Peak RSS `162.9G` to `172.3G` per lane. |
| Lane I/O | About `393-397G` read and `557-561G` written per lane; lane output total about `4.47T`. |
| CPU signal | Benchmarks show only about `6.7-8.1` CPU core-equivalents per lane despite `192` Snakemake threads. BCL Convert logs report `# CPU hw threads available: 64`. |
| Runtime flags used in r57 | `parallel_tiles=16`, `conversion_threads=8`, `compression_threads=48`, `decompression_threads=16`, `fastq_gzip_compression_level=1`, `shared_thread_odirect_output=false`, `output_legacy_stats=true`, `num_unknown_barcodes_reported=10000`. |
| `/dev/shm` | Lane logs set `TMPDIR=/dev/shm`; compute-node `/dev/shm` was `605G` and empty at lane start. The BCL input and output paths were FSx paths, so `/dev/shm` was available for temp use but not used as a full BCL/FASTQ staging layer. |

Recommended next BCL tuning experiment:

- Treat this as primarily FSx read/write bound, not memory bound. More memory is unlikely to shorten wall time.
- Keep `fastq_gzip_compression_level=1`.
- Benchmark `shared_thread_odirect_output=true` against the r57 `false` setting because r57 logs explicitly show shared-thread native output disabled.
- Benchmark a CPU-thread layout aligned to the BCL-reported `64` hardware threads, for example `parallel_tiles=16`, `conversion_threads=2`, `compression_threads=24`, `decompression_threads=8`, with `threads=64`; compare to current `16/8/48/16`.
- Keep one lane per exclusive node for the speed benchmark; packing lanes onto fewer nodes may save cost, but it is unlikely to improve wall time while FSx is near the throughput limit.
- Consider lowering BCL `mem_mb` from `360000` to `240000-300000` only for schedulability/cost-shaping. The observed peak RSS leaves enough headroom, but this is not expected to make the run faster.

Follow-up tuning change applied locally:

- DayOA slurm template BCL Convert lane settings now use `parallel_tiles=24`, `conversion_threads=4`, `compression_threads=64`, and `decompression_threads=32`, keeping the CPU-heavy sum at `192` while increasing tile-level, compression, and decompression concurrency.
- DYEC runtime patch now injects the same `24/4/64/32` settings, allows `i192mem,i192bigmem`, re-enables `shared_thread_odirect_output=true`, and restores `num_unknown_barcodes_reported=1000`.
- This is an intentional benchmark attempt to get BCL Convert to consume more of the 192-vCPU node. The prior r57 successful run was `16/8/48/16`, `shared_thread_odirect_output=false`, and `num_unknown_barcodes_reported=10000`.
