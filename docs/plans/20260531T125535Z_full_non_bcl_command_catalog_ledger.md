# Full Non-BCL Command Catalog Validation Ledger

Date: 2026-05-31T12:55:35Z

## Objective

Run every DayOA command-catalog command on `dyec-515` except BCL Convert commands, fix command/source/runtime defects as they are exposed, and move durable fixes into source code so the next pushed versions contain them rather than relying on one-off headnode edits.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| DAY-EC repo | `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`, branch `codex/dyec515-full-catalog-20260531`; current work pins the command catalog and package dependency to DayOA `2.0.29`, updates DYEC self-pins to `5.1.11`, and records dyec-515 catalog-run evidence |
| DayOA repo | `/Users/jmajor/projects/daylily/daylily-omics-analysis`, branch `codex/dayoa-local-evidence-dewey-refactor-20260528`; pushed commit `22f8137` and annotated tag `2.0.29` contain the raw FASTQ QC wildcard fix after earlier `2.0.27`/`2.0.28` parse fixes |
| Cluster target | `dyec-515`, profile `lsmc`, region `us-west-2`, headnode `i-002fac7d5932b5689` |
| Prior live evidence | Initial `ultima_snv_alignstats`, `ont_snv_alignstats`, and `pacbio_snv_alignstats` launches reached remote tmux sessions; first attempts failed on missing Puppeteer Chrome; after repairing the headnode Chrome cache, retries failed at DayOA parse time in `workflow/rules/multiqc_final_wgs.smk` rule `collect_rules_benchmark_data` |
| Headnode repair already performed | Installed/verifed `chrome-headless-shell@148.0.7778.97` as `ubuntu`; `mmdc` PDF smoke test passed on `dyec-515` |
| Source-pairing baseline | Use catalog-compatible inputs in `docs/plans/20260526T224018Z_blahab44_inputs/`; detected modes: ILMN=`illumina_hg003_5x.tsv`, ONT=`ont_hg003_5x.tsv`, Ultima=`ultima_hg003_5x.tsv`, PacBio=`pacbio_hg003_5x.tsv`, Roche=`roche_hg003_5x.tsv`, hybrid ILMN+ONT=`hybrid_ilmn_ont_hg003_5x5x.tsv`, hybrid Ultima+ONT=`hybrid_ultima_ont_hg003_5x5x.tsv`, CG/MGI=`complete_genomics_mgi_hg003_candidate_blocked.tsv`; run contexts: `illumina_run_context.tsv`, `ont_run_context.tsv`, `ultima_run_context_candidate.tsv` |
| Explicit skip | `illumina_bclconvert` and `illumina_run_qc_bclconvert` are skipped by user request |
| Safety boundary | Do not delete/teardown/cancel AWS resources or Slurm jobs without separate explicit approval; transient staging DRAs may be created by launches but will not be deleted without approval |

## Source Pairing Validation Evidence

Structured TSV header checks passed for every non-BCL sample-analysis source pairing. Each paired manifest contains one row and satisfies the command's catalog input contract:

- ILMN commands matched `ILMN_R1_FQ,ILMN_R2_FQ`.
- Ultima commands matched `UG_R1_FQ,UG_R2_FQ`.
- ONT commands matched `ONT_R1_FQ,ONT_R2_FQ`.
- PacBio command matched `PACBIO_R1_FQ,PACBIO_R2_FQ`.
- Roche command matched `ROCHE_BAM,ROCHE_BAM_ALIGNER,ROCHE_BAM_SNV_CALLER`.
- Hybrid ILMN+ONT commands matched `ILMN_R1_FQ,ILMN_R2_FQ,ONT_CRAM,ONT_CRAM_ALIGNER,ONT_CRAM_SNV_CALLER`.
- Hybrid Ultima+ONT command matched `ULTIMA_CRAM,ULTIMA_CRAM_ALIGNER,ULTIMA_CRAM_SNV_CALLER,ONT_CRAM,ONT_CRAM_ALIGNER,ONT_CRAM_SNV_CALLER`.
- Complete Genomics/MGI command matched `CG_R1_FQ,CG_R2_FQ`; live success remains contingent on the mate-pair contract being valid at runtime.
- Run-context commands have platform-matched rows: ILMN `20260514_LH01106_0009_B23TVLGLT4`, ONT `20260513_ONT_HG003`, Ultima `602221-20260417_2346`.

## Source Data Relocation Evidence

All command-catalog read sources now resolve under `/fsx/references/genomic_data/organism_reads_slim/` for this validation set.

