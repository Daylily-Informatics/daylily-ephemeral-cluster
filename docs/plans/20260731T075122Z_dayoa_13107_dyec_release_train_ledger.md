# DayOA 13.0.107 and DYEC release-train ledger

## Objective

Advance every active DYEC DayOA catalog and contract-test pin to DayOA
`13.0.107`, then publish two immutable DYEC releases:

1. DYEC `16.1.16` pins DayOA `13.0.107`.
2. DYEC `16.1.17` self-pins the preceding DYEC release `16.1.16`.

## Gate 0 inventory

- DayOA remote: `git@github.com:lsmc-bio/daylily-omics-analysis.git`
- DayOA release: annotated tag `13.0.107`, peeled commit
  `ab16caf9d8359753fb69d53c84c7662ee4855ab0`
- Required observed-sex ancestors:
  - `78bb65b2fa9b1761f857423ca16e3c2bef7e2ab7` — route sex-aware tools
    from observed evidence
  - `0863d3604cde5608ac64e02cf27e6140bec543cc` — route sex-aware tools
    from short-read evidence
- DYEC base:
  `a3c9a8ae6b9aafe181cf78a4e1dc64f0bff48d25`
- Release branch: `codex/dyec-dayoa-13107-pin-20260731`
- Planned immutable tags: `16.1.16` and `16.1.17`

The existing Take61 worktree and its untracked launch evidence are outside this
release worktree and remain untouched.

## Ledger

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| DAYOA-001 | Verify `13.0.107` is the newest DayOA numeric release | SUCCESS | Fresh remote tag fetch; numeric tag order ends at `13.0.107` |
| DAYOA-002 | Verify `13.0.107` is annotated and remotely published | SUCCESS | Local object type is `tag`; remote tag object peels to `ab16caf9` |
| DAYOA-003 | Verify both observed-sex fixes are ancestors of `13.0.107` | SUCCESS | `git merge-base --is-ancestor` returned RC 0 for `78bb65b2` and `0863d360` |
| DYEC-001 | Work from an isolated clean branch | SUCCESS | Clean worktree based on remote commit `a3c9a8ae` |
| DYEC-002 | Advance source and packaged catalogs to DayOA `13.0.107` | SUCCESS | All active `default_ref` and `git_tag` values now name `13.0.107`; source/package catalogs are byte-identical |
| DYEC-003 | Advance DayOA contract-test constants and release commit | SUCCESS | Constants name `13.0.107` and peeled commit `ab16caf9`; 237 focused tests passed |
| DYEC-004 | Commit, push, and publish annotated `16.1.16` | SUCCESS | Remote annotated tag peels to pin commit `353cd5832ffaf64ab2c2e78fb7474b0c19fd6940` |
| DYEC-005 | Advance source and packaged DYEC self-pins to `16.1.16` | SUCCESS | Source/package global configs are byte-identical; four fork-contract tests passed |
| DYEC-006 | Commit, push, and publish annotated `16.1.17` | OPEN | Pending |
| VERIFY-001 | Verify clean branch and remote annotated tags | OPEN | Pending |

## Completion rule

The train is complete only when every row has a terminal status, both remote
tags are annotated and peel to the intended commits, source/package payload
copies are byte-identical, and the final release worktree is clean.
