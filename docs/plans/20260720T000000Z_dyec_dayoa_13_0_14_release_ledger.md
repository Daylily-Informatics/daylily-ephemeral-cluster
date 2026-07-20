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
| REL-002 | Intermediate release | Commit and push the DayOA pin release branch, then cut and push annotated DYEC tag `13.0.0`. | SUCCESS | feature_implementation | Gate 1 | Codex | Commit `defe11d6`; `git push -u origin codex/dayoa-pin-13.0.14`; `git tag -a 13.0.0`; `git cat-file -t 13.0.0` -> `tag`; `git push origin 13.0.0` |  | Branch and annotated intermediate tag `13.0.0` pushed. |
| REL-003 | DYEC self-pin | Update DYEC self-pin surfaces to `13.0.0`, commit, push, open PR, merge to `main`, sync merged `main` state. | SUCCESS | config_or_startup_contract | Gate 1 | Codex | Commit `2d5c280a`; PR #47 merged to `main` at `2809a659`; `pytest tests/test_lsmc_bio_fork_contract.py tests/test_hiomrs_command_catalog.py tests/test_command_sample_stats.py -q` -> 23 passed; `git fetch origin main --tags` synced the clean worktree view of `origin/main`. |  | Self-pin release prep reached `main`; canonical checkout fast-forward was intentionally not forced because unrelated untracked plan artifacts there would be overwritten by tracked files from `origin/main`. |
| REL-004 | Final release | Cut and push annotated DYEC tag `13.0.1` from synced `main`. | IN_PROGRESS | feature_implementation | Gate 5 | Codex | Closeout ledger commit pending before final tag. |  |  |
