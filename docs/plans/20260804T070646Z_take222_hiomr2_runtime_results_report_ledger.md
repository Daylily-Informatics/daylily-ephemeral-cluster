# Take222 HIOMR2 runtime/results report and current-campaign Slack handoff ledger

Created: 2026-08-04T07:06:46Z

Objective: identify the most recent completed full HIOMR2 kitchen-sink, mega/NICU, final-MultiQC, and Inflection analytical-packaging run; extract sample, coverage, caller, result, runtime, output-inventory, MultiQC, and packaging evidence; make evidence-backed recommendations about caller combinations and optional tools; write a portable technical report plus Markdown notes and a visually verified PDF hard copy under `/Users/jmajor/Downloads/dyec-dayao-pipe-runtime-artifacts`; capture the current live-testing snapshot; and send the finished report to Mike Kennemer, John Major, and the unambiguously resolved Slack user "AG".

## Gate 0 inventory

- Controlling ledger: this file.
- Most recent completed lane: Take222 at `/fsx/analysis_results/preval-hiomr2/take222`, four samples (HG003, HG004, NA19235, NA20775), DayOA `13.4.3`, terminal five-target proof 21/21 RC 0, final MultiQC, complete NICU research, sharded Jasmine, and four Inflection analytical packages.
- Current live-testing lane: Take333 campaign ledger `docs/plans/20260804T004100Z_take333_remaining_giab_hiomr2_ledger.md`; `take333lc` HG002 5x/5x and `remaining-giab` four-sample full-coverage runs are both live under DayOA `13.4.3`.
- Chronicle was fresh at 2026-08-04T07:05Z and showed an active headnode queue view; Chronicle is context-only. All quantitative claims must be upgraded to workflow artifacts, benchmark receipts, MultiQC data, Slurm accounting, or durable ledgers.
- Existing reusable report model: `docs/plans/20260803T082714Z_take101_export_take222_report/`.
- Requested output directory does not yet exist. It will be created as `/Users/jmajor/Downloads/dyec-dayao-pipe-runtime-artifacts` (correcting only the `Downlads` typo while preserving the requested directory name).
- DYEC canonical checkout is materially dirty with unrelated user work. Only this ledger and explicitly created report-support files are in scope; unrelated changes must remain untouched.
- Evidence collection and cluster status inspection are read-only. No workflow, Slurm, AWS, or analysis-root mutation is authorized.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| RPT-001 | Scope | Prove the latest completed qualifying run and bind the report to its exact version, samples, targets, and terminal state | SUCCESS | contract_test | Gate 0 | orchestrator | Take222 terminal ledgers and DayOA `13.4.3` release records; four samples; five-target 21/21 RC 0 |  | Latest completed qualifying lane proven |
| RPT-002 | Results | Extract per-sample coverage/fragment metrics, SNV `ROI=giabHC` results, SMN1/2 positive-control outputs, SV/Truvari results, and caller/treatment inventory | SUCCESS | feature_implementation | Evidence gate | orchestrator | Reviewed TSVs under `/Users/jmajor/Downloads/dyec-dayao-pipe-runtime-artifacts`; 61 source files collected read-only |  | Metrics and applicability gaps explicitly represented |
| RPT-003 | Runtime | Collect task-level benchmark data and derive per-sample elapsed task totals, bottlenecks, caller/runtime breakdowns, and best observed runtime measures without conflating task wall time with controller makespan | SUCCESS | feature_implementation | Evidence gate | orchestrator | 706 benchmark rows; per-sample and per-rule TSVs; task-wall/vCPU/cost caveats in report |  | Benchmark burden kept separate from controller makespan |
| RPT-004 | Outputs | Describe the kitchen-sink, mega/NICU, MultiQC, and Inflection analytical-package file families and verify package manifests | SUCCESS | feature_implementation | Evidence gate | orchestrator | Complete 5,881-path inventory; four schema-1.3 manifests; MultiQC HTML/JSON review |  | All requested output families documented |
| RPT-005 | Recommendations | Rank evidence-supported tool combinations and identify redundant, diagnostic-only, or candidate-optional tools with explicit caveats | SUCCESS | feature_implementation | Analysis gate | orchestrator | `notes.md` and report recommendation sections |  | No SV accuracy ranking fabricated without HG002 truth |
| RPT-006 | Current state | Capture a fresh read-only snapshot of `take333lc` and `remaining-giab` controllers, progress, jobs, failures, and FSx capacity | SUCCESS | legitimate_safety_handling | Live-read gate | orchestrator | Snapshot at 2026-08-04T07:40:40Z; controllers/queue empty; 4,543,561,072,640 FSx bytes free |  | `remaining-giab` workflow RC 0 but packaging incomplete; `take333lc` RC 1 at 97% |
| RPT-007 | Report | Produce `notes.md`, canonical `artifact.json`, portable `report.html`, source datasets/notes, and chart map in the requested Downloads directory | SUCCESS | feature_implementation | Report gate | orchestrator | Portable delivery receipt: validation/package/verification passed; 27 blocks, 4 charts, 11 tables; desktop and narrow viewport QA |  | Complete local artifact bundle created |
| RPT-008 | Hard copy | Convert the portable report to PDF, render every page, and visually verify legibility and layout | SUCCESS | contract_test | PDF QA gate | orchestrator | 11-page letter PDF; every page rendered; final current-state page rechecked after table-width correction |  | Hard copy is legible without clipping |
| RPT-009 | Slack | Resolve Mike Kennemer, John Major, and "AG" exactly; post one concise message with report paths/links and current live-test snapshot | SUCCESS_WITH_LIMITATION | feature_implementation | Final evidence gate | orchestrator | Michael Kennemer `U0AQXA08V6Z`; John Major `U08TN63K73M`; AG/Andrew Geller `U0ADESEKP1U`; Canvas `F0BMDHL13RV`; message `p1785829644395069` | Slack authorization lacks `files:write:user` | Canvas and message delivered; PDF attachment accurately disclosed as unavailable |
| RPT-010 | Acceptance | Terminalize all rows, preserve evidence, and report exact completed artifacts and residual gaps | SUCCESS | contract_test | Gate 5 | orchestrator | All rows terminal; local bundle, PDF, Canvas, and Slack message verified |  | Objective complete with one disclosed Slack attachment limitation |

