# Day Clone Executing Entity Flag Ledger

Created: 2026-06-01T13:08:54Z

## Objective

Fix the DayEC workflow bootstrap/clone blocker where the generated headnode
launch script passed `-u <executing-entity>` to `day-clone` even though the
observed `day-clone` CLI contract does not accept that short flag.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster` |
| Branch | `codex/dyec515-full-catalog-20260531` |
| Baseline HEAD | `3b6cc5cc2f01862158138214296737d385f89a94`, tag `5.1.15` |
| Live blocker from handoff | API handoff still works; blocker is the DayEC bootstrap/clone command passing `-u dyec-test` to `day-clone`. |
| Contract inspection | Historical tags before `5.1.6` accepted `--executing-entity` but not `-u`; the durable bootstrap command should use the canonical long flag. |
| Live cluster inspection | `AWS_PROFILE=lsmc pcluster describe-cluster -n dyec5115 --region us-west-2` reported `clusterStatus=CREATE_COMPLETE`, `cloudFormationStackStatus=CREATE_COMPLETE`, head node `i-0092ccb047d51c93b` `running`, and `computeFleetStatus=RUNNING`; `dyec-5115` does not exist. |
| Safety boundary | No live AWS mutation, cluster teardown, DRA delete, or Slurm cancellation was performed. |

## Execution Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DCLONE-001 | Workflow bootstrap | Stop generating `day-clone -u "$EXECUTING_ENTITY"` in headnode launch scripts. | SUCCESS | feature_implementation | Gate 1 | Codex | `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` now emits `day-clone --executing-entity "$EXECUTING_ENTITY"`; `tests/test_script_entrypoints.py` asserts the long flag is present and the short flag is absent. | Generated workflow script used a short option that is not part of the observed live `day-clone` CLI contract. | Bootstrap uses the canonical long flag accepted by older and current helper contracts. |
| DCLONE-002 | Helper contract | Keep source and packaged `day-clone` aligned with the no-short-flag contract. | SUCCESS | contract_test | Gate 1 | Codex | `bin/headnode_utils/day-clone` and `daylily_ec/resources/payload/bin/headnode_utils/day-clone` now expose `--executing-entity` without the `-u` alias; the explicit-entity unit test uses the long flag. | Source had grown a short alias that let tests miss the generated-command mismatch. | Source helper and packaged payload copy match the observed CLI contract. |
| DCLONE-003 | Validation | Run focused tests for clone command generation, explicit executing entity handling, and packaged payload parity. | SUCCESS | contract_test | Gate 5 | Codex | `python -m pytest -q tests/test_day_clone.py tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_workflow_session tests/test_cli_registry_v2.py::test_workflow_launch_defaults_executing_entity_to_cluster` -> `14 passed`; `python -m pytest -q tests/test_packaged_defaults.py tests/test_headnode_init.py::test_packaged_post_install_bootstrap_matches_source --maxfail=1` -> `7 passed`. | Needed regression coverage for the exact command shape and packaged helper copy. | Focused local validation passed. |
| DCLONE-004 | Live status | Monitor current `dyec5115` cluster state without mutating it. | SUCCESS | legitimate_safety_handling | Gate 5 | Codex | `AWS_PROFILE=lsmc pcluster list-clusters --region us-west-2` listed `dyec5115` and `dyec-test`; `describe-cluster -n dyec5115` reported `CREATE_COMPLETE` and compute fleet `RUNNING`; `describe-cluster -n dyec-5115` reported no such cluster. | User referred to `dyec5115`; hyphenated spelling was ambiguous. | Live cluster is up; local fix is not yet applied to it. |

## Final Status

Ledger terminal state: 4 `SUCCESS`, 0 `BLOCKED`, 0 working rows.

Objective state: complete for the local source fix. Live relaunch/reconfigure
of `dyec5115` was not performed in this change.
