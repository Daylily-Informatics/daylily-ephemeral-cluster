# DYEC 18.0.22 release ledger: DayOA 15.0.11 and audited code integration

## Gate 0 baseline

- Release branch: `codex/dyec-18.0.22-dayoa-15.0.11`
- Release base: annotated `18.0.21` (`4eda67c07f273613b1e1b9d7c9fbc7058086aa57`)
- Intended release tag: annotated `18.0.22`
- Current command-catalog DayOA pin: `15.0.11`
- Scope: integrate all material DYEC code identified in the preceding audit and advance current catalog calls to the released DayOA `15.0.11` tag.

## Execution ledger

| ID | Work item | Status | Evidence |
| --- | --- | --- | --- |
| BASE-001 | Establish the new release branch from the highest DYEC release | SUCCESS | `18.0.21` is the highest existing semver tag and is annotated; branch starts at its peeled commit `4eda67c07f273613b1e1b9d7c9fbc7058086aa57`. |
| CODE-001 | Integrate the audited material DYEC code | SUCCESS | The `18.0.21` base already contains `16745df`, `32574566`, `ff094634`, `652d09d`, and `ef7c78d`; the missing `374529c` HG002 combined-report builder/evidence collector is staged on this release branch. |
| CATALOG-001 | Advance current command-catalog DayOA pins | SUCCESS | Both canonical and packaged catalog copies have 61 active `default_ref`/`git_tag` pins at `15.0.11`; their six historical `dayoa_tag: 15.0.10` validation receipts were deliberately retained. |
| VERIFY-001 | Validate the release diff and catalog mirror | SUCCESS | `git diff --cached --check` passed; catalog copies are byte-identical; both have 61 active `15.0.11` pins and no active `15.0.10` selector. |
| RELEASE-001 | Commit, push branch, create and push annotated tag | SUCCESS | The clean release commit is the branch tip and is published as annotated tag `18.0.22`; the tag resolves to this commit. |

## Scope boundary

This release changes the current operational DayOA selector only. Historical catalog receipt metadata remains immutable evidence of the `15.0.10` validation runs that produced it.
