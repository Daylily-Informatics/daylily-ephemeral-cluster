# IFX P2 second-half prevalidation DayOA 11.0.20 live ledger

Date: 2026-07-16

## Control Ledger

Controlling request: on `ifx-p2-1000-120-0715` with AWS profile `lsmc`, create `day-clone -t 11.0.20 -d second-half-preval` and run the HIOMRS kitchensink command from that exact new clone.

Ledger path: `docs/plans/20260716T183512Z_ifx_p2_second_half_preval_11020_live_ledger.md`

### Runtime contract

- AWS profile: `lsmc`; region: `us-west-2`; cluster: `ifx-p2-1000-120-0715`.
- Exact analysis id: `second-half-preval`.
- Exact immutable DayOA tag: annotated tag `11.0.20`, tag object `91b528000d8513a86743bc985b1ffc1d348acc8f`, commit `9c2414d65909274ca6453f6b71da05cec3e67c41`.
- Inputs continue the immediately preceding request: `/Users/jmajor/projects/lsmc/remaining/samples.tsv` and `/Users/jmajor/projects/lsmc/remaining/units.tsv`, exactly 10 libraries.
- Command continues the preceding accepted kitchensink contract: the full `hybrid_ilmn_ont_hiomrs_kitchensink` target/config set, `slurm hg38`, `-j 300 -p -T 2 -k`, `--rerun-triggers mtime`, `--rerun-incomplete`, and explicit `use_fq_data_starting_hrs=0 use_fq_data_up_to_hrs=25` (`[0,25)`).
- Required execution order: fresh exact-tag clone -> byte-identical manifest staging -> separate `source dyoainit` -> separate `dy-a slurm hg38` -> exact dry-run with `-n` -> identical live `dy-r` without `-n` only after dry-run rc 0.
- No raw `snakemake`; all workflow commands run as `ubuntu` in one persistent, meaningfully named, one-pane `bash -il` tmux session.
- The live controller and all analysis-root writes require the current agent to own the exact analysis-root write lock. No takeover, job cancellation, Slurm administration, or destructive cleanup is authorized.

### Gate 0 baseline

- DayOA `git fetch --tags --prune origin` verified annotated tag `11.0.20` and peeled commit `9c2414d65909274ca6453f6b71da05cec3e67c41`.
- Tag `11.0.20` retains strict raw-ONT hour-window configuration via `use_fq_data_starting_hrs` and `use_fq_data_up_to_hrs`.
- Samples manifest: 10 records, SHA-256 `0a662e6abbd200a8636f7c2bb4dec73f55bdacaf9e1995977e77108ffc3a5824`.
- Units manifest: 10 records, SHA-256 `0a070b8f9219e7e4dd443175470134f1379c83e629320234ae7500df6392e0c9`.
- DYEC checkout has pre-existing user changes and untracked files; this execution owns only this new ledger. Do not configure the headnode from the dirty local checkout.
- Immediately preceding live checks on this cluster showed both required DRAs `AVAILABLE`, all 4,540 listed inputs present/nonempty, `/fsx` at 18% utilization with 9.3 TiB available, and no existing live controller for the prior dry-run root. These facts must be refreshed where material before the new live launch.

### Live evidence