## Stop rules

- Never infer a caller metric, sample identity, positive-control claim, runtime, or output file from naming alone.
- Keep descriptive benchmark task wall time separate from controller makespan and Slurm pending/configuring time.
- Do not describe non-HG002 `WARNING` applicability receipts as benchmark performance.
- Do not guess who "AG" is; Slack posting is blocked until the user is resolved unambiguously.
- Do not mutate or administer the current live workflows or Slurm jobs.
- Do not send Slack before the final HTML/PDF/Markdown artifacts and the current live snapshot are verified.

## Terminal evidence

- Local bundle: `/Users/jmajor/Downloads/dyec-dayao-pipe-runtime-artifacts`.
- Primary narrative: `notes.md`.
- Portable report: `report.html`; canonical payload: `artifact.json`; receipt: `portable_delivery_receipt.json`.
- Hard copy: `report.pdf`, 11 pages, letter size, visually verified after final current-state-table correction.
- Terminal SHA-256: `notes.md` `8931b5a1fe04fd61ebfb6f468e320fe3d6bed3b161fd57d645d205dfa3758184`; `report.html` `227d85b9d41bb222a54523220f2655f8762edbe551f4aa9ed26e9dc0262cf570`; `report.pdf` `d6c0859f8ced93ca18c6899d226e953849ff3101881aa6e148e7a2b118badaf5`; `artifact.json` `06722095ca6f40bed8e9be89700bb6f75df5ee7de5a66f17387cd4229478710f`.
- The portable verifier passed validation, packaging, and enhanced-reader verification at 1440 px and 390 px.
- Slack Canvas: `https://lsmchq.slack.com/docs/T08TXCVESPL/F0BMDHL13RV`.
- Slack handoff: `https://lsmchq.slack.com/archives/C0ATKCY450U/p1785829644395069`.
- Residual gap: the Slack app connection lacks `files:write:user`, so the verified PDF remains in the local bundle rather than attached to Slack. The message and Canvas state this limitation explicitly.
