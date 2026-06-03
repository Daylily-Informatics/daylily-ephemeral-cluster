# DYEC 5.1.31 Dirty Release Train Ledger

Created: 2026-06-03T14:12:24Z

## Objective

Release all current new, modified, and dirty work across DayOA and DYEC, ending at a clean DYEC semver package release.

## Gate 0 Inventory

- Control ledger: `docs/plans/20260603T141224Z_dyec_5131_dirty_release_train_ledger.md`
- DYEC repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- Instruction files read: `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.agents/AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`, `./AGENTS.md`, `./AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/projects/daylily/daylily-omics-analysis/AGENTS.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`
- DayOA status: branch `codex/dayoa-bclconvert-tile-shards-20260601`, clean, synced with `origin/codex/dayoa-bclconvert-tile-shards-20260601`
- DayOA latest numeric semver tag at Gate 0: `2.0.41`; `HEAD` was exactly tagged `2.0.41`; no modified or untracked DayOA files found before the user-added 384-vCPU partition request
- DYEC status: branch `codex/dyec515-full-catalog-20260531`, synced with `origin/codex/dyec515-full-catalog-20260531`
- DYEC latest numeric semver tag before this train: `5.1.30`
- DYEC branch commits after `5.1.30` at initial inventory: `a6cde131 Record DYEC 5.1.30 publication evidence`, `f16510c2 Record dyec5128 benchmark catalog evidence`
- DYEC dirty inventory before this ledger: 21 modified tracked files, 23 untracked files, all within source, tests, docs, payload mirrors, or `docs/plans/`
- DYEC package pins at Gate 0: `daylily-omics-analysis==2.0.41`; `git_ephemeral_cluster_repo_tag: 5.1.30`; `git_ephemeral_cluster_repo_release_tag: 5.1.30`
- Next DYEC release target: `5.1.31`

## Rows

| ID | Repo | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Include any new DayOA dirty or modified work in the train, or prove none exists. | SUCCESS | repo_state_publish | Gate 5 | Codex | Initial `git status --short --branch` -> clean at `2.0.41`; user then requested adding `bcl2fq-i384-nvme-test` to the Slurm job partition defaults. Updated DayOA `config/day_profiles/slurm/templates/config.yaml`, `workflow/rules/help.smk`, and `tests/test_slurm_profile.py`; `python -m pytest -q tests/test_slurm_profile.py tests/test_bclconvert_multiqc.py tests/test_workflow_catalog.py tests/test_workflow_target_aliases.py tests/test_rule_log_benchmark_contracts.py` -> 36 passed; committed `942e6f7`, annotated tag `2.0.42` pushed, PyPI upload completed, `pip index` and `pip download daylily-omics-analysis==2.0.42` succeeded. |  | DayOA `2.0.42` is the DayOA input for this DYEC release train. |
| REL-002 | DYEC | Include all DYEC modified and untracked work in a release commit. | IN_PROGRESS | repo_state_publish | Gate 5 | Codex | Gate 0 found 21 modified tracked files and 23 untracked files; post-Gate-0 check found local commit `00f329f9 Document day-clone tag usage` already ahead of origin and one additional cleanup stdout evidence file; user later directed ignoring new dirty files generated from the running validation driver. |  |  |
| REL-003 | DYEC | Validate the dirty DYEC source, tests, package mirrors, and docs before release. | SUCCESS | release_validation | Gate 5 | Codex | `source ./activate && python -m pytest -q tests/test_day_clone.py tests/test_headnode_init.py tests/test_headnode_readiness.py tests/test_packaged_defaults.py tests/test_resources_extraction.py tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_versioning.py` -> 161 passed in 4.70s. |  | Focused validation passed before release commit. |
| REL-004 | DYEC | Commit, push, annotated-tag `5.1.31`, and push the tag from an exact clean commit. | OPEN | release_publish | Gate 5 | Codex | Pending. |  |  |
| REL-005 | DYEC | Build and publish clean semver package artifacts for `5.1.31`; verify index and downloads. | OPEN | package_publish | Gate 5 | Codex | Pending. |  |  |

## Evidence Log

- 2026-06-03T14:12:24Z: Gate 0 inventory recorded before staging or release tag creation.
- 2026-06-03T14:14Z: Focused DYEC validation passed with 161 tests.
- 2026-06-03T14:18Z: Post-Gate-0 branch check found `00f329f9` ahead of origin and `docs/plans/20260603T134149Z_dyec5128_cleanup_runtime_env_failures.stdout.txt`; both are included in the release set.
- 2026-06-03T14:21Z: User requested adding the live 384-vCPU partition `bcl2fq-i384-nvme-test` to the DayOA Slurm job partition defaults; released DayOA `2.0.42` and updated current DYEC pins toward `2.0.42`.
- 2026-06-03T14:22Z: User directed ignoring new dirty files from this point unless told otherwise; continuing validation-driver docs under `docs/plans/20260603T132908Z_dyec5128_command_catalog_failed_retries_2_0_41/` are excluded from the `5.1.31` tag.
