# HG002 5x/5x closeout, export, and Take101 full-coverage execution ledger

- Created: `2026-08-02T22:12:50Z`
- Human requestor: John Major
- Cluster: `preval-hiomr2` (`lsmc`, `us-west-2`)
- Completed-run analysis root: `/fsx/analysis_results/preval-hiomr2/13-4-0`
- Planned Take101 analysis root: `/fsx/analysis_results/preval-hiomr2/take101`
- Released DayOA baseline: annotated tag `13.4.1`, commit `9d8d1a52ae84bb38c1e9fca8c037ee4d2b4c18ec`
- Prior run ledger: `docs/plans/20260802T101851Z_hg002_5x5x_hiomr2_1340_kitchensink_ledger.md`

## Objective

Close the terminal HG002 5x Illumina plus 5x ONT HIOMR2 kitchen-sink, mega, and Inflection analytical-package run with an evidence-backed technical report, runbook, verified complete FSx-to-S3 export, and Slack handoff. Only after that handoff, create Take101 at exact DayOA `13.4.1` using proven full-coverage HG002 and one proven SMN12-positive-control Illumina plus ONT `[0,25)` inputs; pass the exact `-j 333 -p -k -T 1 -n` preflight, launch the identical live command without `-n`, notify Mike Kennemer and John Major, and leave exactly one 20-minute same-thread monitor.

## Gate 0 baseline

- The prior ledger records terminal `RC=0`, an empty Slurm queue, no remaining analysis write lock, final MultiQC job `3369` completed `0:0`, and final MultiQC SHA-256 `a5ba27d9d2207b30b759389fd23b51fc9c269781f1e486abef9240cb94e5af05`.
- The prior ledger records Inflection analytical packaging job `3364` completed `0:0` with schema `dayoa.hiomr2_inflection_analytical_package/1.3`, 37 artifacts, and `nicu_research_included=true`.
- The prior ledger records branch `codex/13.4.1-hg002-hiomr2-repairs`, pushed release commit `9d8d1a52...`, and pushed annotated non-v tag `13.4.1`.
- The prior heartbeat automation was deleted. No recurring automation may be created until the Take101 live controller exists; then exactly one 20-minute heartbeat is allowed.
- Existing unrelated tracked and untracked work in this DYEC checkout is excluded. Only this ledger and the exact `20260802T221250Z_hg002_5x5x_closeout_take101_artifacts/` report bundle may be staged unless a later proven DYEC change is explicitly required.

## Execution ledger

| ID | Scope | Gate | State | Evidence / exit criteria | Notes |
|---|---|---:|---|---|---|
| CLOSE-001 | Reverify completed run | 0 | SUCCESS | Current headnode, tmux, controller, Slurm, lock, tag, MultiQC, package, benchmark, and receipt state independently match the prior closure record | Read-only except required visit logs; FSx capacity also passed with 6.2 TB free and balanced 45-46% OST use |
| CLOSE-002 | Metric inventory | 1 | SUCCESS | Complete inventory of `ROI==giabHC` SNV hard-VCF F-scores, Sentieon and SMN12 copy-number evidence, every Truvari output/receipt, and explicit gaps | Durable audit TSVs preserve completion artifacts, SMN12 evidence, and 13 Truvari/alias/NICU rows without treating raw diagnostic summaries as published metrics |
| CLOSE-003 | Runbook | 1 | SUCCESS | Checked technical run instructions written into the completed analysis root | Exact eight-target `dy-r` command, config, selectors, tmux/init sequence, lock contract, completion checks, and stale-banner caveat recorded in `HG002_5x5x_HIOMR2_13.4.1_RUNBOOK.md` |
| CLOSE-004 | Technical report | 1 | SUCCESS | Canonical report artifact and verified self-contained HTML written into the analysis root; exact evidence paths and limitations included | Browser verification passed at 1440 and 390 px with 14 blocks, one chart, four tables, and keyboard source interaction; all six report-bundle hashes match local-to-FSx |
| CLOSE-005 | FSx to S3 export | 2 | NOT_STARTED | Supported export completes and FSx/S3 object, byte, and required-artifact reconciliation proves the requested root is complete | A successful task alone is not full-mirror proof |
| CLOSE-006 | Completion Slack | 2 | NOT_STARTED | Mike Kennemer and John Major receive one message with S3 URI, report, MultiQC, DayOA `13.4.1`, 5x/5x scope, caveats, and full-coverage-next note | Send only after verified export |
| T101-001 | Input inventory | 3 | NOT_STARTED | Exact HG002 and three SMN12-control source manifests, byte/read inventories, identities, and ONT `[0,25)` semantics are proven; one SMN12 control selected explicitly | Labels alone are insufficient |
| T101-002 | Fresh Take101 boundary | 3 | NOT_STARTED | Fresh root, visit/lock, one-pane persistent Ubuntu Bash-login tmux, `day-clone -t 13.4.1 -d take101`, exact tag proof, and explicit manifests/config | Never reuse a pre-existing root silently |
| T101-003 | Dry run | 4 | NOT_STARTED | Exact eight-target `dy-r` closure passes with `-j 333 -p -k -T 1 --rerun-triggers mtime -n` | No live jobs on failure |
| T101-004 | Live run | 4 | NOT_STARTED | Identical command with only `-n` removed is accepted and controller PID/log plus first jobs are recorded | Preserve `DAY_PROJECT=RnD`, `DAYLILY_COST_CENTER=RnD` |
| T101-005 | Live-start Slack | 4 | NOT_STARTED | Mike and John receive one message that two full-coverage production-snapshot samples are underway with estimated 5-6 hour completion | Send only after real submission |
| T101-006 | Single monitor | 4 | NOT_STARTED | Exactly one active same-thread heartbeat at 20-minute cadence; every third heartbeat updates Mike/John; instructions distinguish lost-node retry from proven code failure | No duplicate scheduled task |

