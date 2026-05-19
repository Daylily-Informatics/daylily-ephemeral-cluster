# Ultima 602201/602202 Kitchen Sink 1.0.5 Ledger

Date opened: 2026-05-17

## Control

Controlling request: stage and run the kitchen-sink workflow on Ultima `602202-20260512_1805` and `602201-20260512_1507`, using `day-clone -t 1.0.5`.

Ledger path: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster/docs/plans/ultima_602201_602202_ksink105_ledger.md`

Execution scope:
- AWS profile: `lsmc`
- AWS region: `us-west-2`
- Cluster: `may26-d`
- Reference bucket: `s3://lsmc-dayoa-omics-analysis-us-west-2`
- Source bucket checked: `s3://lsmc-ssf-sequencing-data`
- DayEC repo: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster`
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- Required DayOA ref: `1.0.5`
- 602202 stage dir: `/fsx/data/staged_sample_data/remote_stage_20260517T132408Z`
- 602202 destination: `ultima_602202_20260512_1805_ksink105_20260517T190121Z`

Hard boundaries:
- Use `day-clone -t 1.0.5` for new DayOA worksets.
- Do not include SnpEff; the operator marked SnpEff deprecated.
- Do not invent source paths or manifests. Missing 602201 source evidence blocks that run until a real source prefix or manifest is provided.
- Headnode commands must run as `ubuntu` through DayEC SSM helpers.

## Gate 0 Baseline

- DayEC status: branch `codex/run-directory-mounts...origin/codex/run-directory-mounts`; existing unrelated untracked/dirty work is present from prior ledgers/reports.
- DayOA tag check: `git fetch --tags origin`; `1.0.5^{}` -> `6ff8193350dc059bcb2ba452cf4b057efb62318d` (`Skip sequence QC for missing FASTQs`).
- DayOA local source note: `workflow/scripts/relatedness_report.py` and `tests/test_giab_qc_contracts.py` contain a local reportfix for the prior Ultima 1.0.4 run; tag `1.0.5` itself still imports pandas/Jinja2 in `relatedness_report.py`.
- Cluster check: `daylily-ec --json cluster-info --profile lsmc --region us-west-2` listed `may26-d` as `CREATE_COMPLETE`.
- Headnode preflight command `0f3583d9-cb21-4427-9241-c1acfe745f57` on `i-0e7639ff46f207ae7`: user `ubuntu`, destination `/fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_ksink105_20260517T190121Z` absent, stage manifests present with 13 lines each, `/fsx` has 8.7T available, `day-clone` is on PATH, `squeue -u ubuntu` had no jobs.
- 602202 manifest: `reports/stage_three_latest_20260516T130229Z/manifests/602202-20260512_1805/analysis_samples.tsv` has 12 rows and passed `daylily-ec samples stage ... --precheck-only` with 24 source objects checked.
- 602202 existing stage: `s3://lsmc-dayoa-omics-analysis-us-west-2/data/staged_sample_data/remote_stage_20260517T132408Z/` contains 26 objects, 1.3 TiB, including generated `20260517T132408Z_samples.tsv` and `20260517T132408Z_units.tsv`.
- 602201 source lookup: no local manifest under the current report tree; no matches in `processing_prod_data`; no source objects found under `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN602201/2026/602201-20260512_1507/`, `raw/lsmc/ssf-hq/RUN602201/2026/602201-20260512_1507/`, or bucket-wide object-key searches for `602201` / `20260512_1507` in the checked prefixes.

## Control Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE-000 | DayEC/DayOA/AWS | Record repo, tag, cluster, stage, and source-input baseline before launching. | SUCCESS | plan_amendment | Gate 0 | orchestrator | Gate 0 Baseline section above. |  | Baseline recorded before launch. |
| SRC-602202 | DayEC/AWS | Verify 602202 manifest and staged data for kitchen-sink launch. | SUCCESS | contract_test | Gate 1 | orchestrator | Precheck passed for 12 rows/24 source objects; existing stage has 26 objects/1.3 TiB and FSx manifests with 12 samples/12 units. |  | Reusing complete existing stage to avoid duplicating a 1.3 TiB S3 copy. |
| SRC-602201 | DayEC/AWS | Locate or build a real 602201 manifest/source stage. | BLOCKED | feature_implementation | Gate 1 | orchestrator | Source lookups for `602201`, `20260512_1507`, and `RUN602201` returned no S3 objects in the checked source/reference buckets; no local manifest exists. | No proven source prefix or manifest for `602201-20260512_1507`. | Needs a real source location or completed transfer before staging/launch. |
| RUN-602202 | DayOA/AWS | Launch 602202 kitchen-sink workflow from a `day-clone -t 1.0.5` checkout. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Status JSON `phase=live_success`, `exit_code=0`, `completed_at=2026-05-17T21:54:47Z`; live log completed 930/930 steps; final MultiQC present at `/fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_ksink105_20260517T190121Z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html` (11,929,236 bytes). | Tag `1.0.5` needed run-local fixes for `relatedness_report.py` report dependencies and `common.smk` FASTQ_QC_SAMPS evaluation order. | Completed successfully. |
| RUN-602201 | DayOA/AWS | Launch 602201 kitchen-sink workflow from a `day-clone -t 1.0.5` checkout. | BLOCKED | feature_implementation | Gate 2 | orchestrator | Blocked by `SRC-602201`. | No proven source stage or manifest. | Launch cannot proceed until source is resolved. |
| MONITOR-001 | DayOA/AWS | Monitor launched workflows to terminal status and record final report paths. | SUCCESS | contract_test | Gate 3 | orchestrator | Heartbeat `2026-05-17T22:14:44Z` command `99f9b1fd-a44a-4ab7-a40a-4059ccb61d77`: no tmux session, no Slurm jobs attributed to workdir, final MultiQC present, all checked aggregate reports present. |  | Monitoring objective complete; heartbeat automation removed. |

