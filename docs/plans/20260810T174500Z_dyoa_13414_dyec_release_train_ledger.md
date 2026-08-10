# DayOA 13.4.14 / DYEC release train ledger

Created: 2026-08-10T17:45:00Z
Controlling request: update every DYEC-pinned DayOA reference to `13.4.14`,
commit and push the dirty DYEC work, tag a new DYEC version, then update the
DYEC self-pin and publish a second annotated DYEC tag.

## Gate 0: inventory and baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch
  `codex/pin-dayoa-13.4.10-16.1.45`, tracking the matching origin branch.
- Existing latest DYEC tags: `16.1.63` (DayOA-pin) and `16.1.64` (self-pin).
  This train therefore reserves `16.1.65` then `16.1.66`.
- DayOA `13.4.14` exists remotely as an annotated tag; peeled commit
  `b70e57fbb6b4bed10b929beb2f0c51c12739b7f0`.
- Pre-existing dirty tracked files are `AGENTS.md`, the SSM transport repair,
  and its focused test. There are 254 candidate untracked DYEC paths outside
  clearly unrelated local paths. Two older untracked log files alone are
  62 MiB and 84 MiB, so they cannot be pushed to GitHub unchanged.
- Explicit scope: include DYEC source, tests, configuration, and durable
  DYEC plans/evidence that can be committed and pushed. Exclude the unrelated
  nested `TrusSV` Git repository, backups, recordings, temporary files,
  reports, and any individual files at or above GitHub's 100 MiB object limit.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | Catalog pin | Set every current DYEC DayOA reference and matching test contract to `13.4.14`, in source and packaged catalog. | SUCCESS | config_or_startup_contract | Gate 2 | Codex | Source and packaged catalogs are byte-identical after the literal replacement; `13.4.14` resolves to DayOA commit `b70e57fbb6b4bed10b929beb2f0c51c12739b7f0`; focused validation passed `360`. |  | Every active DYEC DayOA command/catalog pin now uses the requested release. |
| REL-002 | DYEC release | Commit the dirty scoped DYEC work, push branch/PR/merge, then create and push annotated `16.1.65`. | SUCCESS | feature_implementation | Gate 5 | Codex | Commit `63ae01a5` was pushed, PR `#90` merged to `origin/main` commit `d4d9c02591cbffbd2f7307aadca9641019eb8583`, and remote annotated tag `16.1.65` peels to that commit. |  | First DYEC release is published. |
| REL-003 | Self pin | Update source and packaged DYEC self-pins to the released `16.1.65`, test, then publish annotated `16.1.66`. | SUCCESS | config_or_startup_contract | Gate 2 | Codex | Source and packaged configs are byte-identical at `16.1.65`; `471` focused packaging, clone, init, workflow, CLI, and fork-contract tests passed. |  | The self-pin content is complete; final publication verification is tracked by REL-004. |
| REL-004 | Release proof | Verify remote branch, both annotated tag objects, peeled commits, and clean final tree. | OPEN | contract_test | Gate 5 | Codex | Pending release actions. |  |  |

## Final report

All rows terminal: no
Objective complete: no

Status counts:
- SUCCESS: 3
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- OPEN: 1
