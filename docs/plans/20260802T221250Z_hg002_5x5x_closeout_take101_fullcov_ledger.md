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
| CLOSE-005 | FSx to S3 export | 2 | SUCCESS | Supported export completes and FSx/S3 object, byte, and required-artifact reconciliation proves the requested root is complete | DRA `dra-0f7e6dd80654daad7`; task `task-0d9e23c42a8c0113c` `SUCCEEDED` `7,271/7,271`, zero failed; detached/deleted; S3 `7,273` objects and `108,432,011,155` bytes exactly match the file-plus-directory-marker source model and FSx logical bytes; required hashes match |
| CLOSE-006 | Completion Slack | 2 | SUCCESS | Mike Kennemer and John Major receive one message with S3 URI, report, MultiQC, DayOA `13.4.1`, 5x/5x scope, caveats, and full-coverage-next note | Sent to proven Michael Kennemer + John Major DM `D0AQK8RB3D5`: `https://lsmchq.slack.com/archives/D0AQK8RB3D5/p1785711593140789` |
| T101-001 | Input inventory | 3 | SUCCESS | Exact reviewed Bjuice source hashes match Take21; the three SMN controls are NA19235 (4/0 concordant), NA20775 (3/1 primary, Sentieon discordant), and NA23687 (1/2 SMA carrier); NA23687 selected explicitly. Fresh provider-neutral Take101 manifests validate with 2 samples, 4 libraries, 8 sequencing inputs, 2 units, 8 links, all 8 ILMN lane pairs and 3 x 146 ONT paths per sample | Runtime `use_fq_data_starting_hrs=0 use_fq_data_up_to_hrs=25` supplies half-open elapsed-hour window `[0,25)` and historically retains 150/438 ONT FASTQs per sample; manifest subsample fields remain blank |
| T101-002 | Fresh Take101 boundary | 3 | SUCCESS | Fresh root, visit/lock, one-pane persistent Ubuntu Bash-login tmux, `day-clone -t 13.4.1 -d take101`, exact tag proof, and explicit manifests/config | Root `/fsx/analysis_results/preval-hiomr2/take101`; tmux `dayoa_take101_fullcov_hg002_na23687_20260802`; exact annotated tag `13.4.1` at `9d8d1a52...`; all payload hashes verified before install |
| T101-003 | Dry run | 4 | SUCCESS | Exact eight-target `dy-r` closure passes with `-j 333 -p -k -T 1 --rerun-triggers mtime -n` | Candidate dry run passed `RC=0` with `466` jobs, two samples, two NICU Truvari jobs, both samples retaining `150/438` ONT FASTQs, no Slurm submission, and normal lock release |
| T101-004 | Live run | 4 | IN_PROGRESS | Identical command with only `-n` removed is accepted and controller PID/log plus first jobs are recorded | Controller PID `3132158`; initial external jobs `3370`-`3375` accepted under `RnD`; both full-coverage samples represented; live RC remains pending |
| T101-005 | Live-start Slack | 4 | SUCCESS | Mike and John receive one message that two full-coverage production-snapshot samples are underway with estimated 5-6 hour completion | Sent after real submission: `https://lsmchq.slack.com/archives/D0AQK8RB3D5/p1785721601092879` |
| T101-006 | Single monitor | 4 | SUCCESS | Exactly one active same-thread heartbeat at 20-minute cadence; every third heartbeat updates Mike/John; instructions distinguish lost-node retry from proven code failure | Active automation `take101-fullcov-hiomr2-20-minute-monitor`; the only other on-disk heartbeat is paused and belongs to a different completed task |

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
- Export receipt: `docs/plans/20260802T221250Z_hg002_5x5x_closeout_take101_export/fsx_export.yaml`, schema `4`, status `success`, task `task-0d9e23c42a8c0113c`, DRA `dra-0f7e6dd80654daad7`, `delete_data_in_file_system=false`, detach lifecycle `DELETED`.
- S3 reconciliation: `s3://lsmc-ssf-sequencing-data/derived/preval-hiomr2/13-4-0/` contains `7,273` objects and `108,432,011,155` bytes. The count equals `6,298` regular files plus `975` non-root directory markers; bytes exactly equal the FSx logical-file baseline. S3-streamed SHA-256 values match FSx for the report HTML, report artifact, runbook, final MultiQC HTML/data, evidence manifest, final benchmark summary, and package manifest.
- Completion Slack: `https://lsmchq.slack.com/archives/D0AQK8RB3D5/p1785711593140789` sent only after export reconciliation to Michael Kennemer (`U0AQXA08V6Z`) and John Major (`U08TN63K73M`).

## Take101 input receipt recorded 2026-08-02T23:04:00Z

- Reviewed Bjuice source hashes match the prior accepted Take21 contract: `source_manifest_resolved.json` `f03b5f39...`, `run_evidence_v2.json` `363c2186...`, library/run matrix `3da41aca...`, sample snapshot `4ce4f1ee...`, and unit snapshot `c0af9f31...`.
- The three reviewed SMN copy-number controls are NA19235 (expected and observed SMN1/SMN2 `4/0`, two-caller concordant), NA20775 (expected `3/1`, primary SMNCopyNumberCaller `3/1`, Sentieon `3/2`), and NA23687 (expected and raw observed `1/2`, `isCarrier=true`, `PASS:Majority`). NA23687 is selected because it is the positive SMA-carrier boundary and has an already accepted full-coverage two-sample manifest lineage.
- Fresh artifacts: `docs/plans/20260802T221250Z_take101_hg002_na23687_fullcov_manifests/`. `dyec identities validate` passed foreign keys, ordered inputs, provider neutrality, and no identifier creation or rewriting. The two analysis-unit and delivery EUID fields remain blank, so this research run is not customer-release eligible.
- Exact manifest hashes: specimens `da22e23...`, samples `b673dba1...`, libraries `4e835d2f...`, sequencing inputs `b128e357...`, analysis units `a709bca2...`, input links `2ffd5038...`; generator receipt `8aa479f2...`, validation receipt `d3f823d7...`, overlay `f8143397...`.
- HG002 and NA23687 each have all eight Illumina R1/R2 lane pairs, blank SR/ONT subsample fields, and three reviewed ONT runs with 146 FASTQ paths each (438 paths total). The DayOA runtime bounds, not manifest subsampling, implement `[0,25)` with `use_fq_data_starting_hrs=0` and `use_fq_data_up_to_hrs=25`; the previously accepted equivalent graph retained 150/438 paths per sample.

