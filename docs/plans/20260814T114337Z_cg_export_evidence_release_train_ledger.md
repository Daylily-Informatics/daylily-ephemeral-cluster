# CG exported-evidence release train ledger

Created: 2026-08-14T11:43:37Z

## Scope and Gate 0

- Promote the existing annotated DayOA 14.0.20 tag to main without adding any
  DayOA source change. DayOA pull request 108 merged normally at
  13acb2aa4772d6ba05c566593b0809dd964fdfa0.
- Start the DYEC evidence release from the highest existing annotated DYEC tag,
  17.0.25, which peels to 8295f9e0c2569c22b320ffb135b7aa1252847207.
- Record only the primary receipt-bound CG slim analysis and its verified
  no-delete FSx export in the current source and packaged command catalogs.
- The current DYEC source contract intentionally has no self-pin keys. They
  were removed by fd1b583b73ccc22e3c3589357e4d3b09c8502d6a; this release will
  not restore them or cut a redundant follow-up self-pin tag.
- No local test suite will be run, following the user's explicit instruction.
  GitHub pull-request checks remain the release gate.
- FSx deletion is outside this release and has not been authorized or run.

## Control ledger

| ID | Area | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|---|
| REL-DAYOA-001 | DayOA promotion | Merge the existing maximum 14.0.20 tag into main. | SUCCESS | PR 108 merged at 13acb2aa4772d6ba05c566593b0809dd964fdfa0 after three successful CodeQL checks. | The existing source tag remains immutable. |
| REL-DYEC-001 | Evidence record | Add the verified CG export URI and success run record to source and packaged current catalogs. | SUCCESS | Source and packaged current catalogs are byte-identical and record the exact FSx task, DRA, and S3 paths. | Ready for the release commit. |
| REL-DYEC-002 | Release publication | Commit, push, open a PR to main, merge after green checks, and tag the merged DYEC evidence release. | OPEN | Branch is based on 17.0.25. | Pending publication. |
| REL-DYEC-003 | Version contract | Preserve the current no-self-pin contract. | SUCCESS | Source and packaged daylily_cli_global.yaml omit the retired pin keys. | No redundant tag will be invented. |
| REL-FSX-001 | Cleanup boundary | Leave the exported CG root on FSx. | SUCCESS | No deletion command was invoked. | A separate explicit destructive approval is required for deletion. |

## Final report

All rows terminal: no

Objective complete: no
