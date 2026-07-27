# DYEC DayOA 13.0.46 Catalog Release Ledger

Created: `2026-07-26T17:01:55Z`

## Objective

Publish the next DYEC patch release with every one of the 25 analysis commands,
both catalog copies, and the repository default pinned uniformly to the
owner-published DayOA `13.0.46` tag. This is required so Ursa can submit a
three-platform RunQC batch without retaining the deterministic Ultima
Snakemake-formatting failure present in the `13.0.45` lineage.

## Baseline

- Worktree: `/tmp/dyec-dayoa-13-0-46-20260726`
- Branch: `codex/dyec-dayoa-13-0-46-20260726`
- Base: annotated DYEC tag `14.0.18`, peeled commit `d2981924`
- DayOA input: annotated tag `13.0.46`, peeled commit `9bb911b4`
- Release target: annotated DYEC tag `14.0.19`
- No cluster, mount, budget, or other AWS mutation is in scope.

## Control ledger

| ID | Requirement | Status | Evidence | Root cause / terminal note |
|---|---|---|---|---|
| DYEC-001 | Replace both catalog defaults and every `git_tag`/`validated_version` command pin with DayOA `13.0.46`. | `SUCCESS` | Both catalog copies have SHA-256 `095f506c928f560abff037c64e4b785fc1c0bf7d817324d7e8f57b107aed0108`; parsed proof reports 25 commands, singleton `git_tag` and `validated_version` sets `13.0.46`, and repository default `13.0.46`. | Uniform maximum pin proven. |
| DYEC-002 | Update both packaged global configs and exact release-contract tests to DYEC `14.0.19`. | `SUCCESS` | Both packaged global configs are byte-identical and direct test expectations require `14.0.19`. | Release contract advanced without a compatibility path. |
| DYEC-003 | Run focused catalog/repository/registry tests and scoped lint/diff checks. | `SUCCESS` | Seven focused files: `294 passed`; both config-copy comparisons and `git diff --check` pass. Repository Ruff reports 12 pre-existing findings in unchanged lines of the focused test files; no Ruff finding is introduced by the scalar expectation changes. | Required behavior tests and changed-file whitespace checks pass. |
| DYEC-004 | Commit, push the branch, create and push annotated numeric tag `14.0.19`, and verify its peeled commit. | `OPEN` | Pending. |  |
| DYEC-005 | Prove the published tag contains 25 commands, one repository default, and no mixed DayOA pins. | `OPEN` | Pending. |  |

## Final report

All rows terminal: `no`

Objective complete: `no`
