# DYEC Hourly Cost-Center Accounting Ledger

Created: 2026-07-05T00:40:20Z

Controlling request: implement DYEC hourly cost-center accounting using SlurmDBD plus hourly CUR. Cluster AWS Budget checks must use cluster name. Slurm `--comment` is now a required cost-center string. Cost-center usage is allocated hourly by time overlap across distinct active cost centers, with no-job time assigned to reserved `idle`.

## Gate 0: Inventory Freeze

Ledger path: `docs/plans/20260705T004020Z_dyec_hourly_cost_centers_ledger.md`

Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`

Branch/HEAD at inventory:

```text
branch: jemdev10
HEAD: bb75ce01e4a8b42560d667b14e7785c14f2e08d7
git status --short --branch:
## jemdev10
?? docs/plans/20260704T233618Z_testbudgetblock_budget_failure_probe_ledger.md
```

Pre-existing dirty files not owned by this ledger:

- `docs/plans/20260704T233618Z_testbudgetblock_budget_failure_probe_ledger.md` was already untracked before this work.

Sweep commands:

- `rg -n "budget_project|disable-budget|BudgetManager|ensure_cluster_budget|cost-center|cost center|sbatch|slurm-accounting|sacct|CUR|Athena|check_tags|aws-parallelcluster-project|cluster-name" daylily_ec config tests docs pyproject.toml`
- `sed -n '1,430p' daylily_ec/aws/budgets.py`
- `sed -n '1,260p' config/day_cluster/sbatch`
- `sed -n '960,2130p' daylily_ec/workflow/create_cluster.py`
- `sed -n '520,700p' daylily_ec/cli.py`
- `sed -n '4800,5035p' daylily_ec/cli.py`
- `sed -n '1,260p' tests/test_sbatch_wrapper.py`

Baseline findings:

- `daylily_ec/aws/budgets.py` currently describes two budget types: global `daylily-global` and a cluster/project budget named by rendered Slurm project string.
- `_build_budget_dict()` currently filters budget cost on both `user:aws-parallelcluster-project$<project_name>` and `user:aws-parallelcluster-clustername$<cluster_name>`.
- `ensure_cluster_budget()` accepts `budget_name` and currently updates the S3 budget allow-list with that project/budget name.
- `dyec create` currently exposes `--disable-budget-enforcement` and `--budget-project`; the create workflow passes `budget_project` into `REGSUB_PROJECT`.
- `config/day_cluster/sbatch` currently requires `--comment`, treats that value as the AWS Budget name, allows exact `RnD` as an AWS Budget bypass, checks `/fsx/references/runtime_assets/budget_tags/pcluster-project-budget-tags.tsv`, and calls `aws budgets describe-budget --budget-name "$project"`.
- `config/day_cluster/post_install_ubuntu_combined.sh` currently stages `/tmp/jobs/jobs_projects` and cron `check_tags.sh` to tag active compute nodes with `aws-parallelcluster-project=<active comment set>`.
- Slurm accounting code exists in `daylily_ec/aws/slurm_accounting.py`, including `dyec slurm-accounting ensure` and create/scan support in `dyec create`.
- Tests already exist for budgets, create workflow rendering, Slurm accounting provisioning, headnode init, and sbatch wrapper behavior.

Baseline test command: not run before edits; inventory prioritized source capture because the working tree already had an unrelated untracked ledger and the requested change spans multiple runtime surfaces.

Live-system guardrails:

- Profile `lsmc`, preferred Region/AZ `us-west-2b`.
- Validation cluster name format: `dyec-costacct-<UTCSTAMP>`.
- Validation accounting stack name format: `dayec-costacct-<UTCSTAMP>`.
- Ignore accounting DB resources created before `2026-07-04T00:00:00Z`.
- Before creating live validation resources, inventory running clusters and accounting stacks created on or after `2026-07-04T00:00:00Z`.
- Do not create a second validation cluster or DB while the first exists.
- Do not delete live resources without separate destructive-action approval.

Assumptions:

- Hourly CUR is authoritative for billed EC2 compute cost.
- Within an hour, allocation uses Slurm job start/end overlap duration.
- Cost split is equal across distinct active cost-center strings, not CPU- or memory-weighted.
- `idle` is system-owned and always reported.
- Missing accounting, stale usage, missing registry, malformed comments, or missing CUR inputs fail hard.
- Cost-center registry home region defaults to `us-west-2`.

## Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| CC-000 | Orchestration | Gate 0 inventory: dirty state, budget code, create rendering, Slurm accounting code, CUR/Athena state, bootstrap, wrapper, tags. | SUCCESS | contract_test | Gate 0 | Agent 0 Orchestrator | Gate 0 section above records branch, HEAD, dirty baseline, sweep commands, and baseline findings. |  | Inventory captured before runtime edits. |
| CC-001 | Cluster budget semantics | `dyec create` creates/checks an AWS Budget named by cluster name; `--comment` no longer drives budget names; `--budget-project` removed or hard-errors. | SUCCESS | feature_implementation | Gate 2 | Agent 1 | `daylily_ec/aws/budgets.py`; `daylily_ec/workflow/create_cluster.py`; `tests/test_budgets.py`; `tests/test_workflow.py`; live wrapper output checked budget `dyec-costacct-005955`. | Comment/project budget semantics drifted from desired cluster cap model. | Cluster budget names now derive from cluster name; `--budget-project` is a hard-error retired option. |
| CC-002 | Compute node cluster tags | Bootstrap verifies/repairs stable cluster tags on compute nodes: `parallelcluster:cluster-name` and `aws-parallelcluster-clustername`. | SUCCESS | config_or_startup_contract | Gate 2 | Agent 2 | `config/day_cluster/post_install_ubuntu_combined.sh`; payload mirror; live EC2 `i-05f973096abc7ce3a` has both cluster tags set to `dyec-costacct-005955`. | Dynamic project tags were overloaded for both cluster cost and active job project accounting. | Compute nodes keep stable cluster tags; active job cost centers are no longer written to instance cluster/project tags. |
| CC-003 | Cost-center registry and CLI | Add `dyec cost-centers ensure-registry/create/edit/disable/show/list/usage` backed by DynamoDB in default home region `us-west-2`; reserve `idle`. | SUCCESS | feature_implementation | Gate 1 | Agent 3 | `daylily_ec/aws/cost_centers.py`; `daylily_ec/cli.py`; `tests/test_cost_centers.py`; live tables `dayec-cost-centers`, `dayec-cost-center-usage`; live centers `cc005955a`, `cc005955b`, `cc005955d`, `cc005955cap`. | Cost-center metadata and usage needed a global low-latency authority separate from lagged AWS Budgets. | Registry commands and validation rules are implemented; `idle` is system-reserved. |
| CC-004 | Slurm accounting DB live connection | Complete `dyec slurm-accounting ensure` and cluster connection validation; create exactly one post-July-4 accounting DB stack and one validation cluster at a time. | SUCCESS | feature_implementation | Gate 5 | Agent 4 | Inventory found no active post-2026-07-04 `dayec-costacct-*` stacks or `dyec-costacct-*` clusters. `us-west-2b` DB create blocked before DB creation by VPC/IGW service limit. One DB stack was then created in `us-west-2d`: `dayec-costacct-20260705T005955Z`, `CREATE_COMPLETE`, URI `10.0.1.58:3306`. One validation cluster was created: `dyec-costacct-005955`, `CREATE_COMPLETE`, headnode `i-005099e85867081aa`. | Preferred AZ `us-west-2b` baseline stack could not create due account VPC/InternetGateway limits. | Used `us-west-2d` after recording the blocker; no second validation DB or cluster was created. |
| CC-005 | Slurm `sacct` adapter | Add adapter for job id, user, comment, start/end, node list, alloc CPUs, and state; prove live comments/node data when validation cluster exists. | SUCCESS | feature_implementation | Gate 1 | Agent 5 | `daylily_ec/slurm/sacct.py`; `tests/test_sacct_adapter.py`; SSM `c01a9a06-241a-461e-aaf3-93ec97535310`; live jobs `3` and `4` returned `cc005955a`/`cc005955b`, start/end, `i8-dy-price8-1`, alloc CPU, and `COMPLETED` in `sacct`. | SlurmDBD did not persist comments until `AccountingStoreFlags=job_comment` was added. | Bootstrap now appends `AccountingStoreFlags=job_comment`; parser skips `.batch`/step rows. |
| CC-006 | CUR/Athena adapter | Add hourly EC2 cost adapter by instance id and cluster tag; mocked tests pass and live validation records CUR availability or lag blocker. | SUCCESS | feature_implementation | Gate 1 | Agent 6 | `daylily_ec/aws/cur.py`; `tests/test_cur.py`; synthetic allocation used live job times with compute instance `i-05f973096abc7ce3a`; 2026-07-05T09:22:18Z live AWS proof found no CUR source; 2026-07-05T09:37:37Z `dyec cost-centers ensure-cur-export` created `dayec-cur2-hourly`; 2026-07-06T02:25:48Z Data Export refreshed successfully; 2026-07-06T04:30Z Athena table had `259476` rows, `18425` EC2 instance rows, and validation instance rows for `i-05f973096abc7ce3a`; after switching the default CUR tag key to `user_parallelcluster_cluster_name`, the adapter returned `92` rows for cluster `dyec-costacct-005955`. |  | CUR source, normalized CUR 2.0 tag key, and Athena adapter path are live-proven with delivered CUR rows. |
| CC-007 | Allocation engine | Time-weighted hourly allocation: overlapping distinct cost centers split only during overlap; no-job time goes to `idle`. | SUCCESS | feature_implementation | Gate 1 | Agent 7 | `daylily_ec/cost_allocation.py`; `tests/test_cost_allocation.py`; synthetic live-shape run produced `cc005955a=0.003500000 USD for 21.0s`, `cc005955b=0.001666667 USD for 10.0s`, `idle=0.594833333 USD for 3569.0s` for a `$0.60` instance-hour. | Needed a deterministic split independent of AWS tag mutation latency. | Allocation is by distinct active cost-center intervals; no-job time is reported as `idle`. |
| CC-008 | Runtime `sbatch` enforcement | Wrapper requires non-`idle` comment, checks cluster AWS Budget by cluster name, validates cost-center registry/allowance/usage/cap/staleness, and calls real Slurm with one canonical `--comment`. | SUCCESS | config_or_startup_contract | Gate 2 | Agent 8 | `config/day_cluster/sbatch`; payload mirror; `tests/test_sbatch_wrapper.py`; live allow output for jobs `3`/`4`; live negative SSM `3af5ce14-5f15-4311-933d-1a937d935152` returned `DISABLED_RC=1`, `EXCEEDED_RC=1` with Ursa URLs. | Headnode role initially lacked `dynamodb:GetItem`; `sacct` comments initially missing from SlurmDBD. | Added DDB read to pcluster policy templates and live managed policy version `v5`; added `AccountingStoreFlags=job_comment`. |
| CC-009 | Docs, migration, release evidence | CLI docs, migration notes, test matrix, final ledger counts. | SUCCESS | contract_test | Gate 5 | Agent 9 | `README.md`; `docs/cli_reference.md`; `docs/operations.md`; this ledger; `pytest -q` -> `1196 passed, 8 skipped`. | Documentation and evidence needed to track the changed meaning of cluster budget versus cost center. | Final counts below; live validation resources intentionally left running pending separate deletion approval. |
| CC-010 | CUR source provisioning amendment | Add explicit DYEC command to create/validate the missing CUR 2.0 Data Export, S3 policy, Glue table, and Athena partition. | SUCCESS | plan_amendment | Gate 1 | Agent 6 | `daylily_ec/aws/cur_export.py`; `daylily_ec/cli.py`; `tests/test_cur_export.py`; `tests/test_cli_registry_v2.py`; `docs/cli_reference.md`; `docs/operations.md`; live `dyec --json cost-centers ensure-cur-export --profile lsmc` returned bucket/policy/export/database/table/partition `existing`, export `HEALTHY`, latest execution `DELIVERY_SUCCESS`, and `cluster_tag_key=user_parallelcluster_cluster_name`. | The original plan assumed a CUR/Athena source might already exist; live proof showed the account had none. | DYEC now owns an explicit setup path and rejects drift unless `--update-existing-export` or `--adopt-glue-table` is passed. |

## Test Matrix

Planned local tests:

- Budget unit tests proving cluster budget derives from cluster name and cost filters use cluster identity tags instead of active project tags.
- Create workflow tests proving `--budget-project` no longer drives rendering and budget setup is pre-launch.
- Cost-center registry tests for ensure/create/edit/disable/list/show/usage validation.
- Wrapper tests for missing comment, reserved `idle`, unknown cost center, unauthorized user, disabled cost center, exceeded cap, stale usage, exceeded cluster budget, under-cap allowed job, and canonical comment forwarding.
- Slurm adapter fixture tests.
- CUR/Athena adapter fixture tests.
- CUR source setup tests for the Data Exports bucket policy, hourly/resource Parquet export definition, Glue schema conversion, drift handling, and idempotency.
- Allocation fixture tests for full-hour single project, 60-minute plus 10-minute overlap, four concurrent cost centers, same-cost-center duplicate jobs, multi-node jobs, sequential jobs, and `idle`.

Planned live validation:

- Inventory post-2026-07-04 Slurm accounting stacks and `dyec-costacct-*` clusters.
- If no blocker exists, create one accounting DB stack.
- Create one validation cluster connected to that DB.
- Submit small jobs with at least two cost centers.
- Prove `sacct` returns comments, timing, state, and node list.
- Run allocation against synthetic CUR immediately and real CUR when available.
- Confirm wrapper blocks disabled/exceeded cost centers and allows active under-cap cost centers.

## Implementation Notes

- Cluster AWS Budgets are named by cluster name. The budget filter now uses cluster identity tags and does not use Slurm comments.
- `REGSUB_PROJECT` remains rendered to cluster name for legacy ParallelCluster tags, but it is no longer the user-submitted cost-center string.
- `--budget-project` remains visible only as a retired/hard-error compatibility surface; it does not affect budget or Slurm comment behavior.
- `dyec cost-centers` manages DynamoDB registry metadata and usage snapshots in home region `us-west-2` by default.
- Runtime `sbatch` checks cluster AWS Budget first, then the DynamoDB cost-center registry and latest monthly usage snapshot. Enforcement skip only skips the AWS Budget check; comments and cost-center validation remain required.
- Headnode bootstrap adds `AccountingStoreFlags=job_comment` so `sacct` receives Slurm job comments from SlurmDBD.
- Compute bootstrap repairs `parallelcluster:cluster-name` and `aws-parallelcluster-clustername` on compute nodes and no longer uses active job comments to mutate project instance tags.
- The shared `pclusterTagsAndBudget` policy templates now include `dynamodb:GetItem` for `dayec-cost-centers` and `dayec-cost-center-usage`.
- `dyec cost-centers ensure-cur-export` creates or validates the explicit CUR 2.0 source used by cost-center accounting. It uses BCM Data Exports in `us-east-1`, a dedicated account-scoped S3 bucket, Parquet/Parquet overwrite delivery, a Glue/Athena table with the current billing-period partition, and CUR 2.0 `resource_tags['user_parallelcluster_cluster_name']` semantics. Data Exports normalizes EC2 cost-allocation tag `parallelcluster:cluster-name` to `user_parallelcluster_cluster_name`.

## Live Validation Evidence

- Guard inventory before creation found no active post-`2026-07-04T00:00:00Z` validation accounting stacks and no active `dyec-costacct-*` validation clusters. Older `dayec-slurm-accounting-us-west-2d` was pre-cutoff and ignored.
- Preferred `us-west-2b` accounting stack creation failed before a validation DB was created because baseline VPC/InternetGateway quotas were exhausted.
- Created exactly one validation accounting DB stack in `us-west-2d`: `dayec-costacct-20260705T005955Z`, status `CREATE_COMPLETE`, URI `10.0.1.58:3306`, instance `i-089b87fc6d966ec03`.
- Created exactly one validation cluster: `dyec-costacct-005955`, status `CREATE_COMPLETE`, headnode `i-005099e85867081aa`.
- SSM `820b5f53-8d6d-4bd8-96fc-81f556ba880c` proved `ubuntu`, headnode hostname, `/opt/slurm/bin/sbatch`, and `/opt/slurm/bin/sacct`.
- SSM `da44079c-9a46-4ac5-99fb-ecd6686f33cf` proved wrapper checks after IAM policy update: cluster budget `dyec-costacct-005955` at `0.00%`, cost centers `cc005955a` and `cc005955b` under cap. Initial `sacct` comments were blank, which exposed the missing `AccountingStoreFlags=job_comment`.
- SSM `587170bd-f034-4823-8d7a-25ef3ebd0aa2` patched the live validation headnode and proved `AccountingStoreFlags = job_comment`.
- SSM `c01a9a06-241a-461e-aaf3-93ec97535310` submitted post-fix jobs `3` and `4`; `sacct` returned:
  - `3|ubuntu|cc005955a|2026-07-05T01:54:25|2026-07-05T01:54:46|i8-dy-price8-1|1|COMPLETED|00:00:21`
  - `4|ubuntu|cc005955b|2026-07-05T01:54:46|2026-07-05T01:54:56|i8-dy-price8-1|1|COMPLETED|00:00:10`
- SSM `3af5ce14-5f15-4311-933d-1a937d935152` proved disabled and exceeded cost centers fail closed:
  - `cc005955d`: `ERROR: cost center is not active: status=disabled`
  - `cc005955cap`: `ERROR: cost-center monthly cap exceeded: spend=1, cap=1`
- EC2 tag readback found compute node `i-05f973096abc7ce3a` running with `parallelcluster:cluster-name=dyec-costacct-005955` and `aws-parallelcluster-clustername=dyec-costacct-005955`.
- Synthetic live-shape allocation used instance `i-05f973096abc7ce3a`, node `i8-dy-price8-1`, jobs `3`/`4`, and a `$0.60` instance-hour; allocation rows were `cc005955a`, `cc005955b`, and `idle`.
- Real CUR for the validation instance was not queried as terminal proof because CUR data is expected to lag minutes-old EC2 spend; this is recorded as the planned data-lag boundary rather than a fallback.
- 2026-07-05T09:22:18Z CUR proof refresh found this is not just a lag boundary:
  - `aws cur describe-report-definitions --region us-east-1` returned no report definitions.
  - `aws bcm-data-exports list-exports --region us-east-1` returned no exports.
  - `aws glue get-databases` returned no databases in `us-east-1`, `us-east-2`, `us-west-1`, or `us-west-2`.
  - `aws ce get-tags` found no `parallelcluster:cluster-name` or `aws-parallelcluster-clustername` values for `2026-07-05`.
  - Hourly Cost Explorer EC2 queries for `2026-07-05T00:00:00Z` through `2026-07-06T00:00:00Z` returned zero groups and zero `UnblendedCost`, including resource-level queries.
  - Conclusion: real-CUR allocation cannot be proven yet because the source dataset is absent, not merely delayed.
- 2026-07-05T09:37:37Z source provisioning amendment:
  - First `dyec --json cost-centers ensure-cur-export --profile lsmc` attempt failed safely before export creation because AWS rejected `SELECT * FROM COST_AND_USAGE_REPORT` as an invalid Data Exports `QueryStatement`.
  - After changing the export query to select the exact 12 columns DYEC needs, `dyec --json cost-centers ensure-cur-export --profile lsmc` created Data Export `dayec-cur2-hourly`, ARN `arn:aws:bcm-data-exports:us-east-1:108782052779:export/dayec-cur2-hourly-1298e4fd-17f5-4a1d-8426-2e47493e0a45`, bucket `dayec-cur-108782052779-us-east-1`, Glue database `dayec_cur`, table `cur2_hourly`, and partition `2026-07`.
  - Idempotency rerun returned `bucket_action=existing`, `bucket_policy_action=existing`, `export_action=existing`, `database_action=existing`, `table_action=existing`, `partition_action=existing`, and export `StatusCode=HEALTHY`.
  - `aws bcm-data-exports get-export` showed hourly CUR 2.0 with `INCLUDE_RESOURCES=TRUE`, Parquet/Parquet, overwrite delivery, and destination `s3://dayec-cur-108782052779-us-east-1/dayec-cur/dayec-cur2-hourly/`.
  - `aws glue get-partition --database-name dayec_cur --table-name cur2_hourly --partition-values 2026-07` returned location `s3://dayec-cur-108782052779-us-east-1/dayec-cur/dayec-cur2-hourly/data/BILLING_PERIOD=2026-07/` with 12 columns.
  - `aws bcm-data-exports list-executions` returned `[]`, and S3 prefix listing returned `Total Objects: 0`.
  - The Athena adapter query against `dayec_cur.cur2_hourly` for cluster `dyec-costacct-005955` and `2026-07-05` succeeded and returned an empty list, proving the table/query path works but no delivered CUR rows exist yet.
  - 2026-07-05T09:42:28Z final readback remained unchanged: export `HEALTHY`, `list-executions=[]`, S3 `Total Objects: 0`, adapter rows `[]`.
