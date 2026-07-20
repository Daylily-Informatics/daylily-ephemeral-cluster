# DYEC DayOA 13.0.14 Release Ledger

Date: 2026-07-20

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Repo | `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-dayoa-pin-13.0.14` |
| Base | `origin/main` at `0be40cf8` (`Merge pull request #46 from lsmc-bio/codex/dayoa-13.0.12-dyec-release-20260719`) |
| Branch | `codex/dayoa-pin-13.0.14` |
| Existing DYEC latest tag | `12.0.8` |
| Requested DayOA tag | `13.0.14` |
| DayOA tag proof | `git ls-remote --tags git@github.com:lsmc-bio/daylily-omics-analysis.git 'refs/tags/13.0.14*'` returned tag object `c8ede6a` and peeled commit `3ccb1d1` |
| Dirty-state boundary | Canonical checkout had unrelated untracked ledgers, so this clean worktree was created from `origin/main` to avoid staging user artifacts. |

## Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA pin | Update DYEC DayOA default/git-tag pins from `13.0.12` to `13.0.14`. | SUCCESS | config_or_startup_contract | Gate 1 | Codex | `pytest tests/test_lsmc_bio_fork_contract.py tests/test_hiomrs_command_catalog.py tests/test_command_sample_stats.py -q` -> 23 passed |  | Source and packaged command catalogs plus tests now pin DayOA `13.0.14`; validation provenance remains `12.0.3`. |
| REL-002 | Intermediate release | Commit and push the DayOA pin release branch, then cut and push annotated DYEC tag `13.0.0`. | IN_PROGRESS | feature_implementation | Gate 1 | Codex | Pin tests passed; commit/tag pending |  |  |
| REL-003 | DYEC self-pin | Update DYEC self-pin surfaces to `13.0.0`, commit, push, open PR, merge to `main`, sync local `main`. | OPEN | config_or_startup_contract | Gate 1 | Codex | Pending |  |  |
| REL-004 | Final release | Cut and push annotated DYEC tag `13.0.1` from synced `main`. | OPEN | feature_implementation | Gate 5 | Codex | Pending |  |  |
