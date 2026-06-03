# AWS 90-Day Cost Retrospective Multiagent Ledger

Date opened: 2026-05-21T17:35:07Z

## Control

Controlling request: implement the multiagent AWS 90-day cost retrospective and Ursa automation plan, producing a durable control ledger plus `docs/AWS_3month_retrospective_cost_analysis.md`.

Ledger path: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260520T223609Z_aws_90day_cost_analysis_ledger.md`

Report path: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/AWS_3month_retrospective_cost_analysis.md`

Asset directory: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/aws_3month_retrospective_cost_analysis_assets`

Scope:
- AWS profile: `lsmc`
- AWS account: `108782052779`
- AWS caller ARN: `arn:aws:iam::108782052779:root`
- Primary cost metric: `UnblendedCost`
- Analysis window: `2026-02-20` through `2026-05-20` inclusive, implemented as Cost Explorer `Start=2026-02-20`, `End=2026-05-21`.
- Region scope: all enabled commercial regions listed in Gate 0.
- Public mutation boundary: no AWS tagging, stopping, deleting, retention, or cleanup action is authorized in this ledger. Savings targets are report-only.
- Ursa boundary: production automation is documented as a future read-only artifact/API contract; no Ursa dashboard implementation is performed in this execution pass.

## Gate 0 Baseline

- Repo path: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- Repo status before this task: `## codex/analysis-id-export-catalog-validation...origin/codex/analysis-id-export-catalog-validation`
- Pre-existing dirty tracked files not owned by this task: `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`, `tests/test_script_entrypoints.py`.
- Pre-existing untracked paths not owned by this task: `docs/plans/20260520T065706Z_altair_reanalysis_ledger.md`, `fill_in_the_blanks_lims.md`, `tmp/`.
- Instruction files read: `/Users/jmajor/.agents/AGENTS.md`, `AGENTS.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`.
- Memory context read: `/Users/jmajor/.codex/memories/MEMORY.md` lines for durable ledger storage, no pie/donut visuals, Ursa usage/dashboard anchors, and DayEC `lsmc` AWS inventory context.
- Baseline AWS identity command: `AWS_PROFILE=lsmc AWS_DEFAULT_REGION=us-west-2 aws sts get-caller-identity --output json` -> account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Enabled region command: `AWS_PROFILE=lsmc AWS_DEFAULT_REGION=us-west-2 aws ec2 describe-regions --all-regions --query 'Regions[?OptInStatus==\`opt-in-not-required\` || OptInStatus==\`opted-in\`].RegionName' --output text`.
- Enabled regions: `af-south-1`, `ap-east-1`, `ap-northeast-1`, `ap-northeast-2`, `ap-northeast-3`, `ap-south-1`, `ap-south-2`, `ap-southeast-1`, `ap-southeast-2`, `ap-southeast-3`, `ca-central-1`, `eu-central-1`, `eu-north-1`, `eu-west-1`, `eu-west-2`, `eu-west-3`, `sa-east-1`, `us-east-1`, `us-east-2`, `us-west-1`, `us-west-2`.
- Baseline test command: not run at Gate 0 because the task is documentation/data-report generation and does not modify runtime code.
- Multiagent coordination rule: only the orchestrator writes this ledger, the final report, and report assets. Worker agents may perform read-only analysis and report findings back.

## Multiagent Assignments

| Agent | Owned Workstream | Write Scope |
|---|---|---|
| Orchestrator | Ledger, data reconciliation, final report, assets, terminalization | `docs/plans/20260520T223609Z_aws_90day_cost_analysis_ledger.md`, `docs/AWS_3month_retrospective_cost_analysis.md`, `docs/aws_3month_retrospective_cost_analysis_assets/` |
| Cost Explorer Agent | Cost Explorer collection and cost-driver findings | No file writes |
| Resource Inventory Agent | Live regional resource inventory and console-link patterns | No file writes |
| Tag Attribution Agent | Tag classification and untagged-resource findings | No file writes |
| Zombie/Savings Agent | Zombie heuristics and savings-target findings | No file writes |
| Visualization/Report Agent | Non-pie plot/report structure recommendations | No file writes |
| Ursa Automation Agent | Future Ursa read-only artifact/API contract notes | No file writes |

## Terminal Evidence

