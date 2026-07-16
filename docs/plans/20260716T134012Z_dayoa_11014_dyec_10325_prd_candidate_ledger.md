# DayOA 11.0.14 / DYEC 10.3.25 Production-Candidate Ledger

## Objective

Publish clean `prd-candidate` branches for DayOA and DYEC, pin DYEC's active
source and packaged command catalogs to the annotated DayOA `11.0.14` release,
then advance both DYEC self-pins in a separate commit and publish annotated DYEC
tag `10.3.25` without merging the DYEC candidate branch to `main`.

## Gate 0

- DayOA canonical checkout: clean `main` at `04e584b65c74ad9d310e6d8189d9051e0bdd005d`.
- DayOA annotated tag `11.0.14` peels to that same commit.
- DayOA remote `prd-candidate` did not exist and was created without force at `04e584b`.
- DYEC canonical checkout: clean `main` at `247a55460b3c16938e335e444bbc0da349fff8a0`.
- DYEC remote `prd-candidate` and tag `10.3.25` did not exist.
- Historical ledgers and archived catalog snapshots are excluded from mechanical version replacement.

## Control ledger

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| PC-001 | Publish DayOA `prd-candidate` at the clean `11.0.14` release | COMPLETE | Remote branch and annotated tag both peel to `04e584b`. |
| PC-002 | Pin active source/package DayOA defaults and HIOMRS catalog commands to `11.0.14` | COMPLETE | Source/package catalogs, current README contract, and regression expectations match; focused pin/parity suite passed (`56 passed`). |
| PC-003 | Commit and push DayOA-pin change as the first DYEC candidate commit | COMPLETE | Commit `43f283c8` is pushed on `origin/prd-candidate`. |
| PC-004 | Advance source/package DYEC self-pins to `10.3.25` in a second commit | COMPLETE | Both global-config copies and the fork regression contract target `10.3.25`. |
| PC-005 | Validate, push DYEC `prd-candidate`, and publish annotated `10.3.25` | COMPLETE | Focused and complete suites pass; final annotated tag `10.3.25` is published from the clean second commit. |

## Terminal result

All control-ledger rows are terminal. The production-candidate objective is
complete when the second commit and annotated `10.3.25` tag are visible on the
remote; no merge to `main` is part of this request.

## Safety boundary

- No branch or tag may be force-updated or moved.
- No historical plan, archived catalog snapshot, live analysis root, Slurm job,
  or headnode DayOA checkout is modified by this release train.
- The local TIDDIT 3.9.5 migration is released in DayOA `11.0.14` but is not
  installed or executed on the active headnode.
