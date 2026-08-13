# DYEC Inflection Analytical 2.1 Pin and Release Companion Ledger

Date: 2026-08-13

## Objective

After the DayOA Inflection analytical `/2.1` GitHub prerelease is remotely verified, update DYEC active/current catalog surfaces to that new DayOA tag, preserve all historical builds, validate the distribution locally, and create a GitHub-only DYEC prerelease.

## Control boundaries

- `release_integrator` is the sole writer of this companion ledger and sole push/tag/GitHub release authority.
- `dyec_catalog_pin` owns the catalog, bundled payload mirror, and focused catalog/pin tests in an isolated worktree.
- No PyPI publication, `twup`, `twine upload`, or attached distribution assets.
- No mutation begins before a complete DayOA release handoff is verified.

## Gate 0 inventory

| Evidence | Value |
|---|---|
| DYEC repository | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` |
| Integration worktree | `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-inflection-2.1-pin` |
| Integration branch | `codex/dyec-inflection-2.1-pin` |
| Selected release | `17.0.7` |
| Annotated tag object | `b160c3e9e1bf5172438bfae0ded78a1d68548048` |
| Peeled release commit | `716137b81e951140fa25fb31a46e65f900b14638` |
| Required ancestry floor | `716137b81e951140fa25fb31a46e65f900b14638` |
| Remote tag inventory | Strict numeric semver maximum after `git fetch --tags origin` is `17.0.7` |
| Ancestry check | `git merge-base --is-ancestor <floor> 17.0.7^{}` returned `0` |
| Integration status before ledger | Clean |
| Primary checkout status | Dirty with extensive untracked user files; all unowned and untouched |
| Source catalog SHA-256 | `90730f1022cf6e5545f15c76b9025a2018e4aac073672bab2802a7ceddf4c34e` |
| Payload catalog SHA-256 | `90730f1022cf6e5545f15c76b9025a2018e4aac073672bab2802a7ceddf4c34e` |
| Immutable raw `17.0.7` block SHA-256 | `55d2e0e106dfb61f8aa38c28b8f4cf2c24b1efcbe486832fe9ca1666d1cf051f` |
| Historical mapping | Immutable `17.0.7` pins DayOA `14.0.9` |

## Required DayOA handoff

- New annotated non-`v` DayOA tag and tag-object SHA.
- Peeled clean release commit descended from `f4c7aa7e15f7dca602059097cb2314f96f05a826`.
- Remote branch and tag proof.
- Focused and complete DayOA test results.
- Non-draft GitHub prerelease URL with `isPrerelease=true` and no assets.
- Explicit proof that DayOA was not published to PyPI.

## Ledger

| ID | Requirement | Status | Category | Gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|
| DYEC-BASE-001 | Select exact floor or eligible annotated descendant | SUCCESS | config_or_startup_contract | G0 | release_integrator | Exact `17.0.7`; object `b160c3e9...`; peeled `716137b8...`; ancestry rc=0 |  | Requested baseline selected |
| DYEC-DEPS-001 | Verify complete DayOA release handoff | SUCCESS | config_or_startup_contract | G4 | release_integrator | DayOA annotated tag `14.0.10`; tag object `e6cdd3a1613dd895658101e94923ab5f6195428a`; peeled/remote branch `b3e52e980fa8a057c23ebe80e53329497f39ab45`; floor ancestry rc=0; full suite 1725 passed/1 skipped; pre-release https://github.com/lsmc-bio/daylily-omics-analysis/releases/tag/14.0.10; `isPrerelease=true`, assets empty; no PyPI action |  | Complete remote handoff verified |
| DYEC-HIST-001 | Preserve every historical numeric snapshot byte-for-byte | SUCCESS | legitimate_safety_handling | G4 | dyec_catalog_pin | Commit `83af52f9`; raw `17.0.7` SHA-256 remains `55d2e0e106dfb61f8aa38c28b8f4cf2c24b1efcbe486832fe9ca1666d1cf051f`, pinned to DayOA `14.0.9`; every prior numeric block byte-identical |  | Historical release contracts frozen |
| DYEC-PIN-001 | Update active repository/default and all active command pins | SUCCESS | config_or_startup_contract | G4 | dyec_catalog_pin | Commit `83af52f9`; active 29/29 `git_tag` and `validated_version` values plus default ref are `14.0.10` |  | Released DayOA pin applied throughout active surfaces |
| DYEC-CAT-001 | Update active/current Inflection metadata to schema 2.1 | SUCCESS | config_or_startup_contract | G4 | dyec_catalog_pin | Commit `83af52f9`; active/current Inflection alias schema text 2.1; exact command flags retained |  | No `-k`; `-n` dry only; hg38/-j333/-T0/-p/mtime preserved |
| DYEC-SNAP-001 | Replace current and append next immutable numeric build | SUCCESS | feature_implementation | G4 | dyec_catalog_pin | Commit `83af52f9`; new `17.0.8` snapshot semantically equals current |  | Next numeric snapshot appended without modifying prior blocks |
| DYEC-PARITY-001 | Preserve source/payload byte equality and current/snapshot semantic equality | SUCCESS | contract_test | G4 | dyec_catalog_pin | Final source/payload SHA-256 both `6122a30bb41708de55c3b9457b2fa087b3cf49238681979ed7f40170e2e4e9e0`; semantic equality PASS |  | Mirrors exact |
| DYEC-TEST-001 | Focused catalog, pin, alias, provider-neutral, and fixture tests | SUCCESS | contract_test | G4 | dyec_catalog_pin | 60 passed + 9 passed + strengthened alias/HG002 16 passed; diff/invariant audit PASS. Nested-export focused suite separately 46 passed. |  | Bounded focused validation complete |
| DYEC-TEST-002 | Complete DYEC suite and static checks | IN_PROGRESS | contract_test | G4 | release_integrator | One complete suite queued after integrated catalog+nested-export commits |  |  |
| DYEC-BUILD-001 | Local wheel/sdist metadata, hash, and embedded catalog validation | OPEN | contract_test | G4 | release_integrator |  |  |  |
| DYEC-AUDIT-001 | Read-only ancestry/history/release audit | OPEN | contract_test | G4 | release_auditor |  |  |  |
| DYEC-REL-001 | Commit, push, annotated tag, and GitHub prerelease | OPEN | feature_implementation | G4 | release_integrator |  |  |  |
| DYEC-NOPYPI-001 | Prove GitHub-only release with no binary assets | OPEN | legitimate_safety_handling | G4 | release_integrator |  |  |  |
| DYEC-CLOSE-001 | All rows terminal and objective completion stated | OPEN | plan_amendment | G5 | release_integrator |  |  |  |

## Release contract

- Update active `default_ref`, every active `git_tag` and `validated_version`, `dyec_builds.current`, and the next numeric snapshot to the released DayOA tag.
- Update only active/current Inflection alias text from schema 2.0 to schema 2.1.
- Preserve the target set and exact execution flags: `hg38`, `-j 333`, `-T 0`, `-p`, `--rerun-triggers mtime`, no `-k`, and `-n` only in the dry-run command.
- Preserve immutable `17.0.7` and all older numeric snapshots exactly.
- Make the new numeric snapshot semantically equal to `current`.
- Keep source and bundled payload catalogs byte-identical.
- Build and inspect distributions locally; upload nowhere.
- Create a clean release commit, non-`v` annotated tag, pushed branch/tag, and non-draft GitHub prerelease without assets.

## Terminal report

- All rows terminal: no.
- Objective complete: no.
- Working-status counts before full DYEC acceptance: `OPEN=5`, `IN_PROGRESS=1`, `ATTEMPTING_BUGFIX=0`.
- Terminal-status counts before full DYEC acceptance: `SUCCESS=8`, `NO_LONGER_NEEDED=0`, `DUPLICATE=0`, `FAIL=0`, `BLOCKED=0`.
