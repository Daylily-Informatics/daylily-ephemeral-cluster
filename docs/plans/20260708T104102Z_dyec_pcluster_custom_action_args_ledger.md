# DYEC PCluster Custom Action Args Ledger

Date: 2026-07-08T10:41:02Z

## Control Ledger

Controlling plan: user-attached failed `dyec create --profile lsmc --region-az us-west-2d --cluster-type intel` transcript.
Ledger path: `docs/plans/20260708T104102Z_dyec_pcluster_custom_action_args_ledger.md`

Gate 0 baseline:
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-dev`
- HEAD: `b3e7d8e3 Assert RHEL DRAGEN boot script render contract`
- Git status: clean before this ledger and fix.
- Failed create artifact: `/Users/jmajor/.config/daylily/multi-budget-ck_cluster_20260708103421.yaml`
- ParallelCluster log evidence: `/Users/jmajor/.parallelcluster/pcluster-cli.log` reported `ConfigSchemaValidator` error for `HeadNode.CustomActions.OnNodeConfigured.Args[2]` and all `Scheduling.SlurmQueues[*].CustomActions.OnNodeConfigured.Args[2]`: `Not a valid string.`
- Rendered YAML evidence: `CustomActions.OnNodeConfigured.Args` third element rendered as bare `6.00`, which YAML loads as a number, not a string.
- Source template evidence: `config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_us-west-2d.yaml` contains `- ${REGSUB_SPOT_PRICE_WARN_THRESHOLD}`.
- No live create, cluster delete, Slurm, or workflow action is approved or in scope for this fix. PCluster dry-run validation is allowed because it is non-destructive.

Assumption:
- ParallelCluster custom action `Args` values must be strings. DYEC should render the spot warning threshold as a quoted YAML scalar while preserving the shell script receiving the same text value, `6.00`.

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| PCL-001 | Root cause | Identify why `multi-budget-ck` dry-run failed after render and spot pricing | SUCCESS | config_or_startup_contract | Gate 0 | Codex | `/Users/jmajor/.parallelcluster/pcluster-cli.log` says `Args[2]` is not a valid string; rendered YAML has bare `6.00` |  | PCluster schema rejected numeric custom action args. |
| PCL-002 | Render fix | Ensure DYEC renders `REGSUB_SPOT_PRICE_WARN_THRESHOLD` as a string in cluster YAML | SUCCESS | config_or_startup_contract | Gate 2 | Codex | `daylily_ec/workflow/create_cluster.py` now JSON-quotes the formatted threshold before template substitution. |  | The rendered YAML arg becomes `"6.00"` instead of bare `6.00`. |
| PCL-003 | Tests | Add focused tests proving custom action args remain strings after render | SUCCESS | contract_test | Gate 5 | Codex | `tests/test_workflow.py`, `tests/test_renderer.py`, and `tests/test_spot_pricing.py` assert the threshold substitution/final YAML parse as `"6.00"`. |  | Regression tests cover create workflow substitution, RHEL template rendering, and spot-price YAML rewriting. |
| PCL-004 | Validation | Run focused local tests and non-destructive dry-run validation | SUCCESS | contract_test | Gate 5 | Codex | `source ./activate && pytest tests/test_renderer.py tests/test_spot_pricing.py tests/test_workflow.py -q` -> 144 passed. `AWS_PROFILE=lsmc pcluster create-cluster --cluster-name multi-budget-ck --cluster-configuration /tmp/multi-budget-ck_cluster_20260708103421_fixed.yaml --region us-west-2 --dryrun true` -> `Request would have succeeded, but DryRun flag is set.` |  | Original `Args[2] Not a valid string` schema error is cleared in pcluster dry-run. No live cluster create was run. |

## Final Status

All rows are terminal: 4 `SUCCESS`, 0 `BLOCKED`, 0 `FAIL`.

Objective status: complete for the local/source fix and non-destructive dry-run validation. Live cluster creation was not rerun.
