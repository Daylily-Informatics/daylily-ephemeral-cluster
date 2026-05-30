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