## Execution Notes

- 602202 launch uses the 1.0.5 checkout plus run-local patches for the local stdlib `relatedness_report.py` reportfix and the `common.smk` FASTQ_QC_SAMPS ordering fix. The `common.smk` patch was applied through a small remote patcher because uploading the full file exceeded the SSM Run Command 97 KB document limit.
- Launch helper command IDs: relatedness upload `530970d3-050f-4e09-bd57-f17dde007388`, common patcher upload `ec0df5e4-28ac-48ea-95cd-18cf10476c0a`, runner upload `4ad00118-d2cd-4dee-95e4-a1527b7f6fcd`, tmux launch `4f9b6716-6a87-4336-9245-df926e0e80ff`.
- Dry-run completed with return code 0 and planned 930 jobs, including `sent_snv_ug`, `alignstats`, `peddy`, `relatedness_batch_somalier_extract`, `relatedness_batch_somalier_relate`, `produce_snv_concordances`, `vep_chromosome`, contamination reports, and final `multiqc_final_wgs`; SnpEff was disabled via `multiqc_qc.disable_tools`.
- Heartbeat `2026-05-17T19:44:30Z` command `48cc8b8e-c87c-4f12-9a40-e32c771c7433`: status JSON still `phase=live_run` with `exit_code=null`; tmux present; Slurm summary `63 RUNNING`; observed active jobs included `sent_snv_ug`, `alignstats`, `verifybamid2_contam`, `gen_samstats`, `relatedness_batch_somalier_extract`, `legacy_cram_compat_bam`, and `calc_coverage_evenness`; final MultiQC HTML was not present yet.
- Heartbeat `2026-05-17T20:14:30Z` command `2c560129-93f8-49ab-a374-273b609a2440`: status JSON still `phase=live_run` with `exit_code=null`; tmux present; Slurm summary `100 RUNNING`; live log reached 515/930 steps (55%); active jobs were dominated by `vep_chromosome` / `vep_chromosome_input`, with `gatk_contam`, `sentdug_concat_index_chunks`, `bcftools_vcfstat`, `legacy_cram_compat_bam`, `verifybamid2_contam`, and `gen_samstats` also present; final MultiQC HTML was not present yet.
- Heartbeat `2026-05-17T20:44:36Z` command `5667f3b6-137e-45a8-a531-024b4c07550c`: status JSON still `phase=live_run` with `exit_code=null`; tmux present; Slurm summary `5 RUNNING`; live log reached 842/930 steps (91%). A `sentdug_concat_index_chunks` job failed once at 20:38:45 UTC, Snakemake restarted it, and the retry finished by 20:40:51 UTC. Active jobs were two `vep_chromosome` jobs plus `calc_coverage_evenness`, `verifybamid2_contam`, and `gen_samstats`; final MultiQC HTML was not present yet. `relatedness_mqc.tsv` existed; peddy, VEP aggregate, contamination aggregate, and verifybamid2 panel aggregate were still pending.
- Heartbeat `2026-05-17T21:14:32Z` command `309feba0-be14-451c-be3d-32390f51b44f`: status JSON still `phase=live_run` with `exit_code=null`; tmux present; Slurm summary `2 RUNNING` (`verifybamid2_contam` job 15591 and `gen_samstats` job 15594); live log reached 914/930 steps (98%). `relatedness_mqc.tsv`, `peddy_sample_qc_mqc.tsv`, and `vep_annotation_mqc.tsv` existed. `contamination_mqc.tsv`, `verifybamid2_panel_comparison_mqc.tsv`, and final MultiQC HTML were still pending.
- Heartbeat `2026-05-17T21:44:36Z` commands `62b9e3e8-8621-423c-8531-28f699cdc4bd` and `a31b43f7-9b80-4e0a-9069-c9dfd054e461`: status JSON still `phase=live_run` with `exit_code=null`; tmux present; live log reached 920/930 steps (99%). The only Slurm job still attributed to this workdir was `verifybamid2_contam` job 16379 for `KPF011-7`; another visible `sentieon_bwa_sort` job 16385 belonged to `/fsx/analysis_results/ubuntu/dayhoff-full-gui-f9fe0221/daylily-omics-analysis`, not this run. Final MultiQC HTML was not present yet.
- Completion heartbeat `2026-05-17T22:14:44Z` command `99f9b1fd-a44a-4ab7-a40a-4059ccb61d77`: status JSON `phase=live_success`, `exit_code=0`, `completed_at=2026-05-17T21:54:47Z`; tmux session absent after controller exit; no Slurm jobs attributed to the 602202 workdir; final MultiQC present at `results/day/hg38/reports/DAY_final_multiqc.html` (11,929,236 bytes, mtime `2026-05-17 21:54:25 +0000`). Checked aggregates present: `relatedness_mqc.tsv`, `peddy_sample_qc_mqc.tsv`, `vep_annotation_mqc.tsv`, `contamination_mqc.tsv`, and `verifybamid2_panel_comparison_mqc.tsv`.