## Monitoring and repair boundary

- Monitor controller, Slurm, direct rule logs, receipts, and outputs read-only.
- Leave lost-node recovery to `-T 1`; do not cancel or requeue such jobs.
- Only after evidence proves a non-node-loss code defect and identifies the workflow-respawned replacement job may the explicitly authorized bounded kill be considered. Record a kill visit, hold the analysis-root kill/write lock, use `dyec analysis guard`, and touch only that exact replacement job.
- Diagnose source defects only after the controlling workflow has reached the relevant terminal failure boundary. Test any fix with focused tests and the exact mtime dry run before another live retry.
- Commit and push a repair branch and create the next annotated non-v semver tag only after live proof; never move an existing tag and never stage analysis inputs or logs.

## Closeout evidence recorded 2026-08-02T22:49:11Z

- Headnode: `i-0b70541bdad454c76` / `ip-10-0-0-138`; cluster `preval-hiomr2`; analysis root `/fsx/analysis_results/preval-hiomr2/13-4-0`.
- Reverification: controller absent, Slurm queue empty, tmux `dayoa_hg002_5x5x_1340_20260802` alive with one pane, write lock absent after report installation, annotated DayOA tag `13.4.1` peels to `9d8d1a52ae84bb38c1e9fca8c037ee4d2b4c18ec`.
- Capacity: FSx reports approximately `6.2 TB` available (`46%` used); data OSTs are balanced at `45-46%`. No historical-root export or deletion is required.
- Final MultiQC: `daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html`, `10,341,154` bytes, SHA-256 `a5ba27d9d2207b30b759389fd23b51fc9c269781f1e486abef9240cb94e5af05`.
- Final MultiQC data: `14,296,219` bytes, SHA-256 `80c29469a71a2826a103f84cced2227500080e59589d5e314969d1a77a29a818`.
- Final evidence manifest: `323,836` bytes, SHA-256 `2e49a88de2b4d854c3d10634cbf9bb1ed5ce2913cdcc7237536c59f126a32b3d`.
- Final regenerated benchmark TSV: `81,455` bytes, SHA-256 `65176c21073cea7150ef27a210ac9779f6e3df375f0e3553a65993282d99939b`; this supersedes the earlier pre-final snapshot recorded in the prior ledger.
- Inflection package manifest: schema `dayoa.hiomr2_inflection_analytical_package/1.3`, `37` artifacts, NICU included, analytical/research use only and not customer-release eligible.
- Portable report verification: `{ok:true}`, `14` blocks, `1` chart, `4` tables, keyboard source dialog passed, viewports `1440` and `390`.
- FSx report-bundle hashes:
  - runbook `e93ea9659e4e4f31d6567d06cce2552ad2fa0f6893b639dcd57c38f5a8b3f69e`
  - report HTML `5139f4f669a42b234fb251e2c229afd354b0308753d080a72233cba181ff5209`
  - artifact JSON `621b2520d4e50ad7d077d80658341ee33177ce0b00b3860f509a21ce87a16ad3`
  - completion receipt `9470de1c3d800e22fd8ec31eae6737f2441f5bf8eb2817afd82993f57a515b66`
  - SMN12 audit `e1f16d06797024f27705ee5f2245cc1d8679fda6d9bcdadfb123c04b8963a1ef`
  - Truvari audit `c1c135672c01b89ef107f3b6622d79d8def59fdd183f71787beb4956559cce65`

## Terminal acceptance

- All ledger rows must be terminal.
- The 5x/5x closeout is not complete until verified S3 reconciliation and the first Slack handoff succeed.
- The Take101 launch objective is not complete until a real live controller is accepted, the second Slack message is sent, and exactly one 20-minute monitor is confirmed active.
