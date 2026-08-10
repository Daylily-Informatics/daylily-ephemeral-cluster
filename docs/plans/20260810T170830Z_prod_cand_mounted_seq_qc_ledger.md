# prod-cand Mounted Sequencing QC Execution Ledger

Created: 2026-08-10T17:08:30Z
Scope: render, dry-run, then launch the exact current DYEC `illumina_run_qc`,
`ont_run_qc`, and `ultima_run_qc` catalog entries in parallel against the three
verified read-only run mounts. The Illumina entry excludes BCLConvert by its
catalog target. No mount, S3, FSx-output deletion, auto-export, Slurm service,
or scheduler intervention is authorized.

Controlling request: run all three mounted sequencing-QC catalog commands in
parallel, monitor every ten minutes, and report bugs that cause failures.

## Gate 0: inventory and baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` on
  `codex/pin-dayoa-13.4.10-16.1.45`; the large existing dirty/untracked
  worktree is user-owned and preserved.
- Target: `prod-cand-260809`, `UPDATE_COMPLETE`, `us-west-2`, profile `lsmc`.
- Explicit active Slurm cost center: `prod-cand-260809`, cap `$200`, approved
  2026-08-10; no August usage row exists. DayOA project: `RnD`.
- All three input mounts are `AVAILABLE` and headnode-verified:
  - ILMN `dra-0fd9d1dbc1b329805` at
    `/fsx/run_dir_mounts/bjuicepreval-20260618-ilmn/`.
  - ONT `dra-0c1ad269bb841a34e` at
    `/fsx/run_dir_mounts/bjuicepreval-20260615-ont-set4-fc1/`.
  - ULTIMA `dra-02af97c809a9fadd6` at
    `/fsx/run_dir_mounts/ultima-602202-20260512/`.
- Catalog contract: DayOA tag `13.4.13`, explicit run-context input, standard
  `ubuntu` interactive tmux controller, analysis lock, no export trigger, and
  no `--replace-existing-analysis` / reuse behavior.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| QC-001 | ILMN | Render/dry-run/launch `illumina_run_qc` only; no BCLConvert target. | BLOCKED | feature_implementation | Gate 1 | Codex | Exact `13.4.13` rendering selected only `produce_illumina_run_qc` with `run_context_only=true`; the dry launch failed before controller creation. | DYEC SSM Run Command payload exceeded AWS's 97 KB document limit on headnode `i-0ee0f65150b39b976`. | No DayOA, lock, tmux, or Slurm execution exists. Repair the bootstrap payload contract, then rerender and dry-run from a fresh analysis ID. |
