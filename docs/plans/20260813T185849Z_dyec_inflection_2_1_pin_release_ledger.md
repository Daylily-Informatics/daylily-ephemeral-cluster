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
| DYEC-DEPS-001 | Verify complete DayOA release handoff | OPEN | config_or_startup_contract | G4 | release_integrator |  |  |  |
| DYEC-HIST-001 | Preserve every historical numeric snapshot byte-for-byte | OPEN | legitimate_safety_handling | G4 | dyec_catalog_pin | Baseline `17.0.7` block hash recorded above |  |  |
| DYEC-PIN-001 | Update active repository/default and all active command pins | OPEN | config_or_startup_contract | G4 | dyec_catalog_pin | Baseline contains 29 active DayOA `14.0.9` analysis rows |  |  |
| DYEC-CAT-001 | Update active/current Inflection metadata to schema 2.1 | OPEN | config_or_startup_contract | G4 | dyec_catalog_pin |  |  |  |
| DYEC-SNAP-001 | Replace current and append next immutable numeric build | OPEN | feature_implementation | G4 | dyec_catalog_pin | Expected `17.0.8` if no later eligible release appears |  |  |
| DYEC-PARITY-001 | Preserve source/payload byte equality and current/snapshot semantic equality | OPEN | contract_test | G4 | dyec_catalog_pin | Baseline catalog hash recorded above |  |  |  |
| DYEC-TEST-001 | Focused catalog, pin, alias, provider-neutral, and fixture tests | OPEN | contract_test | G4 | dyec_catalog_pin |  |  |  |
| DYEC-TEST-002 | Complete DYEC suite and static checks | OPEN | contract_test | G4 | release_integrator |  |  |  |
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
- Working-status counts at Gate 0: `OPEN=13`, `IN_PROGRESS=0`, `ATTEMPTING_BUGFIX=0`.
- Terminal-status counts at Gate 0: `SUCCESS=1`, `NO_LONGER_NEEDED=0`, `DUPLICATE=0`, `FAIL=0`, `BLOCKED=0`.
