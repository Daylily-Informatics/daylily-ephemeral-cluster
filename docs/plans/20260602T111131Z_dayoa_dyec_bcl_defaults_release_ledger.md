# DayOA/DYEC BCL Defaults Release Ledger

Created: 2026-06-02T11:11:31Z

## Objective

Release the DayOA BCL Convert tile-shard default fixes, update DYEC to pin that DayOA release, then update DYEC self-pins after the first DYEC release.

## Gate 0: Inventory Freeze

- Ledger path: `docs/plans/20260602T111131Z_dayoa_dyec_bcl_defaults_release_ledger.md`
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayOA branch: `codex/dayoa-bclconvert-tile-shards-20260601`
- DayOA latest semver tag: `2.0.35`
- DayOA package versioning: `setuptools_scm` from non-`v` semver tags.
- DYEC repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`
- DYEC branch: `codex/dyec515-full-catalog-20260531`
- DYEC latest semver tag: `5.1.23`
- DYEC package versioning: `setuptools_scm` from non-`v` semver tags.
- Dirty DYEC benchmark artifacts are out of release scope and must not be staged.
- Upload command must run Twine from Conda env `TWINE`.

## Rows

| ID | Repo | Requirement | Status | Category | Gate | Evidence | Terminal Note |
|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Commit BCL Convert defaults fix and tag `2.0.36`. | OPEN | feature_implementation | Gate 5 | Pending. | Pending. |
| REL-002 | DayOA | Build and upload `daylily-omics-analysis==2.0.36` with Twine from env `TWINE`. | OPEN | release_publication | Gate 5 | Pending. | Pending. |
| REL-003 | DYEC | Update DayOA pins/catalog/env to `2.0.36`, commit and tag `5.1.24`. | OPEN | config_or_startup_contract | Gate 5 | Pending. | Pending. |
| REL-004 | DYEC | Build and upload `daylily-ephemeral-cluster==5.1.24` with Twine from env `TWINE`. | OPEN | release_publication | Gate 5 | Pending. | Pending. |
| REL-005 | DYEC | Update DYEC self pins to `5.1.24`, commit and tag `5.1.25`. | OPEN | config_or_startup_contract | Gate 5 | Pending. | Pending. |
| REL-006 | DYEC | Build and upload `daylily-ephemeral-cluster==5.1.25` with Twine from env `TWINE`. | OPEN | release_publication | Gate 5 | Pending. | Pending. |
| REL-007 | Cross-repo | Verify annotated tag type, pushes, and package upload outcomes. | OPEN | release_publication | Gate 5 | Pending. | Pending. |
