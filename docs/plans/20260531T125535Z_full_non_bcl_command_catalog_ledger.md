# Full Non-BCL Command Catalog Validation Ledger

Date: 2026-05-31T12:55:35Z

## Objective

Run every DayOA command-catalog command on `dyec-515` except BCL Convert commands, fix command/source/runtime defects as they are exposed, and move durable fixes into source code so the next pushed versions contain them rather than relying on one-off headnode edits.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| DAY-EC repo | `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`, branch `codex/dyec515-full-catalog-20260531`; dirty from catalog rename, detached-head configure fix, `day-clone` cluster-identity behavior, DayOA `2.0.27` catalog pin, and current catalog-run ledger artifacts |
| DayOA repo | `/Users/jmajor/projects/daylily/daylily-omics-analysis`, branch `codex/dayoa-local-evidence-dewey-refactor-20260528`; pushed commit `ab160ed` and annotated tag `2.0.27` contain the benchmark wildcard parse fix |
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

## Source Pairing Matrix

| Command | Input Type | Paired Source | Pairing Basis |
|---|---|---|---|
| `simple-test` | none | none | Utility command, `input_contract=none` |
| `illumina_snv_alignstats` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/illumina_hg003_5x.tsv` | detected mode `ilmn_solo` |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | sample manifest | `docs/plans/20260526T224018Z_blahab44_inputs/illumina_hg003_5x.tsv` | detected mode `ilmn_solo` |
| `illumina_hg002_kitchensink_multiqc` | sample manifest | `docs/plans/20260526T213400Z_jem_bucktst3_ilmn_0p1x_kitchensink/analysis_samples.tsv` | command name and prior validation use HG002 kitchensink-specific ILMN manifest |
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
| DATA-001 | Source pairing | Validate each non-BCL command uses a source manifest/run context compatible with its catalog data mode. | SUCCESS | contract_test | Gate 1 | orchestrator | Source pairing matrix above plus structured header validation under `Source Pairing Validation Evidence`. |  | All non-BCL rows have source data paired to the catalog contract. |
| SKIP-001 | BCL Convert | Skip `illumina_bclconvert` and `illumina_run_qc_bclconvert`. | SUCCESS | not_applicable_after_inspection | Gate 1 | orchestrator | User explicitly requested skipping BCL Convert commands. |  | BCL rows excluded from launches. |
| RUN-001 | Live dyec-515 | Run `simple-test`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-002 | Live dyec-515 | Run `illumina_snv_alignstats`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-003 | Live dyec-515 | Run `illumina_snv_alignstats_relatedness_vep_multiqc`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-004 | Live dyec-515 | Run `illumina_hg002_kitchensink_multiqc`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-005 | Live dyec-515 | Run `ultima_snv_alignstats`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Attempts `dyec515_20260531t1237_ultima_snv_alignstats` and `dyec515_20260531t1244_retry1_ultima_snv_alignstats`; retry reached DayOA parse error. | DayOA `collect_rules_benchmark_data` benchmark-only wildcard caused Snakemake parse failure. |  |
| RUN-006 | Live dyec-515 | Run `ultima_snv_alignstats_kitchensink`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-007 | Live dyec-515 | Run `ont_snv_alignstats`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Attempts `dyec515_20260531t1237_ont_snv_alignstats` and `dyec515_20260531t1244_retry1_ont_snv_alignstats`; retry reached DayOA parse error. | DayOA `collect_rules_benchmark_data` benchmark-only wildcard caused Snakemake parse failure. |  |
| RUN-008 | Live dyec-515 | Run `ont_snv_alignstats_kitchensink`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-009 | Live dyec-515 | Run `pacbio_snv_alignstats`. | ATTEMPTING_BUGFIX | contract_test | Gate 3 | orchestrator | Attempts `dyec515_20260531t1237_pacbio_snv_alignstats` and `dyec515_20260531t1244_retry1_pacbio_snv_alignstats`; retry reached DayOA parse error. | DayOA `collect_rules_benchmark_data` benchmark-only wildcard caused Snakemake parse failure. |  |
| RUN-010 | Live dyec-515 | Run `roche_snv_alignstats`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-011 | Live dyec-515 | Run `hybrid_ilmn_ont_snv`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-012 | Live dyec-515 | Run `hybrid_ilmn_ont_snv_kitchensink`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-013 | Live dyec-515 | Run `inflection-bjuice-product-v0.1`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-014 | Live dyec-515 | Run `hybrid_ultima_ont_snv`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-015 | Live dyec-515 | Run `complete_genomics_mgi_snv_concordance`. | OPEN | contract_test | Gate 3 | orchestrator | Prior ledger flagged mate-pair contract risk; must verify rather than substitute. |  |  |
| RUN-016 | Live dyec-515 | Run `illumina_run_qc`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-017 | Live dyec-515 | Run `ont_run_qc`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| RUN-018 | Live dyec-515 | Run `ultima_run_qc`. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| MON-001 | Monitoring | Keep launch batches bounded, record terminal status/log evidence, and do not leave local launch processes running. | OPEN | legitimate_safety_handling | Gate 4 | orchestrator |  |  |  |

## Final Status

In progress.
