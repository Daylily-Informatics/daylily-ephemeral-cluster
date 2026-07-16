# Cached AWS API Call Audit

`dyec aws audit api-calls` reproduces the Cost Explorer request-cost and caller-origin analysis without a fixed account window or an unbounded sequence of AWS calls. It emits JSON/CSV evidence only; it does not build a report or dashboard.

## Supported Run

Activate the repository environment, then provide every identity and filesystem boundary explicitly:

```bash
source ./activate

dyec --json aws audit api-calls \
  --profile lsmc \
  --account-id 108782052779 \
  --start 2026-07-01 \
  --end 2026-07-15 \
  --trail-region us-east-1 \
  --resource-region us-west-2 \
  --resource-region us-east-1 \
  --output-dir .daylily/api-call-audit/outputs/20260716T011418Z \
  --cache-dir .daylily/cache/aws-api-call-audit
```

`--start` is inclusive and `--end` is exclusive. The command performs only read operations.

## Cost And Call Controls

- The normal audit shape makes at most one live paid Cost Explorer method call. At the account's observed July 2026 rate of `$0.01` per request, that is approximately `$0.01`.
- The module rejects a paid-call budget above 300, enforcing a `$3.00` ceiling at that observed rate.
- Botocore automatic retries are disabled for this module (`total_max_attempts=1`), so a paid request is not silently repeated by the SDK.
- Live calls are spaced per service: Cost Explorer `1.0s`, CloudTrail `0.5s`, and other read APIs `0.2s` by default.
- Throttling limits request rate. Persistent exact-request caching and the paid-call budget limit request count and Cost Explorer charges.

The Cost Explorer request price is recorded from this account's observed billing evidence. If AWS changes its price, update `OBSERVED_COST_EXPLORER_REQUEST_USD` before treating the dollar ceiling as current.

## Reuse Previously Returned Data

Every request cache key includes the schema version, AWS profile, expected account id, service, region, operation, and canonical exact parameters. The first identity response must match the explicit account id before the module can make the paid Cost Explorer call. The response, collection time, and response digest are stored atomically.

Run the same command again with the same cache directory. The summary's `request_reuse` object reports cache hits, live calls, paid live calls, and throttle sleep. A fully reused run reports:

```json
{
  "cache_hit_ratio": 1.0,
  "live_calls": 0,
  "paid_live_calls": 0
}
```

To guarantee that a run cannot contact AWS, add `--cache-only --paid-call-budget 0`. Missing, stale, corrupt, or mismatched entries fail hard.

```bash
dyec --json aws audit api-calls \
  --profile lsmc \
  --account-id 108782052779 \
  --start 2026-07-01 \
  --end 2026-07-15 \
  --trail-region us-east-1 \
  --resource-region us-west-2 \
  --resource-region us-east-1 \
  --output-dir .daylily/api-call-audit/outputs/20260716T011418Z-cache-only \
  --cache-dir .daylily/cache/aws-api-call-audit \
  --cache-only \
  --paid-call-budget 0
```

`--refresh` bypasses valid cache entries. It is intentionally incompatible with `--cache-only` and remains subject to the paid-call ceiling and live-call throttles.

## Evidence Files

The output directory contains `summary.json` plus CSVs for daily billed operations, the bounded CloudTrail sample, principals, source IPs, caller/user-agent groups, request shapes, mapped EC2 origins, and IAM principal metadata. The cache is separate from these derived files and should be retained between runs.