| QC-002 | ONT | Render/dry-run/launch `ont_run_qc` for Set4-FC1. | BLOCKED | feature_implementation | Gate 1 | Codex | Exact `13.4.13` rendering selected `produce_ont_run_qc_and_demux_multiqc`; the dry launch failed before controller creation. | DYEC SSM Run Command payload exceeded AWS's 97 KB document limit on headnode `i-0ee0f65150b39b976`. | No DayOA, lock, tmux, or Slurm execution exists. Repair the bootstrap payload contract, then rerender and dry-run from a fresh analysis ID. |
| QC-003 | ULTIMA | Render/dry-run/launch `ultima_run_qc`. | BLOCKED | feature_implementation | Gate 1 | Codex | Exact `13.4.13` rendering selected `produce_ultima_run_qc` with `run_context_only=true`; the dry launch failed before controller creation. | DYEC SSM Run Command payload exceeded AWS's 97 KB document limit on headnode `i-0ee0f65150b39b976`. | No DayOA, lock, tmux, or Slurm execution exists. Repair the bootstrap payload contract, then rerender and dry-run from a fresh analysis ID. |
| QC-004 | Monitoring | Create the user-authorized 10-minute heartbeat and report terminal failures/bugs. | SUCCESS | legitimate_safety_handling | Gate 1 | Codex | User authorized monitoring; no heartbeat was created because every launch failed before a controller existed. The pre-controller failure was reported immediately. |  | No scheduled task is active in this thread. |
| QC-005 | DYEC SSM transport | Prevent all DYEC Run Command call sites from submitting an oversized request. | SUCCESS | defect_repair | Gate 1 | Codex | `run_shell` stages oversized shell payloads in SHA-256-verified bounded chunks; all direct Run Command submissions route through `start_bounded_command`. Focused SSM and Sentieon suites: 54 passed. A live ILMN catalog dry run reached terminal `SUCCEEDED` (controller PID `1966826`, exit 0, no Slurm jobs). | AWS rejected DYEC's generated inline Run Command document at its 97 KB limit (`MaxDocumentSizeExceeded`). | The repair is published in DYEC `16.1.66`. |
| QC-006 | Seq-QC retry | Launch all three catalog workflows from fresh analysis IDs with released DYEC `16.1.66` and explicit DayOA `13.4.14`. | SUCCESS | feature_implementation | Gate 1 | Codex | All three launched from fresh IDs and cloned DayOA commit `b70e57fbb6b4bed10b929beb2f0c51c12739b7f0` for tag `13.4.14`. Each controller subsequently reached a terminal failure that is recorded in QC-009. |  | The released DYEC transport repair allowed all requested controllers to launch. |
| QC-007 | Monitoring | Restore the previously user-authorized ten-minute launch monitor after controllers are created. | SUCCESS | legitimate_safety_handling | Gate 1 | Codex | Heartbeat `monitor-released-mounted-sequencing-qc-retries` was created at 10-minute cadence with terminal stop and six-hour runaway flag, then paused when all three controllers were terminal. |  | No scheduled task remains active. |
| QC-008 | Local DYEC resource cache | Diagnose and report the concurrent versioned-resource cache promotion race that initially blocked ONT. | BLOCKED | config_or_startup_contract | Gate 2 | Codex | Concurrent launch hit `[Errno 66] Directory not empty` while promoting `~/.config/daylily/resources/16.1.67.dev0+g926c309a4.d20260810`; serial ONT retry then launched successfully before creating a prior controller. | DYEC local resource-cache installation is not concurrency-safe. | The immediate run request is satisfied; a code fix and a further DYEC release require a new explicit request. |
| QC-009 | Workflow monitoring | Track the three live controllers through bootstrap and terminal workflow state. | ATTEMPTING_BUGFIX | config_or_startup_contract | Gate 1 | Codex | The three terminal failures are now being repaired under the user's explicit instruction. All controllers had entered `dy-a slurm hg38`; only ILMN reached Slurm. | ILMN used unsupported Lustre `RENAME_EXCHANGE`; ONT mixed incompatible run-context and manifest overrides; Ultima received an obsolete DYEC bootstrap that disrupted its native run-context mode. | Fresh analysis IDs and released code are required for the next execution attempt. |
| QC-010 | DayOA FSx publisher | Replace unsupported Lustre directory exchange while preserving rollback safety. | SUCCESS | defect_repair | Gate 1 | Codex | DayOA `13.4.16`, commit `b896ea7a093be83f2d46da876704375c09f468c8`, uses same-filesystem staged renames with rollback instead of `renameat2(RENAME_EXCHANGE)`; focused publisher/RunQC tests: 27 passed. Annotated tag and branch are pushed. | FSx Lustre returned `EINVAL` for `renameat2(RENAME_EXCHANGE)`. | The publisher will retain the old tree until the new staged tree reaches the canonical path, then remove the private previous sibling. |
| QC-011 | DYEC mounted RunQC contracts | Remove ONT manifest overrides and Ultima's obsolete metrics bootstrap; pin command catalog to DayOA `13.4.16`. | SUCCESS | defect_repair | Gate 1 | Codex | ONT now passes only `run_context_file` plus `run_context_only`; Ultima uses DayOA's native mounted-run JSON collection and no longer injects `run_qc`/metrics configuration. Source and packaged catalogs uniformly pin `13.4.16`; focused DYEC tests: 101 passed. | The catalog contradicted DayOA's explicit run-context contract and DYEC added an obsolete secondary Ultima contract. | DYEC release and fresh workflow proof remain in QC-012/QC-013. |
| QC-012 | Release activation | Publish a DYEC release containing QC-011 and activate the exact released CLI. | SUCCESS | feature_implementation | Gate 1 | Codex | Annotated DYEC `16.1.68` is pushed at `da2e1db057ce6541874e70c7235230d86eda8164`. After `source ./activate`, `dyec version`, package import, and `git describe --tags --exact-match HEAD` each returned `16.1.68`; focused DYEC suite: 112 passed. | `setuptools-scm` guess-next-dev treated a dirty exact-tag checkout as a post-tag development version. | Source version resolution now honors a valid exact tag at `HEAD`; the previous `16.1.67` tag remains unchanged. |
| QC-013 | Fresh live verification | Launch fresh ILMN, ONT, and Ultima catalog analyses and verify final report trees on FSx. | ATTEMPTING_BUGFIX | feature_implementation | Gate 1 | Codex | At DayOA `13.4.16`, ILMN and Ultima controllers exited `0`; their required FSx reports and MultiQC data are non-empty. ONT exited `1` after reaching Slurm: NanoPlot rejected `--tsv_stats`/`--info_in_report`, while PycoQC/ToulligQC containers lacked the spool helper's required host utilities/interpreter. No export trigger was configured. | ONT's container/runtime contract did not supply DYEC/DayOA's required local-spool commands, and its NanoPlot invocation targeted unsupported options. | Preserve the successful ILMN/Ultima roots; publish the ONT repair and retry only ONT from a fresh analysis ID. |
| QC-014 | DayOA ONT runtime repair | Publish a complete ONT RunQC environment and remove incompatible tool invocations. | SUCCESS | defect_repair | Gate 1 | Codex | DayOA `13.4.18`, commit `723784373852c056a69d7bb2f08b026ad9df20f7`, adds immutable `ont_run_qc_reports_v0.3.yaml` with PycoQC and ToulligQC, executes those rules under the shared Conda environment, removes unsupported NanoPlot options from workflow and helper scripts, and sets ToulligQC's NumExpr ceiling to the allocated threads. Focused tests: 90 passed. | The prior split-container model omitted DayOA spool dependencies and NanoPlot options were incompatible with the pinned installed tool. | Tag and branch are pushed; DYEC must now pin the exact tag. |
| QC-015 | DYEC ONT repair release | Pin source and packaged catalog defaults to DayOA `13.4.18`, advance the DYEC self pin, then publish and activate the release. | SUCCESS | feature_implementation | Gate 1 | Codex | Annotated DYEC `16.1.69`, commit `a89316aba7b63190b48b08bc2d3d365a30421e19`, was pushed and exact activation showed `16.1.69`; source/payload config files were byte-identical and focused DYEC suite passed 144. |  | The fresh retry outcome is recorded in QC-016. |
| QC-016 | ONT fresh live verification | Launch one fresh ONT catalog analysis at the repaired DayOA/DYEC tags and verify its final FSx report tree. | ATTEMPTING_BUGFIX | feature_implementation | Gate 1 | Codex | Fresh root `prod-cand-ont-seqqc-16169-r1` cloned exact DayOA `13.4.18`, then exited `1` before Slurm submission at 2026-08-10T20:03:25Z. | The combined `ont_run_qc_reports_v0.3.yaml` is unsatisfiable: PycoQC `2.5.2` requires Plotly `4.1`, while ToulligQC `2.9.1` requires Plotly `>=5.15,<6`. | Preserve this failure root; repair the incompatible environment routing and retry only from a new ONT analysis ID. |
| QC-017 | DayOA ONT Conda-solve repair | Route PycoQC, generic ONT utilities, and ToulligQC to their existing separate immutable environments. | SUCCESS | defect_repair | Gate 1 | Codex | DayOA `13.4.20`, commit `a09cf8578a9987247b47439d48b53d3b6d2c31b4`, routes PycoQC to `ont_run_qc_reports_v0.1.yaml`, generic tools to `v0.2`, and ToulligQC to `ont_toulligqc_v0.1.yaml`; no versioned YAML was edited. Focused suite: 90 passed. | The v0.3 combined environment violated mutually exclusive package constraints. | Tag and branch are pushed; advance DYEC's exact DayOA pin. |
| QC-018 | DYEC ONT Conda-solve repair release | Pin source and packaged catalog defaults to DayOA `13.4.20`, advance DYEC self pin, and publish the release. | IN_PROGRESS | feature_implementation | Gate 1 | Codex | Active catalog/test pin edits are staged locally; source/payload catalog parity and focused DYEC tests remain required. |  | Publish an annotated DYEC `16.1.70` and prove the activated CLI identity before retry. |
| QC-019 | ONT final fresh live verification | Launch one fresh ONT catalog analysis at the repaired DayOA/DYEC tags and verify the complete final FSx report tree. | IN_PROGRESS | feature_implementation | Gate 1 | Codex | User authorized continued debugging until final FSx reports succeed; all older ONT roots are retained as evidence and will not be reused. |  | Wait for QC-018, launch one new ONT-only ID, and restore the authorized terminal monitor. |

