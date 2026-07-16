# Cluster-Gated DayOA/DYEC Release Ledger

Created: 2026-07-08T11:54:00Z

## Objective

Wait until the currently building Intel and RHEL/DRAGEN cluster creation attempts complete successfully, then run the requested DayOA and DYEC release chain on the `lsmc-bio` `jem-dev` branches.

## Gate 0 Inventory

| Item | State |
| --- | --- |
| DYEC working tree | Dirty on `jem-dev`; boot-script checksum removal, stale CFN output validation, tests, and ledgers are present. |
| DayOA primary working tree | Clean on `jem-dev` at tag `10.0.67`. |
| Intel cluster | `jul8itelx4` observed in `CREATE_IN_PROGRESS`. |
| RHEL/DRAGEN cluster | Pending discovery; `pcluster-vpc-stack-2c` observed in `CREATE_IN_PROGRESS` after deletion/retry. |
| Release condition | Do not release until Intel and RHEL/DRAGEN cluster creation both reach successful terminal state. |

## Execution Rows

| ID | Scope | Action | Status | Evidence |
| --- | --- | --- | --- | --- |
| MON-001 | AWS | Monitor `jul8itelx4` and the RHEL/DRAGEN create path to terminal state. | IN_PROGRESS | Started read-only polling after Gate 0. |
| DAYOA-001 | DayOA | If dirty, commit/push `jem-dev`, create annotated non-v semver tag, and push tag. | PENDING | Blocked on MON-001 success. |
| DYEC-001 | DYEC | Update DayOA pin if needed, commit/push `jem-dev`, create annotated non-v semver tag, and push tag. | PENDING | Blocked on MON-001 success. |
| DYEC-002 | DYEC | Update DYEC self pin to the new DYEC version, commit/push `jem-dev`, create annotated non-v semver tag, push tag, and report versions. | PENDING | Blocked on DYEC-001 success. |

## Notes

- No cluster deletion, quota change, VPC deletion, or IGW deletion is part of this ledger.
- If either cluster create path fails, release rows remain blocked unless the user explicitly overrides the gate.
