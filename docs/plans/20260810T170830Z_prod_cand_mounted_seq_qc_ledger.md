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
| QC-005 | DYEC SSM transport | Prevent all DYEC Run Command call sites from submitting an oversized request. | SUCCESS | defect_repair | Gate 1 | Codex | `run_shell` now stages oversized shell payloads in SHA-256-verified bounded chunks; all direct Run Command submissions route through `start_bounded_command`. Focused SSM and Sentieon suites: 54 passed. A live ILMN catalog dry run reached terminal `SUCCEEDED` (controller PID `1966826`, exit 0, no Slurm jobs). | AWS rejected DYEC's generated inline Run Command document at its 97 KB limit (`MaxDocumentSizeExceeded`). | The former failure mode is prevented locally for shell and non-shell Run Command requests; no release has been published. |

## Amendment: 2026-08-10 SSM transport repair

The user directed that the repair be structural rather than a one-off catalog
workaround. All DYEC calls to `client.send_command` now flow through the
bounded transport gateway. Shell callers use automatic verified staging when
needed; non-shell document callers fail locally before an AWS 97 KB rejection.
The previously blocked launch rows remain historical evidence until their live
catalog launches are separately retried.

## Final report

All rows terminal: yes
Objective complete: no

Status counts:
- SUCCESS: 2
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 3
