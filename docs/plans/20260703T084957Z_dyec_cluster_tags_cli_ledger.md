# DYEC Cluster Tags CLI Ledger

Controlling request: add DYEC CLI support to add and edit cluster tags so Ursa can use tags to decide whether a cluster can accept jobs.

Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260703T084957Z_dyec_cluster_tags_cli_ledger.md`

## Gate 0: Inventory Freeze

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch baseline: `jem-dev...origin/jem-dev`
- Existing dirty files not owned by this change:
  - `config/day_cluster/post_install_rhel8_dragen.sh`
  - `daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh`
  - `config/day_cluster/prod_cluster_dragen_native_ami_rhel8_nofsx.yaml`
  - `config/daylily_ephemeral_cluster_dragen_native_ami_rhel8_2c_nofsx.yaml`
- Instruction files read:
  - `/Users/jmajor/projects/lsmc/AGENTS.md`
  - `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/AGENTS.md`
  - `/Users/jmajor/.codex/AGENTS.md`
  - `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`
  - `/Users/jmajor/.codex/memory.md`
  - `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`
- Existing cluster CLI surface:
  - `dyec cluster list`
  - `dyec cluster describe`
  - `dyec cluster wait`
- Current tag plumbing:
  - Cluster templates render root `Tags:` entries including `aws-parallelcluster-project`, `aws-parallelcluster-clustername`, and `aws-parallelcluster-enforce-budget`.
  - ParallelCluster 3.15 `describe-cluster` model returns `cloudformationStackArn` and `tags`.
  - Existing policy validation includes CloudFormation and tag permissions.
- Live-system boundary:
  - No live cluster tag mutation will be run in this implementation turn.
  - Tests must use mocks only.

## Control Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| TAG-001 | CLI | Add a DYEC cluster tag command that can list, add, and edit existing cluster tags through explicit `--set KEY=VALUE` inputs. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `daylily_ec/cli.py` adds `dyec cluster tags`; `dyec cluster tags --help` renders the command and options. |  | Command lists when no mutation flags are supplied and applies repeated explicit `--set KEY=VALUE` entries. |
| TAG-002 | CLI | Support explicit tag deletion through `--delete KEY` without broad wipe behavior. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `daylily_ec/aws/cluster_tags.py`; `tests/test_cluster_tags.py::test_update_cluster_stack_tags_deletes_explicit_existing_key`. |  | Only named existing keys are deleted; no broad wipe/all-tags mode was added. |
| TAG-003 | AWS helper | Resolve the backing CloudFormation stack from `pcluster describe-cluster` output and fail hard when stack identity is missing. | SUCCESS | legitimate_safety_handling | Gate 1 | orchestrator | `stack_id_from_describe_cluster()` requires `cloudformationStackArn`; `tests/test_cluster_tags.py::test_cluster_tags_cli_fails_when_describe_lacks_stack_arn`. |  | Missing stack identity is a hard CLI error. |
| TAG-004 | AWS helper | Preserve existing stack parameters/template while updating only stack tags; avoid direct EC2/Slurm/job intervention. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `update_cluster_stack_tags()` uses `UsePreviousTemplate=True`, `UsePreviousValue=True` parameters, and CloudFormation `Tags`; mocked tests assert update kwargs. |  | The implementation does not call EC2 tag APIs, Slurm, SSM, job controls, or node controls. |
| TAG-005 | Tests | Add mocked unit and CLI tests for set/edit/delete/list, missing stack identity, no-op, and registry policy. | SUCCESS | contract_test | Gate 1 | orchestrator | `tests/test_cluster_tags.py`; `tests/test_cli_registry_v2.py`; `pytest tests/test_cluster_tags.py tests/test_cluster_info.py tests/test_cli_registry_v2.py -q -> 150 passed`. |  | Mocked tests cover helper and CLI behavior without live AWS mutation. |
| TAG-006 | Docs | Document the new tag command and a suggested Ursa accept-jobs tag pattern. | SUCCESS | contract_test | Gate 1 | orchestrator | `docs/cli_reference.md`; `docs/operations.md`. |  | Docs show `daylily-accept-jobs=true|false` and state DYEC only edits tags, not Slurm state. |
| TAG-007 | Final | Run focused checks and record final terminal row counts. | SUCCESS | contract_test | Gate 5 | orchestrator | `pytest tests/test_cluster_tags.py tests/test_cluster_info.py tests/test_cli_registry_v2.py -q -> 150 passed`; `python -m py_compile daylily_ec/cli.py daylily_ec/aws/cluster_tags.py`; `git diff --check -- ...`. |  | All ledger rows are terminal: 7 SUCCESS, 0 BLOCKED, 0 FAIL. |

## Final Terminal State

- Status counts: 7 SUCCESS, 0 BLOCKED, 0 FAIL, 0 OPEN.
- Live actions: no live cluster tag update, Slurm operation, SSM operation, job control, node drain/resume, or AWS destructive action was run.
- Existing unrelated dirty files listed in Gate 0 were preserved.

