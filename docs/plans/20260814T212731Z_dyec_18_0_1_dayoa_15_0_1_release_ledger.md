# DYEC 18.0.1 / DayOA 15.0.1 Release Ledger

## Control Ledger

Controlling cross-repository ledger: `/Users/jmajor/projects/lsmc/.codex-worktrees/dayoa-tiddit-native-bundle-15.0.1/docs/plans/20260814T212130Z_dayoa_15_0_1_dyec_18_0_1_release_train_ledger.md`

Ledger path: `docs/plans/20260814T212731Z_dyec_18_0_1_dayoa_15_0_1_release_ledger.md`

### Gate 0: Inventory Freeze

- DYEC release checkout: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-18.0.1-dyoa-15.0.1`, branch `codex/dyec-18.0.1-dyoa-15.0.1`, clean at current `origin/main` commit `e09a4e64a89b9c1e1639c469a42ac90851ef6aa0`.
- DYEC remote numeric-tag maximum is `18.0.0`. The candidate tag will be `18.0.1` and is absent from the remote at inventory time.
- DayOA `15.0.1` is an existing remote annotated tag after merged DayOA PR #110; it resolves to DayOA merge commit `0253dde4983dc522980dffcdeb1498b898821656`.
- Preserved DYEC source checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `codex/prod-cand-1703-seq-run-qc-20260814`, has broad unrelated tracked/untracked state and an unmerged ledger. This release uses the clean checkout only.
- Source sweep: `origin/main` has no `cluster jobs` command. The active DayOA catalog pin set is confined to `repositories.daylily-omics-analysis` and `dyec_builds.current` in `config/daylily_pipeline_command_catalog.yaml` and the packaged payload copy; historical `dyec_builds` entries are not release-pin targets.
- Assumptions and live limits: the previous user request for quick cluster/job inspection authorizes the pending read-only `dyec cluster jobs` command. This release does not launch workflows, mutate AWS state, or manage Slurm jobs; it only uses the central SSM read-only helper for `squeue` summaries.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-001 | CLI | Add the requested `dyec cluster jobs` aggregate read-only queue-count command, docs, and contracts. | SUCCESS | feature_implementation | Gate 1 | Codex | `daylily_ec/cli.py`; `README.md`; `docs/cli_reference.md`; `tests/test_cluster_info.py`; `tests/test_cli_registry_v2.py`; focused pytest -> `257 passed in 27.48s`. |  | The command reports per-cluster total/running/pending/other Slurm jobs through central read-only SSM calls; unavailable cluster states report `CLUSTER_NOT_READY`. |
| DYEC-002 | Catalog | Pin the active DYEC DayOA catalog surfaces to remote annotated DayOA `15.0.1` without rewriting historical provenance. | SUCCESS | config_or_startup_contract | Gate 2 | Codex | Source/payload catalog parity check passed; each active catalog has `120` `15.0.1` references and zero active `14.0.22` references; 100 focused catalog-contract tests passed. |  | Only `repositories.daylily-omics-analysis` and `dyec_builds.current` moved to `15.0.1`; historical `17.0.29` remains explicitly pinned to `14.0.22`. |
| DYEC-003 | Release | Commit, push, merge, and create/push the annotated DYEC `18.0.1` tag. | SUCCESS | config_or_startup_contract | Gate 5 | Codex | PR #104 merged at `da72fb47f629beca3d7d64794264fe5daa609b30`; remote `18.0.1` tag object peels to the same commit and is type `tag`. |  | DYEC `18.0.1` is a published annotated release. |
| DYEC-004 | Validation | Verify CLI/contracts, source-payload pin parity, PR checks, merge commit, and remote tag. | SUCCESS | contract_test | Gate 5 | Codex | `pytest` -> `257 passed` and `100 passed`; catalog parity assertion, `compileall`, and `git diff --check` passed; remote `main` semantic pin check passed; Ruff reports no diagnostics on changed Python lines. |  | Remote `main` has active DayOA `15.0.1` pins, source/payload blobs match, and historical `17.0.29` remains `14.0.22`. |

## Final Report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 4
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

Released tag: DYEC `18.0.1` -> `da72fb47f629beca3d7d64794264fe5daa609b30`
