# Majors HG003 1x Single Full-Depth HIOMRS Ledger

Created: `2026-07-19T12:32:50Z`

## Objective

Start a separate fresh HIOMRS kitchen-sink analysis on `majors-cluster` from
exact DayOA candidate commit `1818223c3dfc9fc9e8227db40a8fc29224406b4d`,
using exactly one HG003 analysis unit with the mounted ILMN 1x and ONT 1x inputs
at full input fractions. Do not include the duplicate full-depth unit or either
candidate downsample unit. Leave the existing four-unit workflow untouched.

## Gate 0 Baseline

- AWS profile `lsmc`, region `us-west-2`, cluster `majors-cluster`, remote user `ubuntu`.
- Existing workflow root `/fsx/analysis_results/majors-cluster/hg003-1x-hiomrs-1308cand-20260719T115732Z` remains live and locked by its controller; no cancel, edit, unlock, or takeover is authorized.
- Source fixture contains four units: `A1` and `A2` are duplicate full-depth attempts; `A3` and `A4` set both short- and long-read fractions to `0.90` and `0.75` respectively.
- This run selects only `HG003-SR1x-ONT1x-A1` with joins to `HG003-SR-1X-FASTQ` (`sr`, ordinal 1) and `HG003-LR-1X-FASTQ` (`lr`, ordinal 2). Its subsample fields are empty, meaning no additional downsampling of the mounted 1x inputs.
- Execution contract: fresh root, exact commit, separate named tmux, `source dyoainit`, `dy-a slurm hg38`, clean fail-fast `dy-r` dry-run, then identical live `dy-r` command.

## Control Ledger

| ID | Area | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|---|
| INV-001 | Baseline | Preserve existing workflow and verify the exact single-unit selection | SUCCESS | Live four-unit controller remains active; source manifest inspected directly | Selected only `HG003-SR1x-ONT1x-A1`; excluded A2/A3/A4. |
| ROOT-001 | Fresh root | Create a new root and exact detached candidate checkout | SUCCESS | `/fsx/analysis_results/majors-cluster/hg003-1x-full-hiomrs-1308cand-20260719T123250Z/daylily-omics-analysis`; detached HEAD `1818223c3dfc9fc9e8227db40a8fc29224406b4d` | Fresh bundle clone; no outputs reused. |
| LOCK-001 | Agent lock | Record write visit and acquire the new root lock without touching the existing root | IN_PROGRESS | Write visit recorded; lock owned by `codex-root-majors-hg003-1x-full-20260719` | Live controller retains the new-root lock. Existing root lock/controller unchanged. |
| INPUT-001 | Six manifests | Install and validate one specimen, sample, library, two sequencing inputs, one analysis unit, and two joins | SUCCESS | Validator rows `1/1/1/2/1/2`; analysis-unit SHA256 `90da7902...`; join SHA256 `2e277bfd...`; all invariants true | Only `HG003-SR1x-ONT1x-A1`; subsample columns empty; A2/A3/A4 absent. |
| DRY-001 | DAG | Run the exact kitchen-sink target/config set fail-fast with `-n` | SUCCESS | `RETURN CODE: 0`; 178 jobs; maximum 128 threads | No `-k`; identical target/config set reserved for live execution. |
| LIVE-001 | Execution | Launch the identical command live and capture controller/Slurm evidence | SUCCESS | Controller PID `1051411`; new-root Slurm jobs `305`, `306`, `307`, `309`, and `310` confirmed by `sacct WorkDir` | `306` and `307` completed; `305`, `309`, and `310` running at first receipt. |
| MON-001 | Monitoring | Confirm lock, controller, accounting, and initial progress without claiming completion | IN_PROGRESS | Tmux `majors-hg003-1x-full-hiomrs-1308cand-20260719`; controller active; new-root lock held | Analysis started but is not complete. Concurrent old-root jobs were separated using accounting `WorkDir`. |

## Final Report

All rows terminal: `no`

Objective complete: `no`