## Amendment: 2026-08-10 SSM transport repair

The user directed that the repair be structural rather than a one-off catalog
workaround. All DYEC calls to `client.send_command` now flow through the
bounded transport gateway. Shell callers use automatic verified staging when
needed; non-shell document callers fail locally before an AWS 97 KB rejection.
The previously blocked launch rows remain historical evidence until their live
catalog launches are separately retried.

## Amendment: released retry

The earlier defect repair is now released as DYEC `16.1.66`. The user directed
a live retry, so the new launch row pins DayOA `13.4.14` explicitly and uses
fresh analysis IDs rather than reusing the failed pre-controller attempts.

## Amendment: 2026-08-10 released retry terminal outcomes and repair

The DayOA controllers explicitly requested the `slurm` profile and set genome
build `hg38`; their controller logs show the resulting Slurm rule-profile file
in every analysis root. This is direct evidence of the requested execution
environment, not merely catalog metadata. Only Illumina reached a Slurm rule.

No workflow data were deleted, exported, retried, or cancelled during the
failed attempt. The previously authorized ten-minute heartbeat remains paused;
any subsequent monitor will be created only for fresh live controllers and will
stop at their terminal states.

## Final report

All rows terminal: no
Objective complete: no

Status counts:
- SUCCESS: 6
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 4
- ATTEMPTING_BUGFIX: 1
- IN_PROGRESS: 2
