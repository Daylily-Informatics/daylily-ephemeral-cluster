# DRAGEN Headnode Configure Ledger

Date: 2026-07-03

## Control

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Requested action: run DYEC headnode configure on the DRAGEN headnode; if the existing Ubuntu-oriented path fails, create a separate DRAGEN/RHEL-safe path and leave the existing path as-is.
- Profile/region: `lsmc` / `us-west-2`
- Local DYEC version after refresh: `10.0.91`

## Gate 0 Inventory

- `pcluster list-clusters --region us-west-2` under `AWS_PROFILE=lsmc` showed:
  - `ursa-ilmnqc-0703`: `UPDATE_COMPLETE`
  - `testbudgetblock`: `CREATE_COMPLETE`
  - `dragen-f2-pcimg-fsx-2c`: `CREATE_FAILED`, stack `ROLLBACK_FAILED`
  - `jemx3`: `CREATE_COMPLETE`
- The only DRAGEN-named cluster in the current PCluster list is `dragen-f2-pcimg-fsx-2c`.

## Tracking Rows

| ID | Area | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|---|
| CFG-001 | Inventory | Identify reachable DRAGEN headnode | CLOSED | `pcluster describe-cluster-instances --cluster-name dragen-f2-pcimg-fsx-2c`: `{"instances": []}`. EC2 query for `parallelcluster:cluster-name=dragen-f2-pcimg-fsx-2c` returned no running/stopped instances. | No reachable DRAGEN headnode exists for this failed cluster. |
| CFG-002 | Existing configure | Try existing `dyec headnode configure` path first | CLOSED | `dyec headnode configure --profile lsmc --region us-west-2 --cluster dragen-f2-pcimg-fsx-2c`: `Head node instance not found for cluster 'dragen-f2-pcimg-fsx-2c'.` | Existing configure path did not mutate the headnode; target resolution failed before SSM. |
| CFG-003 | DRAGEN-safe path | If existing path fails due to Ubuntu assumptions, add separate DRAGEN/RHEL-safe path | CLOSED | Added `dyec headnode configure-dragen`, which uses the shared configure runner with `remote_user="ec2-user"` while preserving `dyec headnode configure` as the Ubuntu path. | DRAGEN/RHEL path is implemented separately; existing Ubuntu command remains default/unchanged. |
| CFG-004 | Validation | Verify configured headnode command surface | CLOSED | `dyec headnode configure-dragen --help` rendered; `python -m pytest tests/test_headnode_readiness.py tests/test_workflow.py::TestConfigureHeadnode tests/test_cli_registry_v2.py::test_cli_registry_exposes_v2_command_tree_and_policies tests/test_cli_registry_v2.py::test_headnode_configure_uses_workflow_configure tests/test_cli_registry_v2.py::test_headnode_configure_dragen_uses_ec2_user -q`: 23 passed; `ruff check`: passed; `ruff format --check`: passed. | Local DRAGEN-safe command path is validated, but live headnode validation is blocked until a DRAGEN cluster has a resolvable headnode instance. |

## Live Outcome

- `dragen-f2-pcimg-fsx-2c` is `CREATE_FAILED` / stack `ROLLBACK_FAILED` with PCluster failure `OnNodeConfiguredExecutionFailure`.
- PCluster currently reports no instances for `dragen-f2-pcimg-fsx-2c`.
- EC2 inventory found no instances tagged with `parallelcluster:cluster-name=dragen-f2-pcimg-fsx-2c`.
- The only running DRAGEN-named EC2 instance found by name tag was `i-088a7bd0e4f42695d` / `dragen-pcluster-rhel8-migrate-builder` / `f2.6xlarge` / `Red Hat Enterprise Linux`; it is not tagged as a PCluster headnode.
