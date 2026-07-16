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
| PC-003 | Commit and push DayOA-pin change as the first DYEC candidate commit | READY | Validated candidate is ready to commit and push before the self-pin commit. |
| PC-004 | Advance source/package DYEC self-pins to `10.3.25` in a second commit | PENDING | `config/daylily_cli_global.yaml` and packaged copy plus fork regression contract. |
| PC-005 | Validate, push DYEC `prd-candidate`, and publish annotated `10.3.25` | PENDING | Tag must be new, annotated, and peel to the clean second commit. |

## Safety boundary

- No branch or tag may be force-updated or moved.
- No historical plan, archived catalog snapshot, live analysis root, Slurm job,
  or headnode DayOA checkout is modified by this release train.
- The local TIDDIT 3.9.5 migration is released in DayOA `11.0.14` but is not
  installed or executed on the active headnode.
