# DYEC 17.0.14 Prompt-First Create Release Ledger

Controlling request: collect every interactive `dyec create` input before the first long-running provisioning wait, publish the next DYEC patch release, update the canonical local checkout, and configure the active `prod-cand-1703` headnode from that exact release.

Ledger path: `docs/plans/20260814T071710Z_dyec_17_0_14_prompt_first_release_ledger.md`

## Gate 0 baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `codex/create-prompts-before-provisioning`, based on exact annotated tag `17.0.13` at `40b2e2acbd432eed287e44e41211afb778c1860d`.
- Owned pre-release changes: `daylily_ec/workflow/create_cluster.py` and `tests/test_workflow.py` only. All other untracked paths reported by `git status --short --branch` are user-owned and excluded from staging.
- Live remote sweep: `git ls-remote --tags origin 'refs/tags/17.*'` found strict maximum `17.0.13`; `gh release view 17.0.14` returned `release not found`. Target is non-v patch `17.0.14`.
- Catalog contract: `DyecBuildCommandSet` documents that `current` is copied for each numeric release. `17.0.14` must preserve the existing `current` DayOA `14.0.14` command set without changing command behavior.
- Focused baseline: four create-workflow tests passed; `python -m py_compile` passed; `git diff --check` passed. Broad pre-existing Ruff debt is outside this focused patch.
- Live target: AWS profile `lsmc`, region `us-west-2`, cluster `prod-cand-1703`; `UPDATE_COMPLETE`, compute fleet `RUNNING`, Ubuntu headnode `i-0a19cb6b471874d56` / `10.0.0.22` currently on exact DYEC `17.0.13`.
- Live workload gate at `2026-08-14T07:20:30Z`: authoritative inventory reports zero controllers and zero Slurm jobs. Sixteen pre-existing idle tmux panes are not modified.
- Existing headnode authentication references were verified without reading credential values: repository-scoped DYEC and DayOA deploy keys plus the managed two-repository GitHub token `dayec/github-token/lsmc-bio-dayoa-dyec` are already installed. Headnode configuration is explicitly authorized; no workflow or Slurm lifecycle action is in scope.

## Control ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DYEC | Freeze the repository, remote-version, release-target, and live-cluster baseline. | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | Baseline above; remote maximum `17.0.13`; target `17.0.14`; user-owned paths excluded. |  | Release and live target are exact. |
| IMP-001 | `dyec create` | Collect all genuinely late interactive choices before the baseline provisioning stack begins. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `daylily_ec/workflow/create_cluster.py`; regression in `tests/test_workflow.py`; focused create tests passed. |  | Render choices and multi-policy IAM selection are prompt-first; subnet values remain deterministic stack outputs. |
| REL-002 | Catalog | Add immutable `17.0.14` snapshot equal to `current` in source and packaged catalogs without changing the DayOA `14.0.14` pin. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `config/daylily_pipeline_command_catalog.yaml` and packaged copy are byte-identical; focused catalog tests prove `17.0.14 == current` and both pin DayOA `14.0.14`. |  | The release has an explicit immutable command-catalog snapshot. |
| REL-003 | Validation | Run focused create, catalog, syntax, parity, and diff checks on the final release tree. | SUCCESS | contract_test | Gate 5 | orchestrator | Seven focused tests passed in 5.54s; `python -m py_compile`, catalog `cmp`, and `git diff --check` passed. |  | Focused release checks are green; unrelated baseline Ruff debt was not changed. |
| REL-004 | GitHub | Commit owned scope, push the feature branch, create and push annotated tag `17.0.14`, and publish the matching GitHub prerelease. | OPEN | config_or_startup_contract | Gate 5 | orchestrator | Pending remote branch, peeled tag, and release URL verification. |  |  |
| LOC-001 | Localhost | Leave the canonical checkout on exact tag/version `17.0.14`. | OPEN | config_or_startup_contract | Gate 5 | orchestrator | Pending detached-tag and `dyec --version` verification. |  |  |
| HN-001 | Headnode | Run supported `dyec headnode configure` for `prod-cand-1703` from exact local `17.0.14`, then verify remote version/configuration. | OPEN | config_or_startup_contract | Gate 5 | orchestrator | Pending current live identity, credential ARN, configure result, and remote verification. |  |  |

## Final report

All rows terminal: no

Objective complete: no
