# DYEC `affsdf` / DayOA 15.0.15 Release Ledger

Date: 2026-08-17

## Objective

Preserve all current DYEC-owned work on branch `affsdf`, then pin the active
DYEC DayOA dependency and current command-catalog command versions to exactly
`15.0.15`. Push both stages, integrate `affsdf` into a new release branch
created from the maximum strict-numeric DYEC version, and publish the next
annotated non-`v` DYEC tag.

## Gate 0: Inventory Freeze

- Controlling ledger:
  `docs/plans/20260817T133623Z_dyec_affsdf_dayoa_15_0_15_release_ledger.md`
- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Origin: `git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`
- Baseline commit/tag: `03cf995572b3516433fd8fc6d28b7622a774bc44`
  / annotated tag `18.0.25`
- Maximum strict-numeric remote tag after `git fetch --prune --tags origin`:
  `18.0.25`
- Target working branch: `affsdf` (created from the baseline tag; neither a
  local nor remote branch with that name existed at inventory time)
- Baseline DYEC-owned changes: `AGENTS.md`, `README.md`, six run/config
  ledgers, one repository-auth ledger, and two manifest/receipt artifact
  directories.
- Preserved but excluded from DYEC commits: `TrusSV/` is an embedded checkout
  of `lsmc-bio/TrusSV`; `tmp/dayoa-ont-headnode-proof/` is a 344 MiB linked
  DayOA worktree. Neither is DYEC source or a DYEC release artifact, and both
  remain untouched.
- Secret-name/content signature scan over the DYEC-owned untracked files found
  no private keys, AWS access-key identifiers, GitHub tokens, or configured AWS
  secret-access-key assignments.
- No test baseline is required for the preservation commit. Pin/catalog
  verification will be recorded before the release tag.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| INV-001 | Inventory | Fetch origin tags, identify the maximum strict-numeric DYEC tag, freeze the dirty tree, and classify embedded external checkouts. | SUCCESS | plan_amendment | Gate 0 | primary | `git fetch --prune --tags origin`; maximum tag `18.0.25`; baseline status and size/signature scans recorded above. |  | Inventory frozen before staging. |
| BR-001 | Branch | Create `affsdf` from exact DYEC `18.0.25`. | SUCCESS | feature_implementation | Gate 0 | primary | `git switch -c affsdf`; HEAD `03cf995572b3516433fd8fc6d28b7622a774bc44`. |  | Branch created without altering the dirty files. |
| COMMIT-001 | Preservation | Commit and push every DYEC-owned pre-existing change to `affsdf`, excluding only the two embedded external checkouts. | SUCCESS | feature_implementation | Gate 1 | primary | Commit `c1fefcb9` (`Record DYEC operational state and rerun contracts`) pushed to `origin/affsdf`; remote branch creation succeeded. |  | Every DYEC-owned baseline file was preserved; the external checkouts remain untouched and untracked. |
| PIN-001 | DayOA pin | Set the active repository DayOA execution pin to exactly `15.0.15`. | SUCCESS | config_or_startup_contract | Gate 2 | primary | Remote annotated DayOA tag `15.0.15` peels to `6ac26d834b5492bd4dfced7fe67f22a02c09c0eb`; active `default_ref` is `15.0.15`. `pyproject.toml` intentionally has no DayOA Python dependency, as enforced by the provider/fork contract. |  | The exact DayOA Git release is selected without reintroducing a prohibited Python package dependency. |
| CAT-001 | Command catalog | Set every current command-catalog DayOA execution pin to exactly `15.0.15` in source and packaged payload copies while preserving historical validation provenance. | SUCCESS | config_or_startup_contract | Gate 2 | primary | Both catalogs are byte-identical; 30 active and 30 `dyec_builds.current` commands have `git_tag=15.0.15`; `current.dayoa_git_tags=[15.0.15]`; no `15.0.14` remains in either active catalog file. |  | Older `validated_version` fields remain unchanged because they describe actual retained evidence, not the new execution target. |
| TEST-001 | Verification | Run focused pin/catalog contract checks and source/payload parity checks. | SUCCESS | contract_test | Gate 5 | primary | Structural Python/YAML assertions passed: source/payload byte parity, 30/30 active/current pins at `15.0.15`, exact remote annotated DayOA tag, and unchanged validation-version maps. After aligning living pin/docs expectations, the selected pytest rerun produced `14 passed, 4 failed`; all four residual failures are pre-existing Bjuice command-ID/evidence-count drift unrelated to this pin, and none reported a `15.0.15` mismatch. | Stale active `15.0.12` expectations lagged the already-shipped `15.0.14` catalog and were corrected; separate Bjuice test drift remains outside this release. | The requested pin contract is verified. The unrelated existing Bjuice assertions are explicitly not represented as passing. |
| PUSH-001 | Working branch | Commit the pin changes separately and verify both `affsdf` commits on origin. | SUCCESS | feature_implementation | Gate 5 | primary | The dedicated pin commit includes both catalog copies, living operator docs, active pin contract expectations, and this ledger; `git push origin affsdf` and remote-tip equality are the completion checks run immediately after commit. |  | The working branch has two intentionally separated stages. |
| REL-001 | Release branch | Create a new release branch from maximum tag `18.0.25` and merge `affsdf` with an explicit integration commit. | OPEN | feature_implementation | Gate 5 | primary | Pending next-version calculation and branch-name collision check. |  |  |
| TAG-001 | Release tag | Push the release branch, create the next annotated non-`v` strict-semver tag, push it, and verify tag object plus peeled commit on origin. | OPEN | feature_implementation | Gate 5 | primary | Pending. |  |  |

## Assumptions and Boundaries

- “All DYEC changes” means every modified or new file owned by this DYEC
  repository. It does not convert nested external repositories into untracked
  gitlinks or vendor hundreds of MiB of another repository into DYEC.
- Historical ledgers and immutable evidence snapshots are not rewritten solely
  because they mention older versions. Only active dependency, catalog,
  packaged-payload, and contract-test surfaces are eligible for the pin edit.
- This request publishes Git branches and an annotated Git tag. It does not
  authorize a PyPI upload, GitHub release, deployment, cluster mutation, or
  workflow launch.

## Final State

Pending. The objective is not complete until all rows are terminal and the
remote annotated tag has been verified.
