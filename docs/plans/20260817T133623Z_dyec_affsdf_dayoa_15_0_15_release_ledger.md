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
| COMMIT-001 | Preservation | Commit and push every DYEC-owned pre-existing change to `affsdf`, excluding only the two embedded external checkouts. | OPEN | feature_implementation | Gate 1 | primary | Pending staged-scope review, commit, and remote verification. |  |  |
| PIN-001 | DayOA pin | Set the active package/repository DayOA dependency pin to exactly `15.0.15`. | OPEN | config_or_startup_contract | Gate 2 | primary | Pending source inventory and edit. |  |  |
| CAT-001 | Command catalog | Set every current command-catalog DayOA `git_tag` / validated-version pin to exactly `15.0.15` in source and packaged payload copies. | OPEN | config_or_startup_contract | Gate 2 | primary | Pending source inventory, edit, exact search, and byte-parity check. |  |  |
| TEST-001 | Verification | Run focused pin/catalog contract checks and source/payload parity checks. | OPEN | contract_test | Gate 5 | primary | Pending. |  |  |
| PUSH-001 | Working branch | Commit the pin changes separately and verify both `affsdf` commits on origin. | OPEN | feature_implementation | Gate 5 | primary | Pending. |  |  |
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
