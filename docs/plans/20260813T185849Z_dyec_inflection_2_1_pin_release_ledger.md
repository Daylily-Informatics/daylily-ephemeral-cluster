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

## Release collision amendment

After the initial Gate 0 inventory, a separately authorized DYEC `17.0.8`
release was published on `origin/main`. The annotated tag object is
`97b5242cb24c1fac10c8518b0ca76899c2aa721e`; it peels to mainline merge commit
`60f3ed6bbd00845b16e10c1130fa46bc64b3ed65`, which descends from the selected
`17.0.7` floor. The release tag is immutable and was not moved. This lane merged
that mainline release, preserved its catalog snapshot byte-for-byte, and moved
the pending version to `17.0.9`.

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
| DYEC-HIST-001 | Preserve every historical numeric snapshot byte-for-byte | SUCCESS | legitimate_safety_handling | G4 | dyec_catalog_pin | Raw `17.0.7` SHA-256 remains `55d2e0e106dfb61f8aa38c28b8f4cf2c24b1efcbe486832fe9ca1666d1cf051f`, pinned to DayOA `14.0.9`; published raw `17.0.8` remains byte-exact SHA-256 `6dac4a6f5724191ee1c930a07d209b29c90c1a8171b2574d0afc94e1628efc8e`; every older numeric block byte-identical |  | Historical release contracts frozen across the concurrent mainline release |
| DYEC-PIN-001 | Update active repository/default and all active command pins | SUCCESS | config_or_startup_contract | G4 | dyec_catalog_pin | Commit `83af52f9`; active 29/29 `git_tag` and `validated_version` values plus default ref are `14.0.10` |  | Released DayOA pin applied throughout active surfaces |
| DYEC-CAT-001 | Update active/current Inflection metadata to schema 2.1 | SUCCESS | config_or_startup_contract | G4 | dyec_catalog_pin | Commit `83af52f9`; active/current Inflection alias schema text 2.1; exact command flags retained |  | No `-k`; `-n` dry only; hg38/-j333/-T0/-p/mtime preserved |
| DYEC-SNAP-001 | Replace current and append next immutable numeric build | SUCCESS | feature_implementation | G4 | dyec_catalog_pin | New `17.0.9` snapshot semantically equals current; current raw SHA-256 `6c390dbd43a3b1d3f18491b39a5921ec9d7ea9b2256d56e42f468f22d4828be5`; raw `17.0.9` SHA-256 `8065f45dec35d88277dba5e0d2b2995eaab84829b029fe337c25be0ce1001ce7` | Concurrent annotated `17.0.8` appeared after Gate 0 | Pending version advanced without moving or rewriting the published tag |
| DYEC-PARITY-001 | Preserve source/payload byte equality and current/snapshot semantic equality | SUCCESS | contract_test | G4 | dyec_catalog_pin | Final source/payload SHA-256 both `c2188c91177951b85c0cede6c71fca1bb075980765b6aef29bdd5571b92676f6`; current/17.0.9 semantic equality PASS |  | Mirrors exact |
| DYEC-TEST-001 | Focused catalog, pin, alias, provider-neutral, and fixture tests | SUCCESS | contract_test | G4 | dyec_catalog_pin | Post-collision focused catalog suite 60 passed; combined nested-analysis plus runtime-cache export suite 53 passed; diff/invariant audit PASS |  | Bounded focused validation complete |
| DYEC-EXPORT-001 | Permit exact nested no-delete analytical-package export | SUCCESS | feature_implementation | G4 | release_integrator | Commits `c4a98931` + `bee5bda9`; focused export suite 46 passed; live task `task-08d5ea4b86628f7c1` SUCCEEDED 157/157/0, DRA `dra-0ccd96e22f9631ba2` detached/DELETED, `DeleteDataInFileSystem=false`; exact S3 prefix contains 157 objects/2,622,473,206 bytes and schema-2.1 manifest | Root-only export parser rejected explicit nested package source/destination before AWS resource creation | Full nested source retained for DRA/task while ownership remains first two analysis components; explicit destination batch plus exact source leaf; no fallback/discovery |
| DYEC-TEST-002 | Complete DYEC suite and static checks | SUCCESS | contract_test | G4 | release_integrator | Post-merge complete suite: 2539 passed, 11 skipped, 1 expected dependency warning in 155.61s; `git diff --check` and conflict-marker audit passed |  | Mainline 17.0.8 plus nested export plus 14.0.10 catalog pin validated together |
| DYEC-BUILD-001 | Local wheel/sdist metadata, hash, and embedded catalog validation | SUCCESS | contract_test | G4 | release_integrator | Pretag build from clean merge commit `bf40f6e5` with `SETUPTOOLS_SCM_PRETEND_VERSION=17.0.9`; wheel/sdist built locally in `/tmp/dyec-17.0.9-build.BK1SFH`; `twine check` passed; wheel metadata name/version `daylily-ephemeral-cluster`/`17.0.9`; source, payload, wheel, and sdist catalog SHA-256 all `c2188c91177951b85c0cede6c71fca1bb075980765b6aef29bdd5571b92676f6`; wheel SHA-256 `0558eb41...`; sdist SHA-256 `11289fa5...` |  | Local validation only; artifacts were not uploaded or attached |
| DYEC-AUDIT-001 | Read-only ancestry/history/release audit | SUCCESS | contract_test | G4 | release_auditor | Final read-only audit PASS with no actionable findings: both 17.0.7 and 17.0.8 annotated-tag peels are ancestors; all 13 published numeric snapshots are present and byte-identical; active 29/29 pins are 14.0.10; current equals 17.0.9; source/payload/artifact parity passes; nested and runtime-cache exports coexist; no publish surface changed |  | Independent acceptance complete; post-release remote/no-assets proof remains orchestrator closeout |
| DYEC-REL-001 | Commit, push, annotated tag, and GitHub prerelease | IN_PROGRESS | feature_implementation | G4 | release_integrator | Release retargeted to 17.0.9 after immutable remote 17.0.8 collision |  |  |
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
- Working-status counts before release closeout: `OPEN=2`, `IN_PROGRESS=1`, `ATTEMPTING_BUGFIX=0`.
- Terminal-status counts before release closeout: `SUCCESS=12`, `NO_LONGER_NEEDED=0`, `DUPLICATE=0`, `FAIL=0`, `BLOCKED=0`.
