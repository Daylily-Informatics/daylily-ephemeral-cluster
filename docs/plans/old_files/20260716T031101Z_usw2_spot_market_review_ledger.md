# us-west-2 NVMe Spot market review ledger

- Ledger timestamp: `2026-07-16T03:11:01Z`
- AWS profile: `lsmc`
- AWS account: `108782052779`
- Region: `us-west-2`
- Evidence window: rolling 72 hours ending at the collection time
- Templates: current working-tree `prod_cluster_intel_spot_us-west-2{a,b,c,d}.yaml`
- Scope: read-only analysis and report generation; no AWS, cluster-template, or runtime changes

## Objective

Assess the current EC2 Spot market for every instance type configured in the five NVMe Slurm partitions (`i96nvme`, `i128nvme`, `i192nvme`, `i384nvme`, and `i192hugenvme`) in each configured `us-west-2` Availability Zone, and identify instance types that should be excluded from clusters built today.

## Gate 0: source and decision contract

| Row | Evidence | Intended use | State |
|---|---|---|---|
| G0.1 | Current working-tree Intel Spot YAMLs for `us-west-2a` through `us-west-2d` | Exact partition membership and allocation configuration | complete |
| G0.2 | `describe-instance-type-offerings` | Structural instance-type offering in each AZ | complete |
| G0.3 | `describe-spot-price-history`, Linux/UNIX, rolling 72 hours | Current and recent market price by type/AZ | complete |
| G0.4 | `get-spot-placement-scores`, eight-node-equivalent target, capacity-optimized assumption | Directional partition-pool capacity signal by AZ | complete |
| G0.5 | CloudTrail `RunInstances`, rolling 72 hours | Account-observed launches, insufficient-capacity errors, and price-cap failures | complete |
| G0.6 | AWS EC2 Spot documentation | Interpretation limits for price history and placement scores | complete |

Decision rules:

1. Recommend **exclude today** when the type is not offered in the template AZ, or when current Spot pricing is above the cluster's effective maximum price and live launch attempts confirm `SpotMaxPriceTooLow`.
2. Recommend **watch / conditional exclude** for repeated capacity failures without successes, because account launch history is workload-correlated rather than a controlled market sample.
3. Recommend **retain** when offered and not blocked by the price ceiling; absence of account attempts is not evidence of unavailability.
4. Use placement score to assess the whole partition pool and AZ, not to claim per-instance-type capacity. AWS does not expose a current per-type capacity score.
5. Do not treat a flat or present price-history series as proof of available capacity.

## Execution rows

| Row | Action | Evidence artifact | State |
|---|---|---|---|
| E1 | Collect template and AWS evidence | `20260716T031101Z_usw2_spot_market_review_snapshot.json` | complete |
| E2 | Produce per-AZ, per-partition, per-type assessment | `20260716T031101Z_usw2_spot_market_review_report_artifact.json` and `20260716T031101Z_usw2_spot_market_review_instance_type_audit.csv` | complete |
| E3 | Package and verify portable HTML report | `20260716T031101Z_usw2_spot_market_review_report.html`; portable verifier passed at 1440 px and 390 px | complete |
| E4 | Confirm no template or AWS mutation occurred | collector source audit contains only STS, EC2 describe/score, and CloudTrail lookup operations | complete |

## Findings

- All 282 configured partition/type/AZ memberships are structurally offered and have Linux/UNIX Spot price history.
- The account sample contains 469 relevant Spot `RunInstances` events: 229 launched instances, 20 insufficient-capacity errors, 255 `SpotMaxPriceTooLow` errors, and no other errors.
- Placement scores by AZ (`2a`, `2b`, `2c`, `2d`):
  - `i96nvme`: `9, 9, 9, 9`
  - `i128nvme`: `6, 3, 2, 1`
  - `i192nvme`: `3, 9, 1, 5`
  - `i384nvme`: `1, 1, 1, 2`
  - `i192hugenvme`: `3, 7, 1, 1`
- Temporary exclusions are limited to 20 partition/type/AZ memberships whose 72-hour minimum stayed above the `$9.99/hour` global ceiling:
  - `us-west-2a`: `i128nvme/x2iedn.metal`; `i192nvme/m8id.48xlarge`; `i384nvme/{m8idb.96xlarge,m8idn.96xlarge,r8id.metal-96xl,r8idb.96xlarge,r8idn.96xlarge}`
  - `us-west-2b`: `i384nvme/{m8idb.96xlarge,m8idn.96xlarge,r8id.96xlarge,r8id.metal-96xl,r8idb.96xlarge,r8idn.96xlarge}`
  - `us-west-2c`: `i384nvme/{m8id.96xlarge,m8idb.96xlarge,m8idn.96xlarge,r8idb.96xlarge,r8idn.96xlarge}`
  - `us-west-2d`: `i384nvme/{m8idb.96xlarge,m8idn.96xlarge}`
- The 12 other currently price-gated memberships remain `RETAIN`: their condition is not a persistent global-cap breach, and some have successful launches in the evidence window.
- `i384nvme` has no healthy Spot AZ today. If required, `us-west-2d` is the least weak Spot choice; the on-demand template is the reliability recommendation.

## Report packaging note

The portable-report delivery wrapper exposed an 8 px headless-Chromium overflow caused by its runtime header using `width: 100vw` while a vertical scrollbar was present. The canonical artifact was built with the bundled packager, the header was constrained to `width: 100%` by `20260716T031101Z_fix_portable_report_scrollbar_css.mjs`, and the bundled verifier then passed the exact embedded artifact at both desktop and mobile widths.

## Closeout

- All rows terminal: yes
- Objective complete: yes
- Mutations performed: none
