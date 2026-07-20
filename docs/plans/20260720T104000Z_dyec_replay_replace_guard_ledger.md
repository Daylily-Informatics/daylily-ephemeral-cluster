# DAY-EC Replay Replace Guard Ledger

## Objective

Fix the generated headnode SSM launch script so an explicit
`--replace-existing-analysis-dir` replay is evaluated deterministically under
`set -u`, release the fix from the current maximum DAY-EC version, and provide
an immutable pin for Ursa.

## Safety Boundary

- This change and its tests do not delete, move, or rename any live analysis
  directory.
- No AWS, headnode, cluster, Slurm, DayOA workflow, Bloom, Dewey, or Ursa
  production mutation is part of the DAY-EC source change.
- Live replay of the three existing Ursa analyses remains separately gated
  because the approved replace mode would remove their exact failed FSx
  analysis directories before cloning a clean DayOA checkout.
- No fallback path, alternate analysis ID, inferred execution owner, or resume
  behavior is introduced.

## Gate 0

| Item | Evidence | Status |
|---|---|---|
| Remote maximum numeric tag | `13.0.1` | VERIFIED |
| Annotated tag object | `93a154c406b674565225381f52ed7142827674c7` | VERIFIED |
| Peeled source commit | `384a9dc1394a87bf0602ac66567f5a964268c752` | VERIFIED |
| Isolated checkout | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-13.0.2-replay-fix` | VERIFIED |
| Branch | `codex/dyec-replay-replace-guard-20260720` | VERIFIED |
| Live failure | Three Ursa replays failed in generated SSM scripts with `REPLACE_EXISTING_ANALYSIS_DIR: unbound variable` before DayOA launch | VERIFIED |
| Current source defect | The flag assignment exists only in the inner controller payload, while the outer launcher checks it first | VERIFIED |

## Execution Ledger

| ID | Requirement | Status | Evidence / Terminal Note |
|---|---|---|---|
| DYEC-001 | Define `REPLACE_EXISTING_ANALYSIS_DIR` in the outer generated script before its existing-directory guard | SUCCESS | One explicit rendered assignment was added before the first outer guard read; the independent inner-controller assignment remains unchanged. |
| DYEC-002 | Preserve fail-closed behavior when replacement is not explicitly requested | SUCCESS | The default render contains `REPLACE_EXISTING_ANALYSIS_DIR=false` before the guard. |
| DYEC-003 | Prove explicit replacement renders before the first variable read | SUCCESS | A second renderer invocation with `--replace-existing-analysis-dir` asserts `true` precedes the guard. |
| DYEC-004 | Run focused and complete DAY-EC validation | SUCCESS | Focused suites: `53 passed`; complete suite: `2229 passed, 11 skipped, 1 unrelated baseline failure`. Changed-file Ruff and `git diff --check` pass. |
| DYEC-005 | Merge through PR checks and publish annotated `13.0.2` | OPEN | Pending. |
| URSA-001 | Update Ursa to immutable DAY-EC `13.0.2`, test, release, and deploy only Ursa | OPEN | Tracked in the Ursa acceptance ledger. |
| LIVE-001 | Replay existing ILMN, ONT, and Ultima analyses | BLOCKED | Requires separate destructive approval for the three exact failed FSx directories. |

## Completion Criteria

The source objective is complete only when the fixed DAY-EC version is tagged,
Ursa is deployed with that exact immutable dependency, production provenance is
verified, and no live replay or directory replacement has occurred without its
separate approval.

## Validation Baseline

The complete tagged-source suite has one unrelated failure in
`tests/test_dayoa12_manifest_contract.py`: the `13.0.1` command catalog pins
DayOA `13.0.14`, while the stale test asserts `13.0.12`. The replay-focused test
and all other 2,229 tests pass. Repository-wide Ruff reports 34 pre-existing
findings under historical documentation and plan scripts. The two changed
Python files pass Ruff, and no unrelated source or test baseline was modified.
