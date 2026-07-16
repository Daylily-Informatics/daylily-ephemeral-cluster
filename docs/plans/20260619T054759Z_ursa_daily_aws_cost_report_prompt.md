# Prompt For Ursa Agent: Daily AWS Cost Attribution Report

Use this prompt to ask an Ursa/Dayhoff implementation agent to turn the current one-off AWS 90-day cost report into a daily, authenticated, rolling report surface.

## Prompt

You are working in the LSMC/Dayhoff/Ursa service workspace. Please determine whether Ursa already auto-creates and serves the AWS 90-day cost attribution HTML report once per day. If it does not, implement it.

The desired result is a daily scheduled producer plus a read-only Ursa-hosted report view. Do not put Cost Explorer, EC2, RDS, S3, FSx, ECS, or other AWS inventory calls on the user-facing request path. Web requests must serve prebuilt artifacts only.

Reference artifacts from the current manual report:

- Example rendered HTML report:
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/aws_90day_cost_attribution_20260618T160028Z_assets/html/index.html`
- Example local SVG assets:
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/aws_90day_cost_attribution_20260618T160028Z_assets/html/images/`
- Example producer/collector code:
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/aws_90day_cost_attribution_20260618T160028Z_assets/scripts/collect_aws_90day_cost_attribution.py`
- Example markdown report:
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/AWS_90day_cost_attribution_20260618.md`
- Example execution ledger:
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260618T160028Z_aws_90day_cost_attribution_ledger.md`
- Older architectural note recommending this exact producer/consumer split:
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/AWS_3month_retrospective_cost_analysis.md`, section `Ursa Production Automation Notes`.

Important: the example collector is a seed, not production-ready as-is. It currently has date constants hardcoded for the June 18 manual run. Production code must compute the trailing 90-day Cost Explorer window from the scheduled run date, using Cost Explorer's exclusive `End` date correctly. Include a clear generated timestamp and report window in each output.

Requirements:

1. Inspect existing Ursa/Dayhoff code first and preserve local patterns.
2. If this report is already generated and hosted daily, document the existing producer, schedule, storage path, retention policy, route, and validation evidence instead of adding a duplicate system.
3. If it is not already happening, implement a daily producer that:
   - runs once per day after Cost Explorer data is expected to settle,
   - uses explicit configuration only,
   - fails hard on missing config, missing credentials, malformed date/window input, missing bucket/prefix, or failed artifact validation,
   - uses a dedicated read-only AWS IAM role/profile with only the AWS read permissions needed for Cost Explorer and inventory,
   - performs no AWS mutations,
   - writes static HTML, SVGs, JSON, CSV, raw Cost Explorer evidence, and command records.
4. Publish artifacts to an explicitly configured private S3 bucket/prefix, with this shape:

```text
current/index.html
current/images/*.svg
current/data/summary.json
current/data/live_resources.json
current/data/live_resources.csv
current/data/recent_resource_costs.csv
current/data/command_records.json
current/report.md
runs/YYYYMMDD/index.html
runs/YYYYMMDD/images/*.svg
runs/YYYYMMDD/data/summary.json
runs/YYYYMMDD/data/live_resources.json
runs/YYYYMMDD/data/live_resources.csv
runs/YYYYMMDD/data/recent_resource_costs.csv
runs/YYYYMMDD/data/command_records.json
runs/YYYYMMDD/report.md
```

5. Keep a rolling series of immutable dated runs. Add retention through explicit config, for example `cost_report_retention_days` or `cost_report_keep_runs`, and document whether retention is enforced by producer deletion, S3 lifecycle, or no deletion yet. Do not delete old runs unless the retention policy is explicit and approved for the target bucket.
6. Add a read-only Ursa route/API, such as:

```text
GET /usage/aws-cost/
GET /usage/aws-cost/runs/{run_id}/
GET /api/v1/aws-cost-report/current
GET /api/v1/aws-cost-report/runs
```

7. The Ursa route must read only from the configured artifact bucket/prefix. It must show explicit `missing`, `stale`, and `error` states when artifacts are absent, too old, or invalid. It must include generated timestamp, run id, report window, stale status, total cost, key attribution surfaces, and links to the current static HTML and dated archived runs.
8. Put the report behind the existing LSMC/Dayhoff browser auth pattern. Ursa's runtime contract uses an external broker; do not invent a separate Basic Auth/shared-password path.
9. Add tests proving:
   - missing required config fails closed,
   - date/window calculation uses a trailing 90-day window and Cost Explorer exclusive `End` correctly,
   - producer writes both `current/` and `runs/YYYYMMDD/`,
   - static HTML references local SVGs that exist,
   - stale/missing artifacts render explicit UI/API states,
   - Ursa request handlers do not call AWS Cost Explorer or inventory APIs,
   - retention behavior matches explicit config and does not silently delete without configuration.
10. Add durable docs under the appropriate repo `docs/plans/` path describing the schedule, IAM role/profile, bucket/prefix, retention, route URLs, validation commands, and no-mutation boundary.

Suggested config keys:

```yaml
aws_cost_report_bucket: <required>
aws_cost_report_prefix: <required>
aws_cost_report_region: <required>
aws_cost_report_role_arn_or_profile: <required>
aws_cost_report_max_age_hours: <required>
aws_cost_report_retention_days: <required-or-explicitly-unset>
aws_cost_report_schedule: <required>
```

Acceptance criteria:

- A fresh daily run can be triggered manually and by schedule.
- The producer writes a complete dated run and updates `current/`.
- The generated `current/index.html` renders with local SVGs.
- Ursa serves the current report and lists archived runs for authorized LSMC users.
- A stale or missing report is visible as a stale/missing state, not as an empty dashboard.
- The user-facing route never makes live AWS billing/inventory calls.
- No AWS resources are mutated by the report producer except writing report artifacts to the explicitly configured report bucket/prefix.
- Implementation is covered by focused tests and a durable ledger/doc.

Do not use fallback behavior, inferred defaults, service-side bucket discovery, public S3 exposure, or ad hoc credentials. Missing configuration must stop the job with a clear error.

