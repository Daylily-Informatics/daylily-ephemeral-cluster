# AWS 90-Day Cost Attribution Ledger

Date opened: 2026-06-14T21:35:21Z

## Control

Controlling request: produce a fresh trailing 90-day AWS cost report and separate Terrarium, Aquarium, Dayhoff, Aurora/RDS, and DYEC cluster compute/cost surfaces where the evidence allows it.

Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260614T213521Z_aws_90day_cost_attribution_ledger.md`

Report path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/AWS_90day_cost_attribution_20260614.md`

Asset directory: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/aws_90day_cost_attribution_20260614T213521Z_assets`

Scope:
- AWS profile: `lsmc`
- AWS account: `108782052779`
- AWS caller ARN: `arn:aws:iam::108782052779:root`
- Primary cost metric: `UnblendedCost`
- Analysis window: `2026-03-16` through `2026-06-13` inclusive, implemented as Cost Explorer `Start=2026-03-16`, `End=2026-06-14`.
- Region scope: all enabled commercial regions returned in Gate 0.
- Mutation boundary: no AWS tagging, stopping, deleting, lifecycle, rightsizing, or cleanup action is authorized in this ledger. Findings are report-only.
- Attribution boundary: service/app attribution must be evidence-backed from Cost Explorer tags, resource names/ARNs, CloudFormation/ParallelCluster tags, and live inventory. Ambiguous spend remains unallocated rather than inferred.

## Gate 0 Baseline

- Repo path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Repo status before this task: `## jem-dev...origin/jem-dev`; unrelated untracked SMN12 plan/report artifacts already present under `docs/plans/`.
- Instruction files read: `/Users/jmajor/projects/AGENTS.md`, `/Users/jmajor/projects/lsmc/AGENTS.md`, `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/AGENTS.md`, `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.agents/AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`.
- Safety memory read: `/Users/jmajor/.codex/memories/aws-destructive-changes.md`, `/Users/jmajor/.codex/memories/fallback_and_legacy_and_migration_support_for_code_changes_DO_NOT_UNLESS_TOLD_TO_PLEASE.md`.
- Baseline AWS identity command: `AWS_PROFILE=lsmc AWS_DEFAULT_REGION=us-west-2 aws sts get-caller-identity --output json` -> account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Enabled region command: `AWS_PROFILE=lsmc AWS_DEFAULT_REGION=us-west-2 aws ec2 describe-regions --all-regions --query 'Regions[?OptInStatus==\`opt-in-not-required\` || OptInStatus==\`opted-in\`].RegionName' --output text`.
- Enabled regions: `ap-south-2`, `ap-south-1`, `ca-central-1`, `eu-central-1`, `us-west-1`, `us-west-2`, `af-south-1`, `eu-north-1`, `eu-west-3`, `eu-west-2`, `eu-west-1`, `ap-northeast-3`, `ap-northeast-2`, `ap-northeast-1`, `sa-east-1`, `ap-east-1`, `ap-southeast-1`, `ap-southeast-2`, `ap-southeast-3`, `us-east-1`, `us-east-2`.
- Tooling baseline: `Python 3.9.6`; `aws-cli/1.44.69 Python/3.12.12 Darwin/25.5.0 botocore/1.42.79`.
- Baseline tests: not run at Gate 0 because this task creates a read-only data/report artifact and does not modify runtime code.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Orchestration | Record repo state, instructions, AWS identity, enabled regions, date window, paths, and no-mutation boundary. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 Baseline. |  | Baseline recorded before Cost Explorer and inventory collection. |
| COST-001 | Cost Explorer | Collect and reconcile 90-day spend by day, month, service, region, usage type, operation, and relevant tags. | SUCCESS | contract_test | Gate 1 | orchestrator | Raw payloads under `docs/aws_90day_cost_attribution_20260614T213521Z_assets/raw/`; derived CSVs under `.../data/`; `summary.json` total `$48,343.63`. |  | Cost Explorer collection completed for total, service, region, usage type, operation, service+usage, service+operation, active tag keys, and recent resource-level views. |
| LIVE-001 | Live Inventory | Collect live read-only inventory for material AWS services and regions needed for attribution. | SUCCESS | contract_test | Gate 2 | orchestrator | `docs/aws_90day_cost_attribution_20260614T213521Z_assets/data/live_resources.json` and `.csv`; 156 resources classified. |  | Live inventory completed across enabled regions for EC2/EBS/EIP/NAT/FSx/RDS/ELB/ECS plus S3 buckets. |
| ATTR-001 | Attribution | Tease apart Terrarium, Aquarium, Dayhoff, Aurora/RDS, and DYEC cluster cost surfaces with evidence and explicit unallocated limits. | SUCCESS | feature_implementation | Gate 3 | orchestrator | Report `Attribution Surfaces`, `DYEC / ParallelCluster`, `Dayhoff / TapDB`, `Aurora / RDS`, and `Terrarium And Aquarium`; summary fields `dyec_cluster_tagged_total`, `dayhoff_lsmc_project_total`, `rds_total`, and `recent_resource_costs_by_class_service`. |  | Historical DYEC and Dayhoff/TapDB were separated by active billing tags where present; Terrarium/Aquarium were limited to live inventory and recent resource-level Cost Explorer because historical app tags were not active. |
| PLOT-001 | Visualization | Produce non-pie plots/tables for the report from preserved derived data. | SUCCESS | feature_implementation | Gate 4 | orchestrator | SVGs under `docs/aws_90day_cost_attribution_20260614T213521Z_assets/images/`: `daily_spend.svg`, `top_services.svg`, `top_regions.svg`, `attribution_surfaces.svg`. |  | Non-pie plots generated and linked from the report. |
| REPORT-001 | Report | Write the new Markdown report and preserve raw/derived assets. | SUCCESS | feature_implementation | Gate 5 | orchestrator | `docs/AWS_90day_cost_attribution_20260614.md`; `docs/aws_90day_cost_attribution_20260614T213521Z_assets/data/summary.json`; collector script preserved under `.../scripts/`. |  | Report, raw evidence, derived data, plots, command records, and rerunnable collector are present. |
| FINAL-001 | Acceptance | Terminalize all rows and report whether the ledger and objective are complete. | SUCCESS | contract_test | Gate 5 | orchestrator | All rows in this ledger are terminal. Collector command records: 360 total, 55 expected S3 metadata misses, 0 unexpected command errors. |  | Objective complete: new report produced; attribution limits explicitly documented; no AWS mutations were performed. |