- 2026-07-06T04:30:57Z CUR delivery and final proof:
  - Export `dayec-cur2-hourly` was `HEALTHY` with `LastRefreshedAt=2026-07-06T02:25:48.278000+00:00`.
  - `aws bcm-data-exports list-executions` returned three executions, all `DELIVERY_SUCCESS`; latest execution `dc4bb399-ddb9-366d-a5a3-8bd1f66fc963` was created `2026-07-06T02:21:38.547000+00:00` and last updated `2026-07-06T02:25:48.269106+00:00`.
  - S3 delivery prefix contained `dayec-cur/dayec-cur2-hourly/data/BILLING_PERIOD=2026-07/dayec-cur2-hourly-00001.snappy.parquet` plus manifest, `Total Objects: 2`, `Total Size: 1117662`.
  - Athena count checks returned `259476` total CUR rows and `18425` EC2 instance rows for partition `2026-07`.
  - Delivered CUR rows showed Data Exports normalized `parallelcluster:cluster-name` to `resource_tags` key `user_parallelcluster_cluster_name`; validation compute node `i-05f973096abc7ce3a` had `user_parallelcluster_cluster_name=dyec-costacct-005955` and Spot usage row `USW2-SpotUsage:r6i.2xlarge` with cost `0.0174063228` at `2026-07-05 01:00:00`.
  - After changing the DYEC default CUR tag key to `user_parallelcluster_cluster_name`, `query_hourly_ec2_instance_costs()` returned `92` rows for cluster `dyec-costacct-005955`, including compute node `i-05f973096abc7ce3a` and headnode `i-005099e85867081aa`.
  - Idempotent `dyec --json cost-centers ensure-cur-export --profile lsmc` readback returned `bucket_action=existing`, `bucket_policy_action=existing`, `export_action=existing`, `database_action=existing`, `table_action=existing`, `partition_action=existing`, latest execution `DELIVERY_SUCCESS`, and `cluster_tag_key=user_parallelcluster_cluster_name`.

Live resources left running because no destructive-action approval was given:

- Cluster: `dyec-costacct-005955`
- Accounting DB stack: `dayec-costacct-20260705T005955Z`
- Accounting DB EC2 instance: `i-089b87fc6d966ec03`

## Final Terminal Counts

- Rows terminal: 11 / 11.
- Rows successful: 11 / 11.
- Rows blocked: 0 / 11.
- Local verification: post-normalized-key `source ./activate && pytest -q` -> `1207 passed, 8 skipped in 35.30s`; focused check `source ./activate && pytest -q tests/test_cur.py tests/test_cur_export.py tests/test_cli_registry_v2.py` -> `149 passed`; `ruff check daylily_ec/aws/cur.py daylily_ec/aws/cur_export.py daylily_ec/cli.py tests/test_cur.py tests/test_cur_export.py tests/test_cli_registry_v2.py` -> `All checks passed!`.
- Live validation cluster and accounting DB were not deleted; deletion requires separate explicit destructive approval.
