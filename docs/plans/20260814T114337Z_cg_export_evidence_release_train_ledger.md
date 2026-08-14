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
- No local test suite was run, following the user's explicit instruction. PR
  100 had no reported checks and main had no required status-check policy; its
  normal merge state was CLEAN.
- FSx deletion is outside this release and has not been authorized or run.

## Control ledger

| ID | Area | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|---|
| REL-DAYOA-001 | DayOA promotion | Merge the existing maximum 14.0.20 tag into main. | SUCCESS | PR 108 merged at 13acb2aa4772d6ba05c566593b0809dd964fdfa0 after three successful CodeQL checks. | The existing source tag remains immutable. |
| REL-DYEC-001 | Evidence record | Add the verified CG export URI and success run record to source and packaged current catalogs. | SUCCESS | Source and packaged current catalogs are byte-identical and record the exact FSx task, DRA, and S3 paths. | Released in commit 11fa09a1a62407147a919fd910a3b574f999b1c1. |
| REL-DYEC-002 | Release publication | Commit, push, open a PR to main, merge after green checks, and tag the merged DYEC evidence release. | SUCCESS | Commit 11fa09a1a62407147a919fd910a3b574f999b1c1 was merged by PR 100 at 276e5ab28e6dba881cfdffde46bddad52c6fc662. Annotated tag 17.0.26 is remote and peels to that exact merge commit. | The maximum-tag baseline and CG export evidence are in main. |
| REL-DYEC-003 | Version contract | Preserve the current no-self-pin contract. | SUCCESS | Source and packaged daylily_cli_global.yaml omit the retired pin keys. | No redundant tag will be invented. |
| REL-FSX-001 | Cleanup boundary | Leave the exported CG root on FSx. | SUCCESS | No deletion command was invoked. | A separate explicit destructive approval is required for deletion. |

## Final report

All rows terminal: yes

Objective complete: yes

## Release proof

- DayOA annotated tag 14.0.20 peels to
  64b1453c55d90e8b23b3e3af500dc9f79216ca3e and is an ancestor of DayOA main
  through PR 108.
- DYEC annotated tag 17.0.26 is tag object
  067c3ce20b4c02ae2daf4e0cad861c721755d708 and peels to the merged main
  commit 276e5ab28e6dba881cfdffde46bddad52c6fc662 through PR 100.
- The source FSx analysis root was intentionally retained. The transient DRA
  dra-00f1368711631e73d is detached; task task-06adea4ad8e644e89 is
  SUCCEEDED with 3,616 succeeded and 0 failed files.
