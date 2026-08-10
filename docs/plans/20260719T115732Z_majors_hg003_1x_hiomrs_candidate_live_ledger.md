# Majors HG003 1x HIOMRS Candidate Live Ledger

Created: `2026-07-19T11:57:32Z`

## Objective

Run a fresh HG003 1x HIOMRS kitchen-sink workflow on `majors-cluster` using
the mounted slim-data inputs and exact DayOA candidate commit
`1818223c3dfc9fc9e8227db40a8fc29224406b4d`, through the supported locked
`dy-r`/tmux execution path.

## Gate 0 Baseline

- Controlling ledger: `docs/plans/20260719T115732Z_majors_hg003_1x_hiomrs_candidate_live_ledger.md`.
- Local DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `main`, behind `origin/main` by 41 commits; three pre-existing untracked ledgers under `docs/plans/` including the bootstrap ledger.
- Target: AWS profile `lsmc`, region `us-west-2`, cluster `majors-cluster`, remote user `ubuntu` through `dyec headnode connect`.
- Requested DayOA identity: exact commit `1818223c3dfc9fc9e8227db40a8fc29224406b4d`; do not substitute the later published `13.0.8` tree.
- Requested input class: HG003 1x slim-data. Exact manifest rows and mounted source paths must be inventoried live before launch.
- Runtime contract: persistent named tmux; separate `source dyoainit`, `dy-a slurm hg38`, and `dy-r` commands; no raw Snakemake; fresh analysis root; visit and write-lock evidence before mutation; clean dry-run before live submission.
- No budget change, cancellation, teardown, root takeover, or destructive AWS action is authorized.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| INV-001 | Live inventory | Record cluster queue/controller state, DayOA/DYEC identities, candidate initialization, and exact HG003 1x slim-data source rows | SUCCESS | contract_test | Gate 0 | orchestrator | DYEC `12.0.2`; candidate `1818223c3dfc9fc9e8227db40a8fc29224406b4d`; initial queue contained only pre-existing sleep job `251`; no DayOA controller |  | Four analysis units join one specimen/sample/library to ILMN R1/R2 and ONT 1x inputs; all mounted sources and GIAB truth directory readable. |
| ROOT-001 | FSx analysis root | Create a fresh uniquely named root and clone exact candidate commit from the authenticated bundle | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `/fsx/analysis_results/majors-cluster/hg003-1x-hiomrs-1308cand-20260719T115732Z/daylily-omics-analysis`; detached HEAD `1818223c3dfc9fc9e8227db40a8fc29224406b4d` |  | Fresh bundle clone; no prior workflow outputs reused. |
| LOCK-001 | Agent locking | Record visit and acquire exact-root write lock with stable agent identity | IN_PROGRESS | legitimate_safety_handling | Gate 2 | orchestrator | Write visits recorded; lock reacquired after renderer-gate repair and currently owned by `codex-root-majors-hg003-1x-20260719` |  | `dy-r` released the first lock correctly after the pre-submission Mermaid failure; current live controller owns the reacquired interval. |
| INPUT-001 | DayOA config | Install only the exact HG003 1x slim-data specimens/samples/libraries rows and verify every source path | SUCCESS | active_product_contract | Gate 3 | orchestrator | Six fixture hashes: `60ba3d59`, `bc36cebf`, `071c714e`, `88e65c99`, `896fea5a`, `1e07a045`; validator schema `dayoa.manifests.validation.v1` |  | Validation: 1 specimen, 1 sample, 1 library, 2 sequencing inputs, 4 analysis units, 8 joins; all invariants true. |
| ENV-001 | DAYOA install | Complete the candidate DAYOA runtime installation and renderer gate | SUCCESS | config_or_startup_contract | Gate 4 | orchestrator | `dayoa` at DAYOA env; editable project `/home/ubuntu/dayoa`; `mmdc 11.15.0`; 7,716-byte smoke PDF; Snakemake `7.25.0b113` | Existing DAYOA env caused `dyoainit` to skip installation; stale Puppeteer Chrome `148.0.7778.97` cache lacked its executable; `dy-b` is a DYEC installer and its alias points at stale DYEC `11.0.4`. | Removed only the incomplete 21 MiB browser-version cache, reran candidate `day_env_installer.sh`, and installed the clean exact candidate checkout editable into DAYOA. |
| DRY-001 | DayOA DAG | Run clean fail-fast kitchen-sink dry-run through `dy-r` in tmux | SUCCESS | contract_test | Gate 5 | orchestrator | `RETURN CODE: 0`; 556 jobs; 1-128 threads; identical target/config set; no `-k` |  | Repeated successfully after installation repair. |
| LIVE-001 | DayOA execution | Submit the identical kitchen-sink command live and preserve controller/Slurm receipts | SUCCESS | contract_test | Gate 5 | orchestrator | Controller PIDs `1014590`/`1014830`; initial Slurm job IDs `252`-`268` submitted across `i128nvme` and `i192nvme` | Initial attempt failed before submission because `mmdc` was missing; no workflow jobs were created. | Repaired install and relaunched the identical command; first wave contains LR/SR preparation, FastQC, SeqFu, and sex-panel validation. |
| MON-001 | Monitoring | Report controller, queue, accounting, lock, and initial progress without claiming completion early | IN_PROGRESS | legitimate_safety_handling | Gate 5 | orchestrator | Tmux `majors-hg003-1x-hiomrs-1308cand-20260719`; `sacct` reports jobs `252`-`268` RUNNING; `squeue` shows nodes CONFIGURING; lock owned by `codex-root-majors-hg003-1x-20260719` |  | Controller is active; workflow is submitted but not complete. Pre-existing sleep job `251` remains separate. |

## Final Report

All rows terminal: `no`

Objective complete: `no`
