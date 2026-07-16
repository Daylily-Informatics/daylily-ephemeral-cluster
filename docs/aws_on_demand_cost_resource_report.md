# On-Demand AWS Cost And Resource Report

`dyec aws audit cost-resources` produces machine-readable cost, resource, tag, budget, lifecycle, cluster, and utilization datasets. It is read-only. It does not create an HTML/Markdown report or change AWS state.

It is strictly one-shot. It contains no scheduler, daemon, watcher, recurring monitor, background task, or continuous polling. API loops are finite pagination loops with token-cycle detection, and the process exits after writing one snapshot.

## First Run

Use explicit dates, identity, cluster tag contracts, filesystem locations, and ParallelCluster regions. The resource-detail window must be no more than 14 days.

```bash
source ./activate

dyec --json aws audit cost-resources \
  --profile lsmc \
  --account-id 108782052779 \
  --start 2026-06-01 \
  --resource-start 2026-07-01 \
  --end 2026-07-15 \
  --control-region us-west-2 \
  --output-dir .daylily/aws-cost-report/runs/20260715 \
  --cache-dir .daylily/cache/aws-cost-report \
  --history-file .daylily/aws-cost-report/history.json \
  --initialize-history \
  --cost-tag-key Project \
  --cost-tag-key lsmc-project \
  --cluster-tag-key parallelcluster:cluster-name \
  --cluster-tag-key aws-parallelcluster-clustername \
  --parallelcluster-executable /Users/jmajor/miniconda3/envs/DAY-EC/bin/pcluster \
  --parallelcluster-region us-west-2 \
  --parallelcluster-region us-east-1 \
  --paid-call-budget 50
```

Remove `--initialize-history` on every later run and use a new empty `--output-dir`. Reuse the same cache and history paths.

## Zero-Live-Call Rerun

An identical request can be reproduced entirely from valid cached responses:

```bash
dyec --json aws audit cost-resources \
  ...same identity, dates, tags, regions, cache, and history... \
  --output-dir .daylily/aws-cost-report/runs/20260715-cache-only \
  --cache-only \
  --paid-call-budget 0
```

A complete reuse reports `request_reuse.live_calls=0`, `paid_live_calls=0`, and `cache_hit_ratio=1.0`. Missing, stale, malformed, or request-mismatched cache data fails hard. `--refresh` explicitly bypasses cache but remains throttled and budget-limited.

## Discovery And Change Handling

- Cost service classes come from Cost Explorer results; the resource query is built from that returned list.
- Resource types are the union of Resource Explorer, the Resource Groups Tagging API, CloudFormation, provider enrichers, and Cost Explorer resource IDs.
- New types are emitted immediately even without an enrichment adapter. Unsupported utilization is explicit.
- The history file classifies types/resources as baseline, appeared, persisting, reappeared, or disappeared.
- A disappeared resource is `unresolved`, not `deleted`, unless provider history proves deletion.
- ParallelCluster reads preserve provider and compute-fleet status, including stopped fleets.

## Tags And Budgets

`resource_tags.csv` contains one row per current resource tag. `service_tag_summary.csv` groups current resources and resource-level cost by service, tag key, and value. `cost_allocation_tag_keys.csv` catalogs active billing tag keys when discovery is enabled.

Each explicit `--cost-tag-key`, each cluster tag key, and each tag key referenced by an AWS Budget filter gets a paginated `cost_by_tag_value.csv` breakdown. Those pages are paid Cost Explorer requests and debit the same paid-call budget.

Budget reads are cached and include budget limits, actual/forecast spend, cost filters/filter expressions, resource tags, notifications, subscribers, and actions. They do not mutate budgets. AWS states that budget monitoring and notifications are free; action-enabled budget configuration and delivered Budget Reports have separate pricing, but this command creates neither.

## Cost Boundary

The command disables SDK automatic retries and debits every live Cost Explorer page before invoking it. It rejects budgets above 300 calls, a hard `$3.00` ceiling at the primary-view `$0.01` request price. The default budget is 50 calls (`$0.50` maximum at that price). Non-Cost-Explorer reads do not consume this paid-call counter.

## Output Files

The output directory includes `summary.json` plus CSVs for service/usage/resource costs, high-cost and untagged resources, current tags and tag-value cost, resource-type changes, lifecycle exceptions, utilization, clusters, CloudFormation stacks, budgets, budget associations, alerts/subscribers/actions, and budget tags.
