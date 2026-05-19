# ILMN 0006 Export, Peddy Touch, And Final MultiQC Readiness Ledger

Date opened: 2026-05-18

## Control

Controlling request: export ILMN 0006 `other_reports`, publish/verify CloudFront URLs, then export the full run directory while touching Peddy outputs and dry-running final MultiQC readiness.

Ledger path: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster/docs/plans/ilmn_0006_export_peddy_touch_multiqc_ledger.md`

Execution scope:
- AWS profile: `lsmc`
- AWS region: `us-west-2`
- Cluster: `may26-d`
- Headnode: `i-0e7639ff46f207ae7`
- Run ID: `ilmn_0006_align_dedup_alignstats_20260517T185626Z`
- Run checkout: `/fsx/analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis`
- CloudFront distribution: `E1O1EGAADAALSL` / `dlqovrcm5y71h.cloudfront.net`
- CloudFront origin path for exported FSx analysis results: `/FSxLustre20260515T103052Z/analysis_results/ubuntu`

Hard boundaries:
- Use the existing Basic-auth CloudFront distribution; do not create a new distribution.
- Do not intentionally rerun alignment, DMD dedup, SNV calling, or VEP.
- Use `--touch` only for Peddy outputs, not for final MultiQC.
- Run headnode payloads as `ubuntu` through DayEC SSM helpers.

## Gate 0 Baseline

- Local DayEC repo status: branch `codex/run-directory-mounts...origin/codex/run-directory-mounts`; existing unrelated untracked ledgers/reports/tmp-export artifacts are present.
- Gate 0 local timestamp: `2026-05-18T13:47:50Z`.
- Headnode baseline command: SSM `e8743aa6-9b62-4e49-b126-96bf10b1eb29`.
- Run checkout state: detached `HEAD`, `git describe=1.0.7-dirty`, `HEAD=a9d6a5d Restore native Mosdepth and VEP MultiQC inputs`, dirty `workflow/rules/common.smk`, untracked `sbatch_errs.log`.
- Controller/queue baseline: no Slurm jobs; two old `bash bin/day_run produce_sent_align ... produce_alignstats -j 200 -p -k` processes were visible but no active Snakemake/Slurm work was submitted from them.
- Final MultiQC baseline: missing at `results/day/hg38/reports/DAY_final_multiqc.html`.
- FSx `other_reports` baseline includes `alignstats_combo_mqc.tsv`, `alignstats_gs_mqc.tsv`, `giab_concordance_mqc.tsv`, `rtg_vcfstats_mqc.tsv`, `bcftools_variant_stats_mqc.tsv`, `vep_annotation_mqc.tsv`, `relatedness_mqc.tsv`, and `expansionhunter_mqc.tsv`.
- Existing S3 baseline for `alignstats_gs_mqc.tsv`: `ContentLength=1280527`, `ContentType=text/plain; charset=utf-8`, `LastModified=2026-05-18T03:30:51Z`.
- CloudFront baseline: distribution `E1O1EGAADAALSL` is `Deployed`, domain `dlqovrcm5y71h.cloudfront.net`, default origin `s3-may26d-analysis-root-20260517t014107z`, origin path `/FSxLustre20260515T103052Z/analysis_results/ubuntu`.

## Amendments

- 2026-05-18T13:52Z: User directed export work to use the old-fashioned single-DRA AWS CLI path instead of `daylily-ec export`. Active implementation uses `aws fsx create-data-repository-task --type EXPORT_TO_REPOSITORY` against FSx filesystem `fs-0c43ddf4b70dc87d8`.
- 2026-05-18T14:19Z: User directed manual touching of all expected Peddy output files after Snakemake `--touch` left `peddy=8` in the final MultiQC dry-run DAG.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | DayEC/DayOA/AWS | Record baseline run, repo, S3, CloudFront, Slurm, and report state. | SUCCESS | plan_amendment | Gate 0 | Agent 0 | Gate 0 Baseline section. |  | Baseline recorded before export/touch work. |
| EXP-OTHER-001 | DayEC/AWS | Export `results/day/hg38/other_reports` FSx to S3. | SUCCESS | feature_implementation | Gate 1 | Agent 1 | AWS CLI single-DRA export task `task-01a4fc6724bd54437` on filesystem `fs-0c43ddf4b70dc87d8` completed `SUCCEEDED`, `1351/1351` files, `0` failed. Receipt: `tmp-export/ilmn0006-other-reports-20260518T135329Z/fsx_export.yaml`. S3 head for `.../other_reports/alignstats_gs_mqc.tsv` returned `ContentLength=1280527`, `ContentType=text/plain; charset=utf-8`, `LastModified=2026-05-18T13:53:58Z`. |  | `other_reports` exported under `s3://lsmc-dayoa-omics-analysis-us-west-2/FSxLustre20260515T103052Z/analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis/results/day/hg38/other_reports`. |
| CF-OTHER-001 | AWS/CloudFront | Verify/report CloudFront URL prefix and at least one file URL. | SUCCESS | contract_test | Gate 1 | Agent 1 | Unauthenticated HEAD for `https://dlqovrcm5y71h.cloudfront.net/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis/results/day/hg38/other_reports/alignstats_gs_mqc.tsv` returned `401`; Basic-auth HEAD returned `200 text/plain; charset=utf-8`. |  | URL prefix: `https://dlqovrcm5y71h.cloudfront.net/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis/results/day/hg38/other_reports/`. Verified file URL: `https://dlqovrcm5y71h.cloudfront.net/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis/results/day/hg38/other_reports/alignstats_gs_mqc.tsv`. |
| EXP-FULL-001 | DayEC/AWS | Export the entire cloned run directory FSx to S3. | SUCCESS | feature_implementation | Gate 2 | Agent 2 | Worker `019e3b5f-82b8-79e1-9303-6c459155d188`; AWS CLI single-DRA export task `task-00a522d9f4ff3719a` completed `SUCCEEDED`, `503848/503848` files, `0` failed. Receipt: `tmp-export/ilmn0006-full-repo-20260518T135640Z/fsx_export.yaml`. S3 head for `.../other_reports/alignstats_gs_mqc.tsv` returned `ContentLength=1280527`, `ContentType=text/plain; charset=utf-8`, `LastModified=2026-05-18T13:53:58Z`. |  | Full run directory exported to `s3://lsmc-dayoa-omics-analysis-us-west-2/FSxLustre20260515T103052Z/analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z`. |
| PEDDY-TOUCH-001 | DayOA/AWS | Run peddy-only `--touch` command. | SUCCESS | feature_implementation | Gate 2 | Agent 3 | Worker `019e3b5f-83e6-7c13-aa51-ad9ffb2c3d1c`; command `DAY_CONTAINERIZED=true bin/day_run produce_peddy -j 200 -p -k --touch --rerun-triggers mtime --config genome_build=hg38 "aligners=['sent']" "dedupers=['dmd']" "snv_callers=['sentd']" "sv_callers=[]"` returned `rc=0`. Initial dry-run still had `peddy=8`, so a manual touch pass created/stamped all expected Peddy outputs across `328` peddy directories, including `328` done files, `64` missing companion artifacts, `4200` touched files/stamps, regenerated `results/day/hg38/other_reports/peddy_sample_qc_mqc.tsv` at `216297` bytes, and wrote `logs/peddy_gathered.done`. Receipt: `/home/ubuntu/daylily-runs/ilmn_0006_align_dedup_alignstats_20260517T185626Z/manual_touch_peddy_expected_20260518T141932Z.log`. |  | Peddy outputs and rollup were manually created/stamped after Snakemake `--touch` left NTC Peddy jobs in the DAG. |
| MQC-DRYRUN-001 | DayOA/AWS | Run final `produce_multiqc_all -n --rerun-triggers mtime` and capture job table. | SUCCESS | contract_test | Gate 3 | Agent 3 | Post-manual-touch dry-run `DAY_CONTAINERIZED=true bin/day_run produce_multiqc_all -j 200 -p -k --rerun-triggers mtime -n --config genome_build=hg38 "aligners=['sent']" "dedupers=['dmd']" "snv_callers=['sentd']" "sv_callers=[]"` returned `dryrun_rc=0`. Log: `/home/ubuntu/daylily-runs/ilmn_0006_align_dedup_alignstats_20260517T185626Z/manual_peddy_touch_multiqc_dryrun_20260518T142136Z.log`. Job table: `aggregate_report_components=1`, `alignment_qc_outputs_custom_data=1`, `collect_rules_benchmark_data=1`, `compile_seqfu=1`, `contamination_mqc_gather=1`, `multiqc_final_wgs=1`, `produce_cov_uniformity=1`, `produce_multiqc_all=1`, `sequence_qc_outputs_custom_data=1`, `stage_multiqc_inputs=1`, total `10`. No Peddy, alignment, DMD dedup, SNV, alignstats, or VEP jobs remained. |  | Dry-run is Peddy-clean. Real MultiQC execution was not launched because the remaining DAG still includes 10 final/gather/staging jobs including `produce_cov_uniformity`; this was stopped for review per the original plan. |
| FINAL-001 | DayEC/DayOA/AWS | Reconcile evidence, terminalize rows, report URL(s), export receipts, and remaining work. | OPEN | contract_test | Gate 4 | Agent 0 | Pending. |  |  |
