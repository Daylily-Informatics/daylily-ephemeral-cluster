# Take222 + Take333lc final HIOMR2 report refresh ledger

Created: 2026-08-04T17:30:58Z

Objective: preserve every reader-facing section of `/Users/jmajor/Downloads/dyec-dayao-pipe-runtime-artifacts/report.pdf`, add the terminal Take333lc HG002 5x/5x MultiQC and Inflection packaging evidence, report all available SNV concordance rows by sample/caller/ROI/variant class, report every produced SV caller/merger VCF against available Truvari evidence without fabricating missing scores, distinguish expected SMN1/SMN2 copy number from Sentieon SegDup and SMNCopyNumberCaller outputs, and deliver verified Markdown and PDF files with explicit eventual S3 URI fields.

## Gate 0 inventory

- Existing report bundle: `/Users/jmajor/Downloads/dyec-dayao-pipe-runtime-artifacts`.
- Existing reader-facing source: `notes.md`; rendered sources: `artifact.json`, `report.html`, and `report.pdf`.
- Existing PDF: Take222 full-coverage report, 12 US-letter pages, generated 2026-08-04T09:23:22-07:00.
- Existing report evidence: Take222 HG003/HG004/NA19235/NA20775 coverage, SNV concordance, SMN, NICU/Truvari gaps, output inventory, MultiQC, Inflection packages, runtime/cost, recommendations, current-testing snapshot, source inventory, and limitations.
- New evidence root: `/fsx/analysis_results/preval-hiomr2/take333lc`, exact DayOA tag `13.4.3` (`0ead6be3ded35a2652afb4fa6b08af893c188c84`).
- Take333lc terminal proof already established in the campaign ledger: five-target post-budget live RC 0, strict final MultiQC, evidence manifest, analytical Inflection package, empty Slurm queue, and released analysis lock.
- No S3 export destination for Take333lc has been confirmed in this reporting task. S3 URI fields must remain explicitly pending rather than guessed.

## Execution rows

| ID | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|
| RPT-001 | Inventory and preserve every existing report section and source artifact | IN_PROGRESS | Existing `notes.md`, 32 artifact blocks, 21 datasets, and 16 sources inventoried |  |
| RPT-002 | Extract completed Take333lc MultiQC, SNV, Truvari SV, SMN, packaging, runtime, and output evidence | PENDING |  |  |
| RPT-003 | Reconcile sample/caller/ROI/class metric grains and explicit gaps | PENDING |  |  |
| RPT-004 | Rebuild full Markdown and portable HTML report without dropping prior sections | PENDING |  |  |
| RPT-005 | Render and visually verify PDF; include eventual S3 URI fields | PENDING |  |  |
| RPT-006 | Commit durable ledger and hand off final artifacts | PENDING |  |  |

## Stop rules

- Do not invent S3 URIs, truth metrics, expected SMN copy numbers, caller identities, or benchmark applicability.
- Treat empty/absent Truvari metrics as unavailable, not zero.
- Preserve the distinction between independent callers, materialization/evaluation routes, and merger outputs.
- Read-only analysis-root inspection requires recorded visits; no workflow, Slurm, export, or delete mutation is authorized by this report refresh.
- Preserve every existing report section unless a narrow dependent correction is required by newer terminal evidence.