- Report: `docs/AWS_3month_retrospective_cost_analysis.md`.
- Asset directory: `docs/aws_3month_retrospective_cost_analysis_assets/`.
- Raw Cost Explorer JSON files: `docs/aws_3month_retrospective_cost_analysis_assets/raw/ce_*.json`.
- Derived summary: `docs/aws_3month_retrospective_cost_analysis_assets/data/summary.json`.
- Live resources: `docs/aws_3month_retrospective_cost_analysis_assets/data/live_resources.json`.
- Untagged/gap resources: `docs/aws_3month_retrospective_cost_analysis_assets/data/untagged_live_resources.csv`.
- Zombie/savings candidates: `docs/aws_3month_retrospective_cost_analysis_assets/data/zombie_candidates.csv`.
- Plots: seven SVG files under `aws_usage_report/images/`.
- Read-only evidence: raw Cost Explorer response files under `docs/aws_3month_retrospective_cost_analysis_assets/raw/` and inventory command logs in `docs/aws_3month_retrospective_cost_analysis_assets/data/inventory_commands.json`.
- Total Cost Explorer spend: `$35,043.24`.
- Top services: EC2 Compute `$15,308.47`, FSx `$9,562.84`, S3 `$4,531.77`, EC2 Other `$2,190.19`, RDS `$1,522.72`.
- Region concentration: `us-west-2` `$31,764.92` / 90.6%.
- Current ParallelClusters: `XL-pilot` and `dra-enabled`, both `CREATE_COMPLETE` in `us-west-2`.
- Live inventory: 142 resources in material regions/global S3; low-spend core regional sweep found 0 EC2/EBS/EIP/NAT/FSx/RDS resources in the remaining enabled regions.
- Tag status counts: 41 completely untagged, 31 missing cluster/stack, 28 missing `Name`, 16 missing project, 8 other-tags-only, 18 fully attributed.
- Savings candidates: 18 entries, including two large FSx Lustre filesystems, four unattached 421 GiB EBS volumes, one unassociated EIP, ten NAT gateways, and one large RDS writer review target.
- Expected S3 metadata findings: 32 `NoSuchLifecycleConfiguration` and 21 `NoSuchTagSet`; after filtering those expected metadata misses there were no unresolved focused live-inventory read failures.
- AWS mutation boundary upheld: no tag, stop, delete, lifecycle, or cleanup APIs were called.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Orchestration | Record repo state, dirty files, AWS identity, enabled regions, date window, report paths, and no-mutation boundary. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 Baseline section. |  | Baseline recorded before AWS data collection or report generation. |
| COST-001 | Cost Explorer | Collect and reconcile daily/monthly spend by service, region, usage type, operation, and cost-allocation tags. | SUCCESS | contract_test | Gate 1 | Cost Explorer Agent | Raw Cost Explorer payloads under `docs/aws_3month_retrospective_cost_analysis_assets/raw/`; summary total `$35,043.24`, top services and regions in `data/summary.json`. |  | Cost Explorer collection and reconciliation completed. |
| TAG-001 | Tag Attribution | Collect tag groupings and blank-tag buckets; classify attribution gaps. | SUCCESS | contract_test | Gate 1 | Tag Attribution Agent | Cost Explorer tag files show `Project`, `project`, `lsmc-project`, and `Name` as 100% blank; `parallelcluster:cluster-name` blank bucket is `$11,071.44`. |  | Historical tag-attribution gaps classified. |
| LIVE-001 | Live Inventory | Scan all enabled regions for current cost-bearing resources. | SUCCESS | contract_test | Gate 2 | Resource Inventory Agent | `data/live_resources.json` has 142 resources from material regions/global S3; `data/low_spend_region_sweep.json` records zero core EC2/EBS/EIP/NAT/FSx/RDS resources in remaining enabled regions. |  | Live inventory completed with deep material-region coverage and lightweight all-region core sweep. |
| UNTAG-001 | Tag Attribution | Produce live untagged and mis-tagged resource tables with AWS Console links. | SUCCESS | contract_test | Gate 2 | Tag Attribution Agent | `data/untagged_live_resources.csv` and report section `Live Resources To Tag`; 95 live action resources with console links. |  | Untagged and attribution-gap resources documented. |
| ZOMBIE-001 | Savings | Identify idle, abandoned, or right-sizing targets with evidence. | SUCCESS | legitimate_safety_handling | Gate 3 | Zombie/Savings Agent | `data/zombie_candidates.csv` and report section `Zombie And Savings Candidates`; 18 review targets. |  | Savings targets are report-only; no destructive action performed. |
| PLOT-001 | Visualization | Generate non-pie daily, weekly, monthly, cluster, untagged, and savings plots. | SUCCESS | contract_test | Gate 4 | Visualization/Report Agent | Seven SVG plots under `aws_usage_report/images/`; no pie or donut visuals generated. |  | Non-pie report plots generated and linked from the report and HTML page. |
| URSA-001 | Ursa Automation | Add production automation notes for a future Ursa dashboard integration. | SUCCESS | active_product_contract | Gate 4 | Ursa Automation Agent | Report section `Ursa Production Automation Notes` defines scheduled producer, explicit S3 artifact contract, explicit config keys, read-only API/page shape, and fail-closed behavior. |  | Future Ursa dashboard integration documented only; no Ursa code changed. |
| REPORT-001 | Report | Write `docs/AWS_3month_retrospective_cost_analysis.md`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | `docs/AWS_3month_retrospective_cost_analysis.md` created with executive summary, plots, cost drivers, tag investigation, savings candidates, Ursa automation notes, and evidence appendix. |  | Report written. |
| FINAL-001 | Final Acceptance | Terminalize all rows and report whether all rows are terminal and whether the objective is complete. | SUCCESS | contract_test | Gate 5 | orchestrator | Terminal Evidence section; all rows are terminal. |  | Objective complete: report, assets, and ledger are present; no AWS mutations were performed. |
