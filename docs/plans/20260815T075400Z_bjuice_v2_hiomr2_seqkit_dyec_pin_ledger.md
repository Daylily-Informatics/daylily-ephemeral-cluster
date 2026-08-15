# Bjuice v2 HIOMR2 `seqkit` DYEC pin ledger

## Release path

- DayOA `15.0.3` is the prerequisite immutable environment release. It adds
  `seqkit=2.13.0` in `hiomr2_v0.4.yaml` after the `10x5` SR-preparation log
  showed `seqkit: command not found` and zero BWA reads.
- DYEC `18.0.8` must pin only the explicit Bjuice v2 full-preval multi-AU
  command to `15.0.3`; generic DayOA commands retain their existing pins.
- Source and packaged catalogs must remain byte-identical. The `18.0.7`
  snapshot remains immutable; a new `18.0.8` snapshot records the repaired
  eligibility contract.

## Terminal gates

| Gate | State | Evidence |
| --- | --- | --- |
| DayOA release | complete | Annotated `15.0.3` published from merged DayOA PR #113. |
| DYEC catalog pin | complete | Explicit command/current snapshot select `15.0.3`; `18.0.8` snapshot added. |
| DYEC focused validation | pending | Catalog and fork-contract tests, plus source/payload parity. |
| DYEC release | pending | Commit, PR, merge, annotated `18.0.8`, and release. |
| Relaunch | pending | Fresh-root dry launch then live launch through the new exact catalog release. |
