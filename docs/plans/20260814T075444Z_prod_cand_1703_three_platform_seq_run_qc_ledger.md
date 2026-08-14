# prod-cand-1703 three-platform sequencing-directory QC execution ledger

Created: 2026-08-14T07:54:44Z

Controlling request: use the activated DYEC 17.0.14 CLI to run the production
command-catalog sequencing-run QC commands for ILMN without BCL Convert, ONT,
and Ultima in parallel on `prod-cand-1703`, region `us-west-2`, profile `lsmc`,
using the existing mounted sequencing directories; start and monitor the
commands on the cluster.

Explicit execution boundary: use catalog render/launch and workflow/headnode
monitoring only. Do not create, detach, or delete DRAs; do not export or delete
workflow results; do not mutate budgets or cost centers; do not cancel,
requeue, reprioritize, or otherwise administer Slurm jobs.

## Gate 0: inventory and baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, detached
  clean tracked tree at annotated tag `17.0.14`, commit
  `96cec5a45993e706e8e075853ac0f5fe27b812ac`. There are 105 pre-existing
  untracked paths owned by other workstreams; this ledger and its context TSVs
  are the only task-owned local writes.
- Activated CLI: `Daylily Ephemeral Cluster 17.0.14`. The headnode reports the
  same version. `day-clone --check-auth` validates
  `daylily-omics-analysis @ 14.0.14` without exposing credentials.
- Cluster: `prod-cand-1703`, `us-west-2`, profile `lsmc`, ParallelCluster state
  `UPDATE_COMPLETE`, compute fleet `RUNNING`, headnode
  `i-0a19cb6b471874d56` (`10.0.0.22`, Ubuntu remote user `ubuntu`).
- Initial occupancy at 2026-08-14T07:52:27Z: zero live DayOA controllers, zero
  receipted or unreceipted controllers, zero Slurm jobs, and 16 idle/stale tmux
  panes from prior workstreams. Those sessions are outside this task and will
  not be modified.
- Project: `prod-cand-1703`, from the live cluster project tag. Cost center:
  `prod-cand-1703-ccenter`, active, allowed user `ubuntu`, monthly cap `$999`,
  with no 2026-08 usage snapshot. No budget or cost-center mutation is
  authorized or required; launches use strict project checks and must fail
  closed if enforcement rejects them.
- The dry-controller project check reports the live AWS project budget as
  `$999` total and `$109.963` used (`11.01%`); no enforcement bypass or budget
  change was performed.
- Existing read-only run DRAs are all `AVAILABLE`, projected locally, and
  verified usable through DYEC:
  - ILMN `dra-0b789d77240836540`, mount
    `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3/`; `RunInfo.xml` and
    `SampleSheet.csv` are present.
  - ONT `dra-0281455160baf94c5`, parent mount
    `/fsx/run_dir_mounts/pca100-2026/`; selected previously reviewed directory
    `/fsx/run_dir_mounts/pca100-2026/20260615_ONT_Set4-FC1/`; `OOW.done` is
    present.
  - Ultima `dra-03fc65aedcaa4ff1c`, mount
    `/fsx/run_dir_mounts/ultima-604834-20260717/`;
    `604834_LibraryInfo.xml` is present.
- Immutable catalog snapshot: DYEC `17.0.14`, catalog schema version 6, exact
  DayOA tag/validated version `14.0.14` for all three commands:
  - `illumina_run_qc` targets only `produce_illumina_run_qc`. The separate
    `illumina_run_qc_bclconvert` command is excluded and will not be rendered or
    launched.
  - `ont_run_qc` targets `produce_ont_run_qc_and_demux_multiqc`; it performs
    mounted run-folder and demultiplexed FASTQ QC, not basecalling.
  - `ultima_run_qc` targets `produce_ultima_run_qc`.
- Launch contract: first render and launch three distinct dry roots in parallel.
  Each must exit `0` with zero Slurm submissions and a correct rendered plan.
  Then render and launch three fresh live roots in parallel, retaining catalog-
  owned analysis locks until terminal controller state. All launches use
  `--executing-entity prod-cand-1703`, `--remote-user ubuntu`,
  `--project prod-cand-1703`, `--cost-center prod-cand-1703-ccenter`,
  `--strict-project-check`, and `--export-trigger none`.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| BASE-001 | Gate 0 | Freeze repo, CLI, cluster, occupancy, mounts, catalog pins, project, cost center, and task boundary before launch. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Live DYEC/headnode/mount/catalog/cost-center evidence summarized above; three exact context TSVs created. |  | Gate 0 recorded before any workflow write. |