## Take101 preflight and repair progress recorded 2026-08-03T01:37:36Z

- The fresh analysis root is `/fsx/analysis_results/preval-hiomr2/take101`. The persistent tmux `dayoa_take101_fullcov_hg002_na23687_20260802` has exactly one interactive Ubuntu Bash-login pane. `day-clone -t 13.4.1 -d take101 --executing-entity preval-hiomr2` succeeded, and the clone was proven to be exact annotated tag `13.4.1`, commit `9d8d1a52ae84bb38c1e9fca8c037ee4d2b4c18ec`.
- `source dyoainit` and the separate `dy-a slurm hg38` activation succeeded. The initialized tmux explicitly restores `DAY_PROJECT=RnD`, `DAYLILY_COST_CENTER=RnD`, and `SEQONE_DELIVERY_BATCH_ID=take101` before any `dy-r` invocation.
- Dry preflight 1 stopped before formal Snakemake execution because the minimal overlay had not enabled the required Truvari contract. The corrected explicit overlay SHA-256 is `2b204bae7f87e1057a421dfaa79f7729a514c0306804978513b42efb7caf23f5` and includes the proven GIAB SV v5.0q truth and NICU/package settings.
- Dry preflight 2 also stopped before formal execution, after again proving that both HG002 and NA23687 retain exactly `150/438` ONT FASTQs for elapsed hours `[0,25)`. Its terminal graph error was `sentdhiomr2_nicu_truvari`: the public all-active-sample NICU aggregate required a mandatory HG002-only GIAB SV benchmark artifact for NA23687. No controller or Slurm job was created by either failed preflight.
- Exact source inspection proved an internal graph/schema mismatch, not an input defect: `_hiomr2_nicu_manifest_paths()` expands all active samples, while `_hiomr2_nicu_artifact_paths()` mandates the two Truvari roles for every sample and `_hiomr2_nicu_truth_sample()` previously rejected every non-HG002 analysis unit during DAG construction.
- The write lock was acquired normally and the exact-tag clone was placed on branch `codex/13.4.2-take101-multisample-nicu-warning`. The bounded patch SHA-256 is `1b65d145f7b5fd6572a08b05ad9c4bdc0eafe94dff2593ecb80242f026bd1e51`; it changes four tracked files. HG002 still runs real GIAB SV v5.0q Truvari. Non-HG002 samples now publish an explicit `NOT_APPLICABLE` warning receipt with the query and truth VCF hashes, empty metrics, no attempted command, and no fabricated precision/recall/F1, while the rest of NICU, MultiQC, and Inflection packaging remains in scope.
- Focused tests pass `58 passed in 1.02s` in the exact headnode `DAY-EC` test runtime. Functional Ruff checks (`E9,F63,F7,F82`), the new CLI help path, and `git diff --check` pass. The first test invocation used the workflow runtime, which intentionally lacks pytest; that invocation is preserved separately and is not a code-test failure.
- The exact candidate dry/live harness SHA-256 is `b844dc48d956d7be7ca74b390fbad69135df5bcc4982760d133a3179a0792a4e`. It preserves the original eight targets and every option; `dry` adds only `-n`, and `live` removes only `-n`.
- The exact candidate dry run completed `RC=0` at `2026-08-03T01:41:18Z`. Its 466-job DAG contains both requested full-coverage samples and two `sentdhiomr2_nicu_truvari` jobs; the rendered non-HG002 shell path includes `truvari-not-applicable` with expected analysis unit `HG002-ck2ky6p4wk6exh`. The command line contains the exact eight targets, `[0,25)` selectors, `-j 333 -p -k -T 1 --rerun-triggers mtime -n`. It submitted no Slurm job and released the write lock normally.
- The write lock was reacquired normally and the identical live command with only `-n` removed was accepted at `2026-08-03T01:45Z`. Controller PID `3132158` is running from log `take101_hg002_na23687_fullcov_13.4.2_candidate_live_20260802.log`; initial external jobs `3370`-`3375` include both HG002 and NA23687 and were accepted under Slurm comment/cost center `RnD`.
- The required live-start Slack update was sent to the proven Michael Kennemer + John Major DM only after actual job submission: `https://lsmchq.slack.com/archives/D0AQK8RB3D5/p1785721601092879`.
- Exactly one active same-thread heartbeat exists: `take101-fullcov-hiomr2-20-minute-monitor`, 20-minute cadence, with every third check routed to the same Slack DM. The only other automation file is a paused 45-minute heartbeat for a different completed Take4 task.

## Terminal acceptance

- All ledger rows must be terminal.
- The 5x/5x closeout is not complete until verified S3 reconciliation and the first Slack handoff succeed.
- The Take101 launch objective is not complete until a real live controller is accepted, the second Slack message is sent, and exactly one 20-minute monitor is confirmed active.
