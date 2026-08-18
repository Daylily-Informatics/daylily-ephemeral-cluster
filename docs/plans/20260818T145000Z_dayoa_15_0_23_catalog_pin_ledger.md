# DayOA 15.0.23 catalog-pin release ledger

## Scope

Advance the active DYEC catalog and its immutable `18.0.41` snapshot from
DayOA `15.0.22` to `15.0.23`, then force-configure `pre-rel-18025` using its
managed GitHub-token reference before the requested catalog launches.

## Gate 0

- DYEC baseline: annotated `18.0.40` (`e18a64b1`).
- DayOA baseline: annotated `15.0.22` (`e838b3ae`).
- Live proof before promotion: the explicitly authorized pinned-source dry
  run in the existing Bjuice analysis root completed controller/day_run/
  Snakemake `rc=0` after the exact two source fixes now tagged DayOA `15.0.23`
  (`33624a81`).
- Exclusions: no local test suite, Git test suite, S3 export, FSx cleanup, or
  Slurm action is part of this release.

| ID | Work | Status | Evidence |
|---|---|---|---|
| G0-001 | Record source baseline and live proof. | COMPLETE | Gate 0 above. |
| CFG-001 | Update active repository/current catalog pins and add immutable `18.0.41` snapshot. | COMPLETE | All active command tags and DayOA default ref are `15.0.23`; `18.0.39` remains immutable at `15.0.22`. |
| REL-001 | Commit, push, annotate, and push DYEC `18.0.41`. | COMPLETE | Release commit contains this final ledger; annotated tag points at that commit. |
| NODE-001 | Force-configure `pre-rel-18025` using its managed Git token and verify both release versions. | OPEN | |
| LIVE-001 | Relaunch the four requested catalog dry runs through DYEC. | OPEN | |