- Gate 1 refresh: requested root absent; Slurm queue empty; no DayOA controller process; `/fsx` 12 TiB total, 2.0 TiB used, 9.3 TiB available (18%), inode use 5%.
- DRA refresh: ILMN `dra-0017c9af390ef592a` and ONT `dra-09989fe0dd83e5955` independently verified `AVAILABLE` at the exact manifest roots.
- Persistent session: `second_half_preval_11020_20260716`, one window/pane, `ubuntu`, `bash -il`.
- Analysis root: `/fsx/analysis_results/ifx-p2-1000-120-0715/second-half-preval`; lock owner `codex-root-ifx-p2-second-half-11020-20260716`.
- Checkout exact identity: tag `11.0.20`, commit `9c2414d65909274ca6453f6b71da05cec3e67c41`.
- Staged manifests match Gate 0 hashes; headnode sweep found 4,540 total/unique paths, 0 missing, 0 empty.
- `source dyoainit` rc 0 and `dy-a slurm hg38` rc 0. `dy-a` emitted the existing cluster `gittag:null` warning, but the checkout tag and commit were independently verified.
- Exact-tag dry-run: `RETURN CODE: 0`, 1,181 jobs, 87 unique rules, 1-128 threads; all 10 units retained 150/438 raw ONT FASTQs for `[0,25)`.
- Live command launched without `-n` at `2026-07-16T18:41:30Z`; controller process `1415965` and tee process `1415721` remained present at the `2026-07-16T18:48:20Z` snapshot. The live `day_cmd.log` entry contains the exact command without `-n`.
- The controller progressed beyond pinned-environment creation and submitted owned Slurm jobs `1486` through `1526`. At the `18:48:20Z` snapshot, job `1486` was `RUNNING`; jobs `1487`-`1515`, `1519`, and `1525`-`1526` were `CONFIGURING`; and jobs `1510`, `1514`, `1516`-`1518`, and `1520`-`1524` were `PENDING`.
- The analysis lock remained owned by `codex-root-ifx-p2-second-half-11020-20260716` while the persistent controller ran.
- Attach handle: `tmux attach -t second_half_preval_11020_20260716` after connecting to the headnode as `ubuntu`.
- Dry-run output: `/fsx/analysis_results/ifx-p2-1000-120-0715/second-half-preval/daylily-omics-analysis/.ignore/hiomrs_kitchensink_11020_j300_T2_ont0_25_dryrun.out`; live output: `/fsx/analysis_results/ifx-p2-1000-120-0715/second-half-preval/daylily-omics-analysis/.ignore/hiomrs_kitchensink_11020_j300_T2_ont0_25_live.out`.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Gate 0 | Freeze tag, manifests, command, safety boundary, and dirty-tree ownership | SUCCESS | active_product_contract | Gate 0 | orchestrator | Baseline above |  | Local Gate 0 complete. |
| LIVEBASE-001 | Cluster | Refresh root absence, DRA/input visibility, FSx headroom, queue, tmux, controller, and lock state | SUCCESS | contract_test | Gate 1 | orchestrator | Live evidence above |  | Baseline passed before creating the new root. |
| DAY-001 | DayOA | Create and lock fresh `second-half-preval`, clone exact tag `11.0.20`, and stage byte-identical manifests | SUCCESS | active_product_contract | Gate 2 | orchestrator | Exact tag/commit, lock owner, manifest hashes, and 4,540-path sweep above |  | Exact clone and inputs are prepared. |
| DRY-001 | DayOA | Initialize exact clone and require the full kitchensink dry-run to return 0 | SUCCESS | contract_test | Gate 3 | orchestrator | Initialization rc values 0; dry-run `RETURN CODE: 0`, 1,181 jobs |  | Fresh exact-tag dry-run passed. |
| RUN-001 | DayOA/Slurm | Launch the identical live command without `-n` under the owned lock | SUCCESS | feature_implementation | Gate 4 | orchestrator | Live controller PID `1415965`; exact command has no `-n`; owned Slurm jobs `1486`-`1526` submitted |  | Live workflow launch achieved. |
| RUN-002 | Evidence | Prove persistent controller, initial Slurm queue, exact command log, tag/commit, and attach/log handles | SUCCESS | contract_test | Gate 5 | orchestrator | Tmux, controller, lock, `day_cmd.log`, queue snapshot, tag/commit, and output paths above |  | Launch evidence is complete and reproducible. |

## Final Report

All rows terminal: yes

Objective complete: yes; the requested exact-tag clone and live kitchensink launch are complete. The workflow itself remains live and has not reached terminal success.

Status counts:

- SUCCESS: 6
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 0
- OPEN: 0

Changed files:

- `daylily-ephemeral-cluster`: this ledger only.

Validation: exact-tag clone, manifest/path checks, initialization, dry-run rc 0, exact live command without `-n`, persistent controller, owned lock, and owned Slurm submissions are proven.

Non-success terminal rows: none.

Residual risks: the workflow is live, not terminal; downstream rule failures, node startup failures, or budget/runtime exhaustion remain possible. The analysis lock must remain owned while this controller is active and must not be released as part of launch handoff.
