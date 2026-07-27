# Pre-validation single-chip ONT RunQC ledger

Created: 2026-07-26T22:54:00Z
Scope: Run DayOA ONT sequencing QC for exactly one mounted Bjuice chip,
`20260615_ONT_Set4-FC1`, on the non-Ursa `preval-hiomr2` cluster. Generate and
inspect both the main ONT MultiQC report and the demultiplexed-FASTQ MultiQC
report. Do not alter the read-only mount, run BCL Convert, manage Slurm, or
touch the separate Ursa-managed ONT acceptance run.

Controlling mount ledger:
`docs/plans/20260726T035509Z_bjuice_preval20_hiomr2_mounts_ledger.md`
Ledger path:
`docs/plans/20260726T225400Z_preval_ont_set4_fc1_run_qc_ledger.md`

## Gate 0: inventory and baseline

- DYEC repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`,
  branch `jem-candidate-260725`, with extensive pre-existing modified and
  untracked work. This ledger is the only local record owned by this task.
- Live cluster: `preval-hiomr2` in `us-west-2`, profile `lsmc`; status
  `UPDATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-0b70541bdad454c76`
  is running.
- Live source mount: DRA `dra-07571825f38c091e3`, mounted read-only as
  `/fsx/run_dir_mounts/pca100-2026/`; lifecycle `AVAILABLE`.
- Selected chip: `/fsx/run_dir_mounts/pca100-2026/20260615_ONT_Set4-FC1/`.
  A read-only headnode probe confirmed the directory, one
  `sequencing_summary*.txt`, 944 compressed FASTQs, 47 demux FASTQ groups, and
  approximately 19 GiB of data.
- Supported catalog command: `ont_run_qc`, which invokes
  `produce_ont_run_qc`. At the pinned catalog tag this target has both the
  main ONT report and the demux-FASTQ MultiQC report as required inputs. It
  uses the explicit `runs.tsv` row at
  `docs/plans/20260726T225400Z_preval_ont_set4_fc1_runs.tsv` whose `RUN_DIR`
  is the selected chip directory; this prevents the target from scanning the
  other fourteen mounted flow cells.
- Acceptance reference:
  `/Users/jmajor/Downloads/ont_run_qc/ont_runs.multiqc.html`. Its module
  anchors establish the expected main-report section identity: General
  Statistics, NanoStat, and pycoQC. The demux report is a separate report
  expected to include NanoStat, SeqKit, and Nanoq instead.
- Live limits: create a fresh explicit analysis root only after the rendered
  DYEC dry-run and analysis-root lock checks pass. No AWS, source-mount, Slurm,
  job, or service intervention is authorized.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| INV-001 | DYEC / source inventory | Confirm the cluster, current read-only DRA, exact chip directory, source contents, and the supported RunQC command contract. | SUCCESS | legitimate_safety_handling | Gate 0 | Codex | `dyec mounts list` confirms `pca100-2026` AVAILABLE; headnode read probe confirms Set4-FC1, 1 summary, 944 FASTQs, 47 groups, 19 GiB; `dyec workflow launch` renders `DAY_CONTAINERIZED=true dy-r produce_ont_run_qc`. |  | Exact one-chip source and supported `dy-r` contract established. |
| CFG-002 | DayOA run context | Create and validate the explicit one-chip `runs.tsv` input and pinned DayOA/DYEC launch rendering. | SUCCESS | feature_implementation | Gate 1 | Codex | Fresh root `preval_ont_set4_fc1_runqc_dryrun2_20260726T231000Z` completed `dy-r -n` with return code 0 using the run-context-only contract. | Historical catalog extras supplied legacy `units_table` and were removed for the corrected run-context invocation. | Validated target graph has 9 tasks; no source-mount fallback or legacy manifest table is used. |
| RUN-003 | DayOA launch preparation | Create a fresh analysis root, record a write visit, and acquire the required lock before writing. | IN_PROGRESS | legitimate_safety_handling | Gate 1 | Codex | Successful dry run verifies root construction, `ubuntu` one-pane tmux, and lock lifecycle. Fresh live-root absence/cost-center check pending. |  |  |
| RUN-004 | DayOA execution | Run the supported ONT RunQC plus demux MultiQC target from a persistent interactive `ubuntu` bash-login tmux session. | OPEN | feature_implementation | Gate 1 | Codex | Pending launch evidence. |  |  |
| QA-005 | MultiQC acceptance | Compare generated report and `multiqc_data` module/section identities with the attached reference. | OPEN | contract_test | Gate 5 | Codex | Pending generated report. |  |  |
| EVD-006 | Durable evidence | Record exact command, run/output paths, report comparison, and terminal outcome in this ledger. | OPEN | feature_implementation | Gate 5 | Codex | Pending completion evidence. |  |  |
| TOS-007 | Headnode Conda policy | Establish and record the Ubuntu-scoped automatic ToS policy for the current headnode. | SUCCESS | config_or_startup_contract | Gate 2 | Codex | Headnode Conda 25.7.0 shows `/home/ubuntu/.condarc` with `plugins.auto_accept_tos: True`; current defaults-channel acceptance also exists from the earlier approved attempt. | Previous policy was false; the manual NVMe probe therefore stopped before dependency solving. | Per subsequent user direction, no future Conda command may run as root or through `sudo`; Ubuntu-scoped policy is sufficient. |
| TOS-008 | DYEC bootstrap | Make local `activate`, Miniconda installation, and supported headnode configuration establish an Ubuntu/user-scoped Conda auto-ToS policy for future use. | SUCCESS | config_or_startup_contract | Gate 2 | Codex | `activate`, `bin/install_miniconda`, and its payload mirror configure `plugins.auto_accept_tos` without `--system`; `configure_headnode` uses Ubuntu `conda tos accept --user` for `pkgs/main` and `pkgs/r`. `pytest -q tests/test_install_miniconda.py tests/test_workflow.py::TestConfigureHeadnode` -> 30 passed; shell syntax and diff checks pass. |  | No DYEC Conda command uses root or `sudo`; future headnode configuration is Ubuntu-scoped. |

## Execution updates

- 2026-07-26T23:08Z: `dyec workflow launch --dry-run` created the named
  one-pane `ubuntu` tmux session and used the supported `dy-r` path. The first
  dry run failed with `WorkflowError` before formal Snakemake execution because
  the catalog's historical `samples_table` / `units_table` arguments are now
  explicitly rejected by the DayOA 13.0.41 run-context contract. No Slurm job
  was submitted; the failed root and tmux session remain preserved for audit.
- 2026-07-26T23:05Z: corrected dry run
  `preval_ont_set4_fc1_runqc_dryrun2_20260726T231000Z` returned 0 with the
  exact one-chip `runs.tsv`, one-pane tmux, an acquired/released analysis lock,
  and no Slurm job submission. Its graph contains 9 tasks. The profile renders
  a 240-minute time value for the ONT QC and demux rules. Main MultiQC is
  configured for `pycoqc` and `nanostat`; demux MultiQC is configured for
  `nanostat`, `seqkit`, and `nanoq`.
- 2026-07-27T02:41Z: before the fresh retry, a manual compute-NVMe Conda
  probe exposed a noninteractive ToS block rather than a solver failure.
  `plugins.auto_accept_tos` was false on the headnode. With the user's explicit
  approval, the policy was initially made global to the headnode Conda installation
  and the active Anaconda defaults-channel terms were accepted into `/etc/conda/tos`.
  Subsequent user direction supersedes that future behavior: DYEC will configure
  and accept ToS only as `ubuntu`, with no root or `sudo` Conda invocation.
- 2026-07-27T02:52Z: implemented the Ubuntu/user-scoped DYEC bootstrap policy.
  Local `activate` and the Miniconda installer set `plugins.auto_accept_tos`
  in the invoking user's Conda configuration; supported headnode configuration
  sets the same preference and accepts the two current defaults-channel terms
  with `conda tos accept --user`. Focused validation returned 30 passed.