| DRY-ILMN | Catalog dry launch | Render and launch `illumina_run_qc` against the existing ILMN mount, with no BCL Convert target. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Root/session `pc1703-ilmn-seqqc-17014-dry-20260814`; rendered target only `produce_illumina_run_qc`; attributed controller exit `0`; submitted and finished Slurm counts both `0`. |  | Correct catalog dry plan completed without compute submission. |
| DRY-ONT | Catalog dry launch | Render and launch `ont_run_qc` against ONT Set4-FC1, with no basecalling. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Root/session `pc1703-ont-set4fc1-seqqc-17014-dry-20260814`; exact `14.0.14` checkout and strict project check succeeded; attributed controller exit `0`; submitted and finished Slurm counts both `0`. |  | Correct catalog dry plan completed without compute submission. |
| DRY-ULT | Catalog dry launch | Render and launch `ultima_run_qc` against the existing Ultima mount. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Root/session `pc1703-ultima-604834-seqqc-17014-dry-20260814`; rendered target only `produce_ultima_run_qc`; attributed controller exit `0`; submitted and finished Slurm counts both `0`. |  | Correct catalog dry plan completed without compute submission. |
| LIVE-ILMN | Catalog live launch | Launch and monitor the fresh ILMN QC controller to terminal state. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Root/session `pc1703-ilmn-seqqc-17014-20260814`; five submitted jobs `661`-`665`; terminal `SUCCEEDED` with attributed exit `0`. Read visit verified the root is unlocked and contains `summary.html`, `summary.tsv`, `illumina_run_qc.json`, `multiqc_report.html`, and `multiqc_report_data/`. |  | Catalog target was only `produce_illumina_run_qc`; no BCL Convert command or target was launched. |
| LIVE-ONT | Catalog live launch | Launch and monitor the fresh ONT QC controller to terminal state. | BLOCKED | feature_implementation | Gate 1 | orchestrator | Root/session `pc1703-ont-set4fc1-seqqc-17014-20260814`; terminal `FAILED` with attributed exit `1`. Jobs `666`, `667`, `675`, `676`, and `677` finished, reaching 5/10 steps. Snakemake automatically retried demux FASTQ QC (`673` then `678`) and NanoPlot (`674` then `679`); both retry attempts failed. Read visit verified the root is unlocked. Partial outputs include `summary.html`, `summary.tsv`, pycoQC HTML/JSON, and ToulligQC HTML/data, but final ONT MultiQC is absent. | `workflow/envs/ont_run_qc_reports_v0.4.yaml` leaves `nanoplot` and Matplotlib unpinned. The generated immutable environment resolved NanoPlot `1.30.1` with Matplotlib `3.11.1`; both failing rules crash in `nanoplotter.check_valid_colormap` because Matplotlib 3.11 no longer exposes `matplotlib.cm.cmap_d`. | A corrected new versioned DayOA environment YAML, updated explicit rule reference/tests, a validated DayOA release, catalog pin update, and a fresh-root rerun require a separate code/release execution scope. No manual retry or fallback was attempted. |
| LIVE-ULT | Catalog live launch | Launch and monitor the fresh Ultima QC controller to terminal state. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Root/session `pc1703-ultima-604834-seqqc-17014-20260814`; four submitted jobs `657`-`660`; terminal `SUCCEEDED` with attributed exit `0`. Read visit verified the root is unlocked and contains `summary.html`, `summary.tsv`, `tables/ultima_run_metrics.json`, `ultima_native.multiqc.html`, and `ultima_native.multiqc_data/`. |  | Catalog execution completed normally. |
| MON-001 | Monitoring | Monitor controller, tmux, lock, Slurm, exit code, and final platform QC artifacts without job or service intervention. | SUCCESS | legitimate_safety_handling | Gate 5 | orchestrator | All three controllers reached attributed terminal states and all three roots are unlocked. ILMN and Ultima final platform artifacts were verified; ONT partial artifacts and exact terminal failure evidence were verified. `analysis_artifacts.tsv` and `artifact_lineage.tsv` exist in every root. Monitoring was read-only apart from required visit receipts; no Slurm, DRA, budget, export, or controller intervention occurred. |  | Monitoring and evidence collection are complete. |

## Final report

All rows terminal: yes

Objective complete: no

Gate 0 and all three dry catalog launches completed successfully. All three
fresh live catalog controllers were started in parallel. ILMN and Ultima
completed successfully with final artifacts; ONT reached a terminal,
attributed environment-compatibility failure after its built-in retries and is
blocked pending a new versioned DayOA environment/release plus a fresh-root
rerun. The requested three-command objective is therefore not complete.
