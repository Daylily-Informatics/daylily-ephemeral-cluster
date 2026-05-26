# hyb-hg003 HIOMR Matrix Export And Report Ledger

## Gate 0

Created: 2026-05-26T15:09:44Z

Scope:
- Export remaining `hyb-hg003` `/fsx/analysis_results/ubuntu/<analysis-id>` matrix outputs to S3 using explicit DRA export.
- Write a detailed report covering all HG003 Altair3 HIOMR matrix attempts, including original input locations, pipeline versions, final S3 locations, coverage mix, GIAB HC concordance, available variant files, run outcome, and reproducibility commands.
- Include the cluster deletion command, but do not execute deletion without a separate explicit destructive-action confirmation.

Export destination root:
`s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/ubuntu/`

Live FSx directories present at Gate 0:
- `hg003a_altair3_hiomr_ilmn15x_ont5x_1022` (`126G`, cancelled at 2026-05-26T15:06Z after retry)
- `hg003a_altair3_hiomr_ilmn10x_ont10x_1022` (`60G`, failed at `rtg_vcfeval_roi`)
- `hg003a_altair3_hiomr_ilmn7x_ont7x_1022` (`46G`, failed at `rtg_vcfeval_roi`)
- `hg003a_altair3_hiomr_ilmn7x_ont5x_1022` (`66G`, cancelled at 2026-05-26T15:06Z)
- `hg003a_altair3_hiomr_ilmn5x_ont5x_1022` (`54G`, cancelled at 2026-05-26T15:06Z)

No destructive AWS action is approved in this ledger.

## Rows

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| G0-001 | Record live FSx dirs, destination root, and no-delete boundary. | SUCCESS | Gate 0 above. |
| EXP-001 | Export remaining FSx matrix dirs to S3. | IN_PROGRESS | One `dyec export` per analysis directory. |
| EVID-001 | Collect run metadata, input manifests, logs, VCFs, coverage and concordance summaries. | PENDING |  |
| REPORT-001 | Write detailed experiment report. | PENDING | Target `docs/hyb_hg003_hiomr_experiment_report.md`. |
| FINAL-001 | Report terminal row counts and cluster-delete confirmation boundary. | PENDING |  |