- HG002 ILMN 0.1x R1/R2 were copied from control data to `s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/`; headnode `/fsx/references` sizes are `81,330,606` and `83,356,045` bytes.
- HG003 CG/MGI T7plus R1/R2 were pair-preserving downsampled to 10% with `seqtk sample -s42`, gzip-validated, staged, and copied to `s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/fastq/H_sapiens/complete_genomics/T7plus_WGS_PE150_HG003_PCR_Free/downsampled/`; headnode `/fsx/references` sizes are `10,251,454,933` and `10,405,048,250` bytes.
- `docs/plans/20260526T223700Z_goodole3_inputs/illumina_0p1x_kitchensink.tsv` now uses the HG002 reads_slim FASTQs.
- `docs/plans/20260526T224018Z_blahab44_inputs/complete_genomics_mgi_hg003_candidate_blocked.tsv` now uses the CG/MGI 10% reads_slim FASTQs and `SUBSAMPLE_PCT=0.5` to preserve the prior 5x intent against the 10% source.
- Config-only checks in `docs/plans/20260531T153241Z_reads_slim_config_check/` passed and produced units files with no `/fsx/control_data` read source paths.

## Source Pairing Matrix

| Command | Input Type | Paired Source | Pairing Basis |
|---|---|---|---|
| `simple-test` | none | none | Utility command, `input_contract=none` |
| `illumina_snv_alignstats` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/illumina_hg003_5x.tsv` | detected mode `ilmn_solo` |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/illumina_hg003_5x.tsv` | detected mode `ilmn_solo` |
| `illumina_hg002_kitchensink_multiqc` | sample manifest | `docs/plans/20260526T223700Z_goodole3_inputs/illumina_0p1x_kitchensink.tsv` | HG002 kitchensink-specific ILMN manifest with `STAGE_DIRECTIVE=pass_through`; the earlier `docs/plans/20260526T213400Z_jem_bucktst3_ilmn_0p1x_kitchensink/analysis_samples.tsv` row uses `stage_data` and is not valid for config-only launch |
| `ultima_snv_alignstats` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/ultima_hg003_5x.tsv` | detected mode `ultima_solo` |
| `ultima_snv_alignstats_kitchensink` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/ultima_hg003_5x.tsv` | detected mode `ultima_solo` |
| `ont_snv_alignstats` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/ont_hg003_5x.tsv` | detected mode `ont_solo` |
| `ont_snv_alignstats_kitchensink` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/ont_hg003_5x.tsv` | detected mode `ont_solo` |
| `pacbio_snv_alignstats` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/pacbio_hg003_5x.tsv` | detected mode `pacbio_solo` |
| `roche_snv_alignstats` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/roche_hg003_5x.tsv` | detected mode `roche_solo` |
| `hybrid_ilmn_ont_snv` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/hybrid_ilmn_ont_hg003_5x5x.tsv` | detected mode `hybrid_ilmn_ont` |
| `hybrid_ilmn_ont_snv_kitchensink` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/hybrid_ilmn_ont_hg003_5x5x.tsv` | detected mode `hybrid_ilmn_ont` |
| `inflection-bjuice-product-v0.1` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/hybrid_ilmn_ont_hg003_5x5x.tsv` | detected mode `hybrid_ilmn_ont`; command targets full hybrid product scope |
| `hybrid_ultima_ont_snv` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/hybrid_ultima_ont_hg003_5x5x.tsv` | detected mode `hybrid_ug_ont` |
| `complete_genomics_mgi_snv_concordance` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/complete_genomics_mgi_hg003_candidate_blocked.tsv` | detected mode `complete_genomics_solo`; live mate-pair contract must be verified before live success can be claimed |
| `illumina_run_qc` | run context | `docs/plans/20260526T224018Z_blahab44_inputs/illumina_run_context.tsv` | ILMN run-directory row; not BCL Convert |
| `ont_run_qc` | run context | `docs/plans/20260526T224018Z_blahab44_inputs/ont_run_context.tsv` | ONT run-directory row |
| `ultima_run_qc` | run context | `docs/plans/20260526T224018Z_blahab44_inputs/ultima_run_context_candidate.tsv` | Ultima run-directory candidate |

## Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record repos, cluster, prior failed attempts, skip boundary, and source-pairing matrix. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | This ledger Gate 0. |  | Baseline captured. |
| CODE-001 | DayOA | Fix DayOA parse blocker in benchmark collection rules without a DYEC runtime shim. | SUCCESS | feature_implementation | Gate 1 | orchestrator | DayOA patch changes benchmark paths in `workflow/rules/multiqc_final_wgs.smk` and `workflow/rules/multiqc_singleton.smk`; validation passed: focused pytest `2 passed`, broader `tests/test_multiqc_qc_targets.py tests/test_evidence_manifest.py -> 31 passed`, `git diff --check`; pushed branch and annotated tag `2.0.27`. | DayOA `collect_rules_benchmark_data` benchmark paths included benchmark-only `{MDIR}` wildcards. | Fixed in DayOA `2.0.27`. |
| CODE-002 | DAY-EC | Add/verify `day-clone -u` executing-entity behavior and make workflow launch prefer the cluster name when no explicit executing entity is supplied. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `day-clone` now resolves explicit `-u`, exported cluster identity, then `/etc/parallelcluster/cfnconfig` `stack_name`; no hostname/`USER` fallback. Headnode inspection showed `stack_name=dyec-515`. Focused DAY-EC tests passed: `tests/test_day_clone.py`, `test_workflow_launch_defaults_executing_entity_to_cluster`, `test_samples_run_defaults_executing_entity_to_cluster`, and script-entrypoint launch test -> `15 passed`. | Previous default used user identity rather than the cluster identity. | Durable in source and payload copy. |
| CODE-003 | Versioning | Move durable fixes into pushed/tagged DayOA and DAY-EC versions before catalog success is treated as durable. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | DayOA branch/tag pushed: `ab160ed`, annotated tag `2.0.27`; package index now reports `daylily-omics-analysis (2.0.27)`. DAY-EC `pyproject.toml`, catalog, payload catalog, and current docs pin DayOA `2.0.27`; environment YAML files now remain operator-tooling only. Validation after the package/env correction: `python -m pip install -e .` succeeded, focused pytest including `tests/test_environment_contract.py` -> `56 passed`, `py_compile`, Ruff, and `git diff --check` all passed. | DayOA `2.0.27` was initially not available on the package index, so the first DAY-EC `5.1.6` tag was not sufficient for durable package installs at that moment. | DAY-EC release is corrected in the follow-up `5.1.7` tag rather than moving `5.1.6`. |
| CODE-004 | DayOA | Fix raw FASTQ QC parse blocker exposed by all catalog dry-runs. | SUCCESS | feature_implementation | Gate 3 | orchestrator | DayOA commit `22f8137`, annotated tag `2.0.29`, and PyPI `daylily-omics-analysis (2.0.29)` are published. Validation: `tests/test_rule_log_benchmark_contracts.py tests/test_multiqc_qc_targets.py tests/test_evidence_manifest.py -> 34 passed`; `twine check` passed with existing metadata warnings. | Rule `seqqc` in `workflow/rules/multiqc_for_raw_fastqs.smk` had output/log/benchmark wildcard mismatch. | Fixed in DayOA `2.0.29`; DAY-EC catalog now pins `2.0.29`. |
| CODE-005 | DAY-EC | Publish a DAY-EC release whose packaged global config points at the exact release tag used for headnode rebuilds. | IN_PROGRESS | config_or_startup_contract | Gate 3 | orchestrator | Source and packaged `daylily_cli_global.yaml` now set `git_ephemeral_cluster_repo_tag` and `git_ephemeral_cluster_repo_release_tag` to `5.1.11`; active docs now mention DayOA `2.0.29`. | Earlier `5.1.10` tag carried the DayOA `2.0.29` catalog pin but still advertised stale DYEC self-pins from `5.1.5`. | Commit, tag, publish, and rebuild headnode from `5.1.11`; do not move `5.1.10`. |
| DATA-001 | Source pairing | Validate each non-BCL command uses a source manifest/run context compatible with its catalog data mode. | SUCCESS | contract_test | Gate 1 | orchestrator | Source pairing matrix above plus structured header validation under `Source Pairing Validation Evidence`. |  | All non-BCL rows have source data paired to the catalog contract. |
| SKIP-001 | BCL Convert | Skip `illumina_bclconvert` and `illumina_run_qc_bclconvert`. | SUCCESS | not_applicable_after_inspection | Gate 1 | orchestrator | User explicitly requested skipping BCL Convert commands. |  | BCL rows excluded from launches. |
| RUN-001 | Live dyec-515 | Run `simple-test`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2_001_simple` launched with `-u` unset and wrote under `/fsx/analysis_results/dyec-515/...`; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch parsed before target selection. | Retest after DayOA `2.0.29` rebuild. |
| RUN-002 | Live dyec-515 | Run `illumina_snv_alignstats`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2d_002_ilmn_snv`; direct `workflow launch --samples-file --units-file` avoided staged-prefix DRA creation; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-003 | Live dyec-515 | Run `illumina_snv_alignstats_relatedness_vep_multiqc`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2d_003_ilmn_mqc`; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-004 | Live dyec-515 | Run `illumina_hg002_kitchensink_multiqc`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2d_004_hg002_kit`; generated units use HG002 reads_slim paths; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-005 | Live dyec-515 | Run `ultima_snv_alignstats`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Earlier attempts reached the `collect_rules_benchmark_data` parse error; retest `d515_0531t1541_r2d_005_ug_snv` reached the newer raw FASTQ QC `seqqc` parse error and exited `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-006 | Live dyec-515 | Run `ultima_snv_alignstats_kitchensink`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2d_006_ug_mqc`; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-007 | Live dyec-515 | Run `ont_snv_alignstats`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Earlier attempts reached the `collect_rules_benchmark_data` parse error; retest `d515_0531t1541_r2d_007_ont_snv` reached the newer raw FASTQ QC `seqqc` parse error and exited `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-008 | Live dyec-515 | Run `ont_snv_alignstats_kitchensink`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2d_008_ont_mqc`; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-009 | Live dyec-515 | Run `pacbio_snv_alignstats`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Earlier attempts reached the `collect_rules_benchmark_data` parse error; retest `d515_0531t1541_r2d_009_pb_snv` reached the newer raw FASTQ QC `seqqc` parse error and exited `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-010 | Live dyec-515 | Run `roche_snv_alignstats`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2d_010_roche`; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-011 | Live dyec-515 | Run `hybrid_ilmn_ont_snv`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2d_011_hio_snv`; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-012 | Live dyec-515 | Run `hybrid_ilmn_ont_snv_kitchensink`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2d_012_hio_mqc`; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-013 | Live dyec-515 | Run `inflection-bjuice-product-v0.1`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2d_013_bjuice`; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-014 | Live dyec-515 | Run `hybrid_ultima_ont_snv`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2d_014_huo_snv`; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-015 | Live dyec-515 | Run `complete_genomics_mgi_snv_concordance`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Retest `d515_0531t1541_r2d_015_cg_mgi`; generated units use CG/MGI reads_slim 10% paths with `SUBSAMPLE_PCT=0.5`; status exit `1`. | DayOA raw FASTQ QC `seqqc` wildcard mismatch. | Retest after DayOA `2.0.29` rebuild. |
| RUN-016 | Live dyec-515 | Run `illumina_run_qc`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4` is now visible. Retest `d515_0531t1541_r2_016_ilmn_runqc` status exit `1`; log also showed stale DayOA `.test_data/data/units.tsv` entries still reference `/fsx/control_data` before the shared parse blocker. | DayOA raw FASTQ QC `seqqc` wildcard mismatch plus run-QC test-data path debt. | Retest after DayOA `2.0.29`; if parse clears, fix run-QC test-data paths as next exposed defect. |
| RUN-017 | Live dyec-515 | Run `ont_run_qc`. | BLOCKED | dependency_unavailable | Gate 3 | orchestrator | Source/run-context preflight found `/fsx/run_dir_mounts/20260513_ONT_HG003/` missing. Serialized mount setup stopped after the ILMN DRA timeout, so the ONT run-QC mount was not created. | Prior run-directory DRA creation blocked serialized run-mount setup. | Blocked pending run-mount availability. |
| RUN-018 | Live dyec-515 | Run `ultima_run_qc`. | BLOCKED | dependency_unavailable | Gate 3 | orchestrator | Source/run-context preflight found `/fsx/run_dir_mounts/602221-20260417_2346/` missing. Serialized mount setup stopped after the ILMN DRA timeout, so the Ultima run-QC mount was not created. | Prior run-directory DRA creation blocked serialized run-mount setup. | Blocked pending run-mount availability. |
| MON-001 | Monitoring | Keep launch batches bounded, record terminal status/log evidence, and do not leave local launch processes running. | OPEN | legitimate_safety_handling | Gate 4 | orchestrator |  |  |  |

## Headnode Rebuild Evidence

After pushing DAY-EC `5.1.7`, `dyec headnode configure --profile lsmc --region us-west-2 --cluster dyec-515` returned success. A follow-up supported headnode reinstall ran `bash bin/init_dayec` from `/home/ubuntu/projects/daylily-ephemeral-cluster` as `ubuntu`.

Verification on `dyec-515`:

- Remote DAY-EC repo head: `9c989a5b04fc1bfcc8e2764057f20aa987a6a0c3`.
- Remote DAY-EC exact tag: `5.1.7`.
- Remote `dyec --json version`: `5.1.7`.
- Remote `daylily-ephemeral-cluster` package: `5.1.7`, editable from `/home/ubuntu/projects/daylily-ephemeral-cluster`.
- Remote `daylily-omics-analysis` package: `2.0.27`.
- Remote catalog: `catalog_has_2_0_27=True`, `catalog_has_2_0_26=False`.
- Old catalog name remains a symlink: `daylily_available_repositories.yaml -> daylily_pipeline_command_catalog.yaml`.

## Final Status

In progress.
