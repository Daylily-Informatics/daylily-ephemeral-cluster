# AWS 90-Day Cost Attribution Ledger

Date opened: 2026-06-18T16:00:28Z

## Control

Controlling request: rerun the AWS cost attribution report for today going back 90 days, and recreate the rendered HTML example with SVGs.

Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260618T160028Z_aws_90day_cost_attribution_ledger.md`

Report path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/AWS_90day_cost_attribution_20260618.md`

HTML path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/aws_90day_cost_attribution_20260618T160028Z_assets/html/index.html`

Asset directory: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/aws_90day_cost_attribution_20260618T160028Z_assets`

Scope:
- AWS profile: `lsmc`
- AWS account: `108782052779`
- AWS caller ARN: `arn:aws:iam::108782052779:root`
- Primary cost metric: `UnblendedCost`
- Analysis window: `2026-03-21` through `2026-06-18` inclusive, implemented as Cost Explorer `Start=2026-03-21`, `End=2026-06-19`.
- Region scope: all enabled commercial regions from the report collector.
- Mutation boundary: no AWS tagging, stopping, deleting, lifecycle, rightsizing, or cleanup action is authorized in this ledger. Findings are report-only.
- Attribution boundary: service/app attribution must be evidence-backed from Cost Explorer tags, resource names/ARNs, CloudFormation/ParallelCluster tags, and live inventory. Ambiguous spend remains unallocated rather than inferred.
- Rendering boundary: create a local static HTML report with local SVG files. In-app browser verification was attempted; local file navigation to the new report was blocked by the Browser Use URL policy, so the terminal rendering evidence is static HTML/SVG validation.

## Gate 0 Baseline

- Repo path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Repo status before this task: `## jem-dev...origin/jem-dev`.
- Instruction files read: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/AGENTS.md`.
- Baseline AWS identity command: `AWS_PROFILE=lsmc AWS_DEFAULT_REGION=us-west-2 aws sts get-caller-identity --output json` -> account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Date stamp: `20260618T160028Z`.
- Baseline tests: not run at Gate 0 because this task creates read-only data/report/browser-rendered artifacts and does not modify runtime code.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Orchestration | Record repo state, instructions, AWS identity, date window, paths, and no-mutation boundary. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 Baseline. |  | Baseline recorded before Cost Explorer and inventory collection. |
| COST-001 | Cost Explorer | Collect and reconcile 90-day spend by day, month, service, region, usage type, operation, relevant tags, and recent resource-level costs. | SUCCESS | contract_test | Gate 1 | orchestrator | `summary.json`; `ce_*.json`; total spend `$57,512.08`; command records `361`. |  | Cost Explorer window collected for `2026-03-21` through `2026-06-18` inclusive. |
| LIVE-001 | Live Inventory | Collect live read-only inventory for material AWS services and regions needed for attribution. | SUCCESS | contract_test | Gate 2 | orchestrator | `live_resources.json`; `live_resources.csv`; live resource count `158`. |  | Live read-only inventory captured across enabled commercial regions. |
| ATTR-001 | Attribution | Separate Terrarium, Aquarium, Dayhoff, Aurora/RDS, and DYEC cluster cost surfaces with explicit attribution limits. | SUCCESS | feature_implementation | Gate 3 | orchestrator | DYEC tagged `$34,597.78`; DYEC EC2 compute `$23,450.47`; Dayhoff/TapDB `$3,016.21`; RDS/Aurora service `$5,246.71`; Terrarium recent `$64.85`; Aquarium recent `$14.30`. |  | Historical tag coverage supports DYEC and Dayhoff/TapDB; Terrarium/Aquarium remain recent resource-level plus live-inventory attribution only. |
| HTML-001 | Rendered Report | Recreate the rendered static HTML example with local SVGs. | SUCCESS | feature_implementation | Gate 4 | orchestrator | `html/index.html` size `15,796` bytes; four local SVGs referenced and present: `daily_spend.svg`, `top_services.svg`, `top_regions.svg`, `attribution_surfaces.svg`. |  | Static HTML report and local SVG image assets generated. |
| FINAL-001 | Acceptance | Validate JSON/HTML artifacts, record browser-render outcome, terminalize all rows, and report completion. | SUCCESS | contract_test | Gate 5 | orchestrator | `python3 -m json.tool` passed for `summary.json` and `live_resources.json`; HTML title and `$57,512.08` total present; in-app browser `goto(file://...)` was rejected by Browser Use URL policy. | Browser Use URL policy blocked local file navigation to the new report. | Artifacts complete; browser verification could not be performed through the in-app browser policy surface. |

## Terminal Evidence

- Markdown report: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/AWS_90day_cost_attribution_20260618.md`
- Static HTML report: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/aws_90day_cost_attribution_20260618T160028Z_assets/html/index.html`
- Asset directory: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/aws_90day_cost_attribution_20260618T160028Z_assets`
- Summary JSON validation: `python3 -m json.tool docs/aws_90day_cost_attribution_20260618T160028Z_assets/data/summary.json >/dev/null` passed.
- Live inventory JSON validation: `python3 -m json.tool docs/aws_90day_cost_attribution_20260618T160028Z_assets/data/live_resources.json >/dev/null` passed.
- Static HTML validation: `<title>AWS 90-Day Cost Attribution Report</title>` present; `$57,512.08` present; four `<img>` references present; all four referenced local SVG files exist under `html/images/`.
- Collector command status: `361` AWS command records; `55` nonzero command records, all expected S3 metadata misses (`37` `NoSuchLifecycleConfiguration`, `18` `NoSuchTagSet`); unexpected command errors `0`.
- Mutation boundary check: no AWS tagging, stopping, deleting, lifecycle, rightsizing, or cleanup action was performed.
- Browser outcome: attempted to navigate the claimed in-app browser tab to `file:///Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/aws_90day_cost_attribution_20260618T160028Z_assets/html/index.html`; Browser Use rejected the local-file navigation under its URL policy, so no browser-render claim is made.