## Terminal Evidence

- Report: `docs/AWS_90day_cost_attribution_20260614.md`.
- Asset directory: `docs/aws_90day_cost_attribution_20260614T213521Z_assets/`.
- Collector: `docs/aws_90day_cost_attribution_20260614T213521Z_assets/scripts/collect_aws_90day_cost_attribution.py`.
- Summary: `docs/aws_90day_cost_attribution_20260614T213521Z_assets/data/summary.json`.
- Total 90-day spend: `$48,343.63`.
- DYEC cluster-name tagged spend: `$27,660.67`; DYEC EC2 compute subset `$16,815.51`; DYEC FSx subset `$10,198.94`.
- Dayhoff/TapDB `lsmc-project` tagged spend: `$2,308.39`; separate `project=dayhoff-all` surface `$1,318.04`.
- RDS/Aurora service total: `$4,641.79`; RDS instance-compute usage-type subset `$4,329.35`.
- Terrarium/Aquarium exact 90-day historical spend is not separable from active Cost Explorer tags; recent resource-level window `2026-06-01` through `2026-06-13` shows Terrarium `$62.07` and Aquarium `$13.70` across compute-adjacent services.
- Live resource classification counts: unallocated `64`, Dayhoff `46`, DYEC cluster `23`, Terrarium `18`, Aquarium `5`.
- AWS command records: `360`; expected metadata misses: `37` `NoSuchLifecycleConfiguration`, `18` `NoSuchTagSet`; unexpected command errors after filtering those expected S3 misses: `0`.
- Repo status after this task still includes pre-existing unrelated untracked SMN12 plan/report artifacts; this task added only `docs/AWS_90day_cost_attribution_20260614.md`, `docs/aws_90day_cost_attribution_20260614T213521Z_assets/`, and this ledger.
- AWS mutation boundary upheld: no tag, stop, delete, lifecycle, rightsizing, or cleanup APIs were called.
