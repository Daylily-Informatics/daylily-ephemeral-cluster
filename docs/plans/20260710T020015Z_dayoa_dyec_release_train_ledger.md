# DayOA and DYEC Release Train Ledger

Created: 2026-07-10T02:00:15Z

Controlling request: release all current dirty DayOA work on `jem-dev`, pin that DayOA release throughout DYEC, release all current dirty DYEC work, then self-pin DYEC to that first DYEC release and cut a final DYEC release.

## Gate 0: Inventory Freeze

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch: `jem-dev`; `HEAD` and `origin/jem-dev` both `280daae` (`10.0.76`)
- DayOA dirty baseline: four tracked files for RTG vcfeval Slurm memory (`slurm`, `slurm_rhel`, and two tests)
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch: `jem-dev`; `HEAD` and `origin/jem-dev` both `07aae755` (`10.0.129`)
- DYEC dirty baseline: 25 tracked Intel AZ-template/default-resolution/test files plus the existing `20260710T002740Z_*` command-catalog evidence and `20260710T012212Z_*` Intel contract ledger
- Remote refresh: `git fetch origin jem-dev --tags --prune` succeeded in both repositories; both branches remain `0 0` ahead/behind
- Reserved unused tags: DayOA `10.0.77`; DYEC `10.0.130` and `10.0.131`
- DayOA pin sweep: `rg -l '10\\.0\\.76' pyproject.toml config daylily_ec/resources/payload/config tests` -> seven active files
- DYEC self-pin sweep: `rg -n 'git_ephemeral_cluster_repo_tag|10\\.0\\.129' ...` plus prior self-pin commit inspection -> four active files
- Scope rule: preserve and include all pre-existing dirty and untracked work; do not discard changes originating in other tasks.

## Control Ledger

| ID | Repo | Requirement | Status | Category | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Verify the complete dirty RTG-memory change set | SUCCESS | contract_test | Gate 0 | `pytest` focused RTG/profile coverage -> `4 passed`; `git diff --check` passed; old-pin negative sweep passed | Complete four-file change set verified. |
| REL-002 | DayOA | Commit all dirty work, push `jem-dev`, create and push annotated `10.0.77` | SUCCESS | feature_implementation | Gate 5 | Commit `d81108d`; `git push origin jem-dev` succeeded; annotated tag `10.0.77` pushed | DayOA release published. |
| REL-003 | DYEC | Pin DayOA `10.0.77` in `pyproject.toml`, active and packaged config, overrides, and tests | SUCCESS | config_or_startup_contract | Gate 2 | Seven active pin files updated; source/payload catalogs byte-match; historical `10.0.76` run evidence retained | Active dependency, catalog, override, and contract pins now use DayOA `10.0.77`. |
| REL-004 | DYEC | Verify and commit every current dirty/untracked change, push `jem-dev`, create and push annotated `10.0.130` | SUCCESS | feature_implementation | Gate 5 | Combined focused suite -> `244 passed`; commit `5e931485`; branch and annotated tag `10.0.130` pushed | All pre-existing dirty/untracked work plus the DayOA pin and release ledger were published. Generated TSV terminal delimiters were preserved. |
| REL-005 | DYEC | Self-pin active and packaged DYEC config to `10.0.130` and update contract pins | SUCCESS | config_or_startup_contract | Gate 2 | Both global configs byte-match; override and test pins agree; focused suite -> `21 passed`; `git diff --check` passed | Active and packaged DYEC defaults now self-pin `10.0.130`. |
| REL-006 | DYEC | Verify self-pin, commit, push `jem-dev`, create and push annotated `10.0.131` | IN_PROGRESS | feature_implementation | Gate 5 | Tag confirmed unused locally after remote tag fetch | Final release commit in progress. |
| REL-007 | Both | Verify remote branches, annotated tag objects, exact tag commits, and clean worktrees | OPEN | contract_test | Gate 5 | Final acceptance pending | |

## Release Evidence

Evidence will be appended as each row reaches a terminal state.
