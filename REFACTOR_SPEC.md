1. Executive Diagnosis

bin/daylily-create-ephemeral-cluster is a single, stateful Bash monolith that mixes four concerns that should be separable but currently are not:

Config resolution: “triplet” config semantics, defaults, auto-select behavior, config patching, and snapshot emission.

Preflight validation: toolchain checks, AWS identity + permissions checks, quota checks, and region-scoped S3 bucket validation.

Glue orchestration: baseline artifact ensurement (VPC/subnets via CFN), YAML rendering, spot heuristics, pcluster invocation, monitoring, and post-create actions.

Policy attachments: budgets and heartbeat wiring, plus IAM patching/creation that is not owned by pcluster.

This architecture is fragile because correctness depends on incidental shell behaviors (parsing aws CLI output, grep filtering, yq flavor differences, sourced scripts exporting variables), and because it provides no formal state model for “what we intended” vs “what exists now” (drift). It is also hard to test because logic is not structured as pure functions.

Refactor target is a Python control plane that preserves all behavior but makes it explicit, deterministic, and testable, while keeping ParallelCluster as the single authority for cluster-scoped resources (cluster stack, FSx, nodes, Slurm, cluster IAM roles). The refactor moves:

All glue/policy/validation/IAM patching into Python modules with a strict execution pipeline.

All resource creation/mutation performed by the current scripts into either:

Layer 1 (baseline prerequisites: CFN VPC stack, IAM prerequisites) or

Layer 3 (runtime policy resources: budgets, heartbeat SNS + scheduler, config artifacts).

All cluster resources defined in the pcluster YAML remain under pcluster control (no standalone CFN introduced for those).

A local, deterministic StateStore and DriftDetector will be added for Layer 1 and Layer 3 resources without introducing any new AWS persistence layer.

2. Resource Ownership Table
AWS resource type	Who manages it today	Who manages it after refactor	Justification
ParallelCluster cluster (CloudFormation stack, cluster API objects)	pcluster (invoked by create script)	pcluster	Must remain authoritative engine for cluster create/update/delete. No external CFN allowed for cluster-managed resources.
EC2 instances / ASGs / launch templates for head + compute	pcluster	pcluster	Defined in pcluster YAML. Preserve exactly.
FSx for Lustre filesystem	pcluster (defined in YAML SharedStorage)	pcluster	Must stay in pcluster YAML; do not create separately.
Slurm install/configuration	pcluster	pcluster	Explicit constraint.
Cluster-scoped IAM roles (headnode/compute instance roles, etc.)	pcluster	pcluster	Explicit constraint.
Baseline VPC + subnets + NAT + IGW + routes + EIP	bin/init_cloudstackformation.sh via CFN template config/day_cluster/pcluster_env.yml (triggered by create script when missing)	Layer 1: dayctl infra ensure-network (Python) using the same CFN template	Script already provisions via CFN; must remain outside pcluster and be preserved. Refactor only orchestration.
IAM managed policy pclusterTagsAndBudget	Created by CFN baseline stack (conditional CreatePolicy)	Layer 1 (same CFN, same policy name)	Already provisioned by scripts. Must remain baseline and re-used.
IAM managed policy pcluster-omics-analysis	Created directly in create script if missing	Layer 1 (Python IamPolicyEnsurer.ensure_pcluster_omics_analysis_policy)	Direct IAM mutation in create script must move to Layer 1 or 3. This is baseline.
IAM managed policy DaylilyGlobalEClusterPolicy	bin/admin/daylily_ephemeral_cluster_bootstrap_global.sh (README prerequisite)	Layer 1: dayctl infra bootstrap-account	One-time prerequisite already required; formalize as command, do not expand scope.
IAM managed policy DaylilyRegionalEClusterPolicy-<region> and DaylilyPClusterLambdaAdjustRoles	bin/admin/daylily_ephemeral_cluster_bootstrap_region.sh	Layer 1: dayctl infra bootstrap-region	Same as above, no expansion.
IAM group membership (daylily-ephemeral-cluster group)	Bootstrap scripts	Layer 1 bootstrap commands	Already implied required.
EC2 KeyPairs	Pre-existing, selected/validated in create script	Layer 3 (validated only)	Must not be created; preserve selection + local PEM validation logic.
Region-scoped S3 reference buckets (*-omics-analysis-<region>)	Pre-existing, validated in create script	Layer 3 (validated only)	Must exist prior; strict validator gating cluster create.
S3 object s3://<bucket>/data/budget_tags/pcluster-project-budget-tags.tsv	Created/updated by bin/create_budget.sh	Layer 3 BudgetManager.update_budget_tags_file	Script mutates this; must be preserved as part of budget policy logic.
AWS Budgets: daylily-global and da-<az>-<cluster> + notifications	Created/updated by bin/create_budget.sh	Layer 3 BudgetManager.ensure_budget	Script creates budgets pre-cluster; preserve exactly.
SNS topic daylily-<cluster>-heartbeat + email subscription	bin/helpers/setup_cluster_heartbeat.py	Layer 3 HeartbeatManager.ensure_heartbeat	Script creates/updates; must be preserved and formalized.
EventBridge Scheduler schedule daylily-<cluster>-heartbeat	bin/helpers/setup_cluster_heartbeat.py	Layer 3 HeartbeatManager.ensure_heartbeat	Same.
IAM role for scheduler to publish to SNS (eventbridge-scheduler-to-sns)	Created by bin/admin/create_scheduler_role_for_sns.sh and auto-resolved/created by create script	Layer 1 HeartbeatRoleEnsurer.ensure_role (Python)	Direct IAM creation path exists today. Must remain as baseline prereq or ensured before heartbeat creation.
3. Functionality Parity Table

Legend: “Current location” line ranges are approximate anchors in bin/daylily-create-ephemeral-cluster based on repository snapshot.

Behavior in bin/daylily-create-ephemeral-cluster	Current implementation location	Refactored location (class, method, CLI)	Notes
Bash version guard (ensure bash >= 4; exec conda bash if needed)	L4-L15	bin/daylily-create-ephemeral-cluster (thin wrapper)	Keep as wrapper or replace with Python re-exec logic. Wrapper is acceptable because it is not infrastructure orchestration.
Ensure DAY-EC conda env active	L17-L22 + bin/helpers/ensure_dayec.sh	Wrapper: bin/daylily-create-ephemeral-cluster OR Python ToolchainValidator.ensure_dayec()	If moved to Python, do not attempt in-process “activation”; re-exec via conda run if needed.
CLI argument parsing: --region-az, --pass-on-warn, --debug, --profile, --config, --repo-override	~L240-L360 and elsewhere	daylily_ec.cli:create_ephemeral_cluster_main(argv)	Preserve flags and semantics. --repo-override remains repeatable and validated.
Validate config file is provided and has required top-level structure	~L320-L390	TripletConfigLoader.load_and_validate(path)	Preserve fatal errors and messages.
yq flavor detection + wrapper functions	~L90-L220	Removed	Python YAML parsing replaces yq. Only keep yq checks if other legacy scripts still called.
Triplet parsing: action/default/set_value formats (string/list/map)	~L560-L640	TripletConfig.parse_triplet(node) -> Triplet	Must preserve normalization: "null"/"None" -> "", True/False -> "true"/"false".
Ensure required config keys exist, patch config file	~L640-L700 + ensure_config_key	TripletConfig.ensure_required_keys(write_back=True)	This is a real behavior (mutates the config file). Must remain.
Auto-select semantics with DAY_DISABLE_AUTO_SELECT	should_auto_apply_config_value ~L489-L520	TripletResolver.should_auto_apply(action, set_value, env)	Preserve: if set_value present and auto-select enabled, use it even if action != USESETVALUE.
Compute resource max counts prompts (8I/128I/192I)	~L1160-L1230	CreateClusterWorkflow.resolve_capacity_config()	Preserve prompt defaults and final config values.
Toolchain prerequisite check (bin/check_prereq_sw.sh)	~L1230-L1275	ToolchainValidator.validate_versions()	Preserve pass-on-warn behavior.
pcluster version check equals 3.13.2	~L1260-L1275	ToolchainValidator.validate_pcluster_version(expected="3.13.2")	Preserve warn vs fail logic.
AWS identity check (sts get-caller-identity)	~L1290-L1315	AwsIdentityValidator.validate_credentials()	Must be first AWS call in preflight.
Derive AWS user name from STS Arn	~L1278	AwsContext.from_sts().aws_cli_user	Preserve behavior for user ARNs. If assumed-role ARN, use last path segment.
Check required Daylily managed policies attached to user or group	~L1319-L1365	IamPermissionValidator.check_daylily_policies()	Preserve: prompt “continue anyway?” unless --non-interactive (new) then fail.
Service Quota checks (on-demand/spot/vpc/eip/nat/igw)	~L1370-L1455	QuotaValidator.run_all()	Must output deterministic JSON report. Preserve spot vCPU calculation and “press enter to continue” gating.
Ensure IAM managed policy pcluster-omics-analysis exists	~L1460-L1486	IamPolicyEnsurer.ensure_pcluster_omics_analysis_policy()	Use boto3 IAM, idempotent.
SSH key pair discovery and selection (ed25519, name contains “omics”)	~L1487-L1595	KeyPairSelector.select_keypair()	Preserve: validate local pem file exists and chmod 400.
S3 bucket discovery, filter by name includes “omics-analysis” and region match	~L1600-L1670	S3BucketSelector.select_reference_bucket()	Preserve region match behavior: None means us-east-1.
Verify bucket contents with daylily-omics-references.sh verify --exclude-b37	~L1670-L1705	S3BucketValidator.verify_reference_bundle()	Hard gate: never allow cluster create if this fails.
Baseline subnet existence checks	~L1710-L1735	NetworkBaselineInspector.inspect_subnets()	Preserve: if both missing, create baseline stack; if one missing, fail.
Baseline CFN stack create/update via bin/init_cloudstackformation.sh	~L1735-L1740	CloudFormationStackEnsurer.ensure_pcluster_env_stack()	Use same config/day_cluster/pcluster_env.yml. Preserve stack naming rules and parameters.
Public subnet selection (with triplet preselection)	~L1740-L1800	SubnetSelector.select_public_subnet()	Preserve DAY_DISABLE_AUTO_SELECT behavior.
Private subnet selection (with triplet preselection)	~L1800-L1860	SubnetSelector.select_private_subnet()	Same.
Select IAM policy ARN for pclusterTagsAndBudget	~L1860-L1910	IamPolicySelector.select_pcluster_tags_policy()	Preserve single-policy auto-select logic.
Cluster name prompt + validation	~L1910-L1965	ClusterNameResolver.resolve()	Preserve regex and length limit.
Budget email prompt + validation	~L1965-L1995	BudgetEmailResolver.resolve()	Preserve email regex.
Ensure global budget exists (daylily-global), else create via bin/create_budget.sh	~L1995-L2035	BudgetManager.ensure_global_budget()	Must preserve thresholds 25,50,75,99 and S3 tag file update.
Ensure cluster budget exists, else create	~L2035-L2105	BudgetManager.ensure_cluster_budget()	Must preserve naming and threshold 75.
Budget enforcement prompt (skip/enforce)	~L2105-L2145	BudgetEnforcementResolver.resolve()	Must preserve tag behavior in YAML.
Cluster template YAML selection (default prod_cluster.yaml)	~L2145-L2185	ClusterTemplateResolver.resolve_path()	Preserve defaulting via template_defaults.
Headnode instance type selection	~L2185-L2215	HeadnodeInstanceTypeResolver.resolve()	Preserve choices and defaults.
FSx size selection	~L2215-L2235	FsxSizeResolver.resolve()	Preserve numeric validation.
Enable detailed monitoring selection	~L2235-L2275	MonitoringResolver.resolve()	Preserve USESETVALUE quick-fix behavior.
Delete local root selection	~L2275-L2305	LocalRootDeletionResolver.resolve()	Preserve semantics.
FSx retain/delete selection	~L2305-L2325	FsxDeletionPolicyResolver.resolve()	Preserve Retain vs Delete.
Heartbeat email/schedule prompt + validation	~L2220-L2330 (overlapping)	HeartbeatConfigResolver.resolve()	Must preserve default to budget email and schedule regex.
Resolve or create scheduler role ARN	resolve_or_create_heartbeat_role ~L60-L115	HeartbeatRoleEnsurer.resolve_or_create()	Preserve env var probing, role-name probing, and fallback to create script behavior.
Spot allocation strategy selection	~L2310-L2335	SpotAllocationResolver.resolve()	Preserve defaults and options.
Render cluster YAML substitutions (envsubst equivalent)	~L2385-L2475	PclusterConfigRenderer.render_template()	Must replace ${REGSUB_*} tokens exactly; write init template artifact.
Run calcuate_spotprice_for_cluster_yaml.py to set SpotPrice	~L2475-L2510	SpotHeuristics.apply_spot_prices()	Keep bump price default 4.14 and AZ/profile inputs. Can import existing module or invoke as subprocess.
pcluster create-cluster --dryrun true and parse success message	~L2510-L2535	PclusterRunner.dry_run_create()	Must preserve success criteria and DAY_BREAK=1 early exit behavior.
pcluster create-cluster real invocation	~L2535-L2545	PclusterRunner.create_cluster()	No reimplementation.
Watch cluster creation status loop with 5 warning tolerance	~L2545-L2565	ClusterCreationMonitor.wait_for_create_complete()	Preserve 5 consecutive failure threshold.
Headnode configuration (clone repo, install miniconda, init env, apply repo overrides)	~L2565-L2615 + bin/daylily-cfg-headnode	HeadnodeConfigurator.configure()	Initial implementation can call existing script; phase 2 converts it to Python while keeping SSH behavior.
Heartbeat wiring (SNS + scheduler)	~L2615-L2650 + bin/helpers/setup_cluster_heartbeat.py	HeartbeatManager.ensure_heartbeat()	Keep boto3 implementation, but integrate into control plane and state.
Persist run artifacts: final config snapshot, resolved CLI config, next-run template	~L2650-L2695	RunArtifactsWriter.write_all()	Must preserve file naming patterns and contents.
Print login command (pem + headnode IP)	~L2695-L2705	OutputPrinter.print_headnode_login()	Must not depend on sourced shell var. Derive IP from pcluster describe or state.
4. Target Architecture
Layer 1: Baseline Prerequisites (only resources current scripts create)

Scope: AWS artifacts that exist outside a single ephemeral cluster, created by existing scripts today.

Managed by: dayctl infra ... commands (Python) using boto3 + existing CFN templates and IAM policy docs.

Resources included (must match current behavior):

CloudFormation stack created from config/day_cluster/pcluster_env.yml:

VPC, public subnet, private subnet, route tables, IGW, NAT gateway, EIP.

Optional managed policy pclusterTagsAndBudget (controlled by CreatePolicy parameter).

IAM managed policy pcluster-omics-analysis created by create script.

IAM policies and group membership from README bootstrap scripts:

DaylilyGlobalEClusterPolicy

DaylilyRegionalEClusterPolicy-<region>

DaylilyPClusterLambdaAdjustRoles

Group daylily-ephemeral-cluster and user membership.

IAM role eventbridge-scheduler-to-sns and inline policy for publishing to SNS (only as currently created via create_scheduler_role_for_sns.sh).

Forbidden expansions in Layer 1:

No new networking topology, no new VPCs beyond what pcluster_env.yml already defines.

No new persistent AWS state store (DynamoDB/S3-as-database) beyond current usage.

No Terraform/CDK.

Layer 2: Cluster Profile (ParallelCluster-owned)

Scope: All cluster-scoped resources expressed in pcluster YAML templates and executed by pcluster.

Managed by: pcluster only.

Artifacts:

config/day_cluster/prod_cluster.yaml (and any existing alternate templates).

Node bootstrap scripts referenced by YAML from S3 (e.g., cluster_boot_config/post_install_ubuntu_combined.sh).

Spot heuristics inputs (placeholders like CALCULATE_MAX_SPOT_PRICE).

Explicit rule:

Anything defined in pcluster YAML stays in pcluster YAML.

Do not move FSx, cluster IAM roles, head/compute provisioning, or Slurm into standalone CFN.

Layer 3: Control Plane (Python)

Scope: Glue, validation, and policy logic.

Managed by: a Python CLI (control plane) that:

Resolves config triplets.

Runs deterministic preflight.

Ensures Layer 1 prerequisites (idempotently).

Renders pcluster YAML and applies spot heuristics.

Calls pcluster create-cluster.

Applies optional policies (budgets, heartbeat).

Writes local state + drift signals.

Forbidden expansions in Layer 3:

No independent CFN stacks for anything pcluster already manages.

No custom orchestrator for compute provisioning (no reimplementing pcluster).

No new long-lived AWS resources for state management.

5. Repository Restructuring Plan
Keep (but re-home) existing assets

Keep config/day_cluster/*.yaml and the pcluster YAML templates unchanged except for clearly flagged, backward-compatible additions.

Keep bin/helpers/setup_cluster_heartbeat.py and watch_cluster_status.py initially; later pull into package.

Keep CloudFormation template config/day_cluster/pcluster_env.yml unchanged.

Add a Python package for the control plane

Add daylily_ec/ as a first-class package (keep daylib/ intact).

Proposed layout:

daylily_ec/
  __init__.py
  cli.py
  workflow/
    create_cluster.py
  config/
    triplets.py
    models.py
  aws/
    context.py
    iam.py
    ec2.py
    s3.py
    quotas.py
    budgets.py
    cloudformation.py
    heartbeat.py
  pcluster/
    runner.py
    monitor.py
  render/
    substitutions.py
    renderer.py
  state/
    store.py
    models.py
    drift.py
  artifacts/
    writer.py
  util/
    prompt.py
    subprocess.py
    logging.py

Modify packaging

Update pyproject.toml [tool.setuptools.packages.find] include to include daylily_ec*.

Add dependencies:

ruamel.yaml (only if you need formatting preservation; otherwise use pyyaml already present).

Keep setup.py script installation behavior.

Replace shell orchestration entrypoint

bin/daylily-create-ephemeral-cluster becomes either:

A thin Bash wrapper that ensures DAY-EC and execs Python, OR

A Python script that re-execs itself via conda run if needed.

All orchestration logic moves out of Bash and into daylily_ec.workflow.create_cluster.

6. Control Plane Specification
CLI surface (deterministic)

Primary preserved entrypoint:

bin/daylily-create-ephemeral-cluster

It must accept the same flags:

--region-az <az> (required)

--profile <aws_profile> (optional, default from env or prompt behavior preserved)

--config <path> (optional; prompt if missing like today)

--pass-on-warn (optional)

--debug (optional)

--repo-override <repo_key:ref> (repeatable)

Additions allowed (breaking changes permitted but keep defaults compatible):

--non-interactive (optional): if any prompt would be required, fail with a machine-readable error. Default is interactive to preserve today.

Workflow pipeline (single endorsed path)

CreateEphemeralClusterWorkflow.run() executes in this strict order:

Initialize context

Resolve region from region-az (strip last char).

Create boto3 session with profile and region.

Fetch account id and caller ARN once, store in AwsContext.

Load and normalize config

Parse config YAML (triplets + template defaults).

Ensure required keys exist; write-back to config file if missing (preserve current mutation).

Resolve “effective values” using the same auto-select rules (DAY_DISABLE_AUTO_SELECT).

PreflightValidator.run()

Toolchain checks (python, git, wget, pcluster version).

AWS identity and permissions checks.

Quota checks (structured report).

S3 bucket candidate discovery and selection (if multiple).

Bucket validation (hard gate).

EC2 keypair selection and local pem validation.

Baseline network prerequisites inspection (subnets/policy presence).

Produce a JSON report object and persist it locally before proceeding.

Ensure baseline prerequisites (Layer 1)

If both public/private subnets missing in AZ, deploy/update CFN stack using existing template and exact parameters.

Ensure pcluster-omics-analysis policy exists.

Resolve pclusterTagsAndBudget policy ARN (post-stack).

Policy resources (Layer 3)

Ensure global budget exists; if not, create budget + notifications + update S3 tags file.

Ensure cluster budget exists; if not, create + update tags file.

Resolve budget enforcement mode.

Render pcluster YAML artifacts

Copy template YAML to ~/.config/daylily/<cluster>_cluster_<ts>.yaml.init (raw template copy, parity).

Render substituted YAML to ~/.config/daylily/<cluster>_init_template_<ts>.yaml (parity).

Apply spot heuristics to produce final YAML ~/.config/daylily/<cluster>_cluster_<ts>.yaml.

pcluster create

Dry-run create, enforce exact success criteria.

Real create.

Monitor to completion using pcluster describe-cluster.

Post-create

Headnode configuration (best-effort, warning only on failure).

Heartbeat policy wiring (best-effort, warning only on failure).

Write artifacts and state

Final config snapshot YAML.

Resolved CLI config YAML.

Next-run template config YAML.

StateStore write including all resolved IDs/ARNs and artifact paths.

Print next actions

Print deterministic headnode login command using the resolved headnode public IP and pem path.

Error handling and determinism rules

Every external command call (pcluster, ssh, optional legacy scripts) must be wrapped with:

Captured stdout/stderr

Exit code

Deterministic exception type with context

Every “warn and continue” from the Bash script must map to:

A PreflightCheckResult(status="WARN") or a runtime WarningEvent stored in state.

7. PreflightValidator Specification
Output contract (machine-readable)

PreflightReport JSON schema (stored under ~/.config/daylily/preflight_<cluster>_<ts>.json):

{
  "run_id": "YYYYMMDDHHMMSS",
  "cluster_name": "string or null",
  "region": "us-west-2",
  "region_az": "us-west-2b",
  "aws_profile": "profile",
  "account_id": "123456789012",
  "caller_arn": "arn:aws:iam::...:user/...",
  "checks": [
    {
      "id": "toolchain.python",
      "status": "PASS|WARN|FAIL",
      "details": { "current": "3.11.6", "required": ">=3.11.0" },
      "remediation": "string"
    }
  ]
}


Checks must be emitted in a stable order.

A single FAIL aborts cluster creation.

WARN aborts only if --pass-on-warn is not set (same semantics as current handle_warning).

Check set (must include at least these)
A. Quota checks (preserve current logic)

Implement as QuotaValidator with explicit quota codes and recommended minimums:

EC2 On-Demand vCPUs: service ec2, quota L-1216C47A, recommended 20.

EC2 Spot vCPUs: service ec2, quota L-34B43A08, recommended 192.

Preserve computed demand:

tot_vcpu = max_count_8I * 8 + max_count_128I * 128 + max_count_192I * 192

If tot_vcpu >= quota_value then:

Interactive mode: prompt “press enter to continue else exit” (parity).

Non-interactive: FAIL with remediation.

VPCs: service vpc, quota L-F678F1CE, recommended 5.

Elastic IPs: service ec2, quota L-0263D0A3, recommended 5.

NAT Gateways: service vpc, quota L-FE5A380F, recommended 5.

Internet Gateways: service vpc, quota L-A4707A72, recommended 5.

Each quota check result must include:

quota_code

service_code

current_value

recommended_min

evaluation (PASS/WARN/FAIL)

note if API call failed (WARN/FAIL consistent with current behavior)

B. S3 bucket region validation (hard gate)

S3BucketValidator must:

List all buckets.

Filter candidates:

Name contains omics-analysis (parity) OR endswith pattern from README.

Determine bucket region using GetBucketLocation:

If LocationConstraint is null/None, treat as us-east-1 (parity).

Only allow selection from buckets matching region.

Validate contents by executing (parity behavior):

daylily-omics-references.sh verify --bucket <bucket> --exclude-b37

If verification fails, mark FAIL and abort create.

Also include explicit validation that:

Bucket string passed into YAML is s3://<bucket_name> (parity bucket_url).

The final chosen bucket is stored in state and in final config snapshot.

C. IAM permission validation (preserve)

IamPermissionValidator must:

Determine aws_cli_user from STS caller ARN.

Check attached user policies for:

DaylilyGlobalEClusterPolicy

Check attached group policies for groups of that user for:

DaylilyGlobalEClusterPolicy

Repeat for region policy:

DaylilyRegionalEClusterPolicy-<region>

If missing:

Interactive: prompt user whether to continue (parity).

Non-interactive: FAIL.

Also implement:

Ensure or validate existence of pcluster-omics-analysis managed policy (creation is allowed because script does it).

Validate scheduler role ARN format when provided (regex match), and verify role exists if not created.

D. Required config validation (preserve and formalize)

ConfigValidator must validate:

region_az ends with a letter and region extracted is valid (parity).

cluster_name matches ^[a-zA-Z0-9\-]+$ and length <= 25.

Emails match the same regex.

Schedule expression matches ^(rate|cron)\(.+\)$.

Numeric fields:

max_count_* are integers >= 0

fsx size is integer > 0

budget amounts are numeric > 0

Enumerations:

enforce_budget in {skip, enforce}

save_fsx in {Retain, Delete}

allocation_strategy in {price-capacity-optimized, capacity-optimized, lowest-price}

detailed_monitoring in {true,false}

delete_local_root in {true,false}

8. Migration Plan (phased)
Phase 0: Introduce control plane without changing entrypoint behavior

Add daylily_ec package.

Implement workflow and validators.

Keep bin/daylily-create-ephemeral-cluster Bash but add a hidden flag --use-python for side-by-side execution.

Acceptance: Python path can create clusters end-to-end using the same YAML templates and produces the same AWS-visible outcomes.

Phase 1: Replace create entrypoint with Python control plane

bin/daylily-create-ephemeral-cluster becomes wrapper that invokes Python workflow.

Preserve flags and interactive prompts.

Acceptance: old Bash monolith removed or renamed to bin/legacy/daylily-create-ephemeral-cluster.bash for rollback.

Phase 2: Internalize remaining shell glue

Replace calls to:

bin/init_cloudstackformation.sh with boto3 CFN deploy logic (same template).

bin/create_budget.sh with boto3 budgets + s3 logic (same semantics).

bin/get_git_deets.sh with Python git + YAML read logic.

Keep headnode config calling the existing script initially.

Acceptance: no yq/jq/bc required for create path (except optional legacy scripts).

Phase 3: Formal drift detection

Implement dayctl drift check:

CFN stack drift detection (Layer 1)

Budget presence and notifications (Layer 3)

Heartbeat schedule/topic/subscription state (Layer 3)

Acceptance: drift report is machine-readable JSON and stable.

Phase 4: Immutable image baking where possible (optional feature flag first)

Add dayctl image build that runs pcluster build-image using a config derived from current bootstrap scripts.

Split post_install_ubuntu_combined.sh into:

Image build steps (static installs)

Minimal runtime steps (dynamic wiring, mounts, tags)

Default remains runtime bootstrap until parity is validated; then flip default.

Acceptance: cluster nodes converge to identical final software state vs current runtime bootstrap, measured by a deterministic “node readiness” script.

9. Implementation Task Graph

Each task is deterministic: implement exactly what is stated, with explicit acceptance criteria.

CP-001: Add Python control plane package skeleton

Deps: none

Files affected:

daylily_ec/ (new files: __init__.py, cli.py)

pyproject.toml (include daylily_ec*, add deps if needed)

Acceptance criteria:

python -c "import daylily_ec" succeeds in DAY-EC.

bin/daylily-create-ephemeral-cluster --help shows preserved flags (even if unimplemented).

CP-002: Implement config triplet parsing + write-back

Deps: CP-001

Files affected:

daylily_ec/config/triplets.py

daylily_ec/config/models.py

Acceptance criteria:

Can load config/daylily_ephemeral_cluster_template.yaml.

Missing required keys are added to config file on disk with [PROMPTUSER,"",""] triplets.

Auto-select logic matches Bash should_auto_apply_config_value.

CP-003: Implement AWS context and clients

Deps: CP-001

Files affected:

daylily_ec/aws/context.py

Acceptance criteria:

Given profile + region, returns account_id and caller_arn.

Stable behavior for both IAM user and assumed-role ARNs.

CP-004: Preflight framework and report writer

Deps: CP-001, CP-003

Files affected:

daylily_ec/workflow/create_cluster.py (skeleton)

daylily_ec/state/models.py (PreflightReport)

daylily_ec/state/store.py (write JSON)

Acceptance criteria:

Running preflight emits JSON report to ~/.config/daylily/.

Report ordering stable and includes PASS/WARN/FAIL.

CP-005: Implement QuotaValidator

Deps: CP-003, CP-004

Files affected:

daylily_ec/aws/quotas.py

Acceptance criteria:

Emits check results for all quota codes listed above.

Spot vCPU computed from max_count_* exactly as Bash.

Behavior: WARN/FAIL gating respects --pass-on-warn.

CP-006: Implement S3 bucket selector + validator

Deps: CP-003, CP-004

Files affected:

daylily_ec/aws/s3.py

Acceptance criteria:

Filters buckets by name contains omics-analysis and region match.

Runs daylily-omics-references.sh verify --exclude-b37 and hard-fails on non-zero exit.

Never proceeds to pcluster steps if this validator fails.

CP-007: Implement IAM policy checks and ensurers

Deps: CP-003, CP-004

Files affected:

daylily_ec/aws/iam.py

Acceptance criteria:

Checks Daylily global + regional policies attached via user or group (same semantics).

Ensures managed policy pcluster-omics-analysis exists (idempotent create).

Resolves scheduler role ARN using env vars and existing role names.

CP-008: Implement baseline CloudFormation stack ensure

Deps: CP-003, CP-004

Files affected:

daylily_ec/aws/cloudformation.py

Acceptance criteria:

Uses existing template config/day_cluster/pcluster_env.yml.

Stack name derivation matches Bash script exactly: pcluster-vpc-stack-$(cut -d '-' -f 3 from AZ).

Parameters match bin/init_cloudstackformation.sh.

If policy already exists, passes CreatePolicy=false.

CP-009: Implement subnet and policy selection

Deps: CP-003, CP-008

Files affected:

daylily_ec/aws/ec2.py

Acceptance criteria:

Finds public/private subnets using tag name contains Public Subnet / Private Subnet and AZ match.

Preserves “both missing triggers create stack; partial missing fails”.

Selects policy ARN pclusterTagsAndBudget (auto-select if single and auto-select enabled).

CP-010: Implement BudgetManager in Python (replace create_budget.sh)

Deps: CP-003, CP-006, CP-004

Files affected:

daylily_ec/aws/budgets.py

Acceptance criteria:

Creates budgets identical in shape to bin/create_budget.sh:

Cost filters on user:aws-parallelcluster-project$<project> and user:aws-parallelcluster-clustername$<cluster>.

Threshold notifications identical.

Updates S3 tags file path exactly: data/budget_tags/pcluster-project-budget-tags.tsv.

Idempotent when budgets exist.

CP-011: Implement YAML substitutions renderer

Deps: CP-002

Files affected:

daylily_ec/render/renderer.py

Acceptance criteria:

Replaces all ${REGSUB_*} tokens in template text exactly.

Writes both .yaml.init (template copy) and init_template artifact in ~/.config/daylily/ matching naming scheme.

Required substitution keys enforced: region, pub subnet, private subnet, cluster name.

CP-012: Integrate spot heuristics

Deps: CP-003, CP-011

Files affected:

daylily_ec/workflow/create_cluster.py

(Option A) import and call bin/calcuate_spotprice_for_cluster_yaml.py logic as library

(Option B) subprocess invoke existing script for strict parity

Acceptance criteria:

Final YAML has SpotPrice values set for each ComputeResources group.

Uses bump price 4.14 and AZ/profile inputs.

Fails with actionable message if spot API access denied (parity).

CP-013: Implement PclusterRunner + dry-run semantics

Deps: CP-011, CP-012

Files affected:

daylily_ec/pcluster/runner.py

Acceptance criteria:

Dry-run success criterion exactly matches: message == "Request would have succeeded, but DryRun flag is set."

Honors DAY_BREAK=1 to exit after dry-run.

Executes real create with same flags and region/profile behavior.

CP-014: Implement cluster creation monitor

Deps: CP-013

Files affected:

daylily_ec/pcluster/monitor.py

Acceptance criteria:

Wait loop stops only on CREATE_COMPLETE.

Implements 5 consecutive non-zero monitor exits before failing (same behavior as Bash).

CP-015: Implement HeartbeatManager and role resolution

Deps: CP-003, CP-007

Files affected:

daylily_ec/aws/heartbeat.py

Acceptance criteria:

Creates/updates SNS topic, subscription, and scheduler schedule with same names and schedule expression.

Persists created ARNs in StateStore.

Non-fatal failure behavior matches current script (warn and continue).

CP-016: Implement StateStore + drift detection

Deps: CP-004, CP-008, CP-010, CP-015

Files affected:

daylily_ec/state/store.py

daylily_ec/state/drift.py

Acceptance criteria:

Writes a state JSON per run including:

Selected bucket, keypair, subnet IDs, policy ARN

Budget names

Heartbeat resources

Paths to generated YAML artifacts

Drift check reports mismatches for Layer 1 and Layer 3 resources without mutating anything.

CP-017: Wire full create workflow and swap entrypoint

Deps: CP-001..CP-016

Files affected:

daylily_ec/workflow/create_cluster.py

bin/daylily-create-ephemeral-cluster (wrapper or Python)

Acceptance criteria:

End-to-end run produces:

Same gating behaviors (bucket validation, quota checks)

Same pcluster create semantics

Same artifact outputs in ~/.config/daylily/

The old Bash monolith is no longer the orchestrator.

CP-018: Tests

Deps: CP-002..CP-016

Files affected:

tests/test_triplets.py

tests/test_renderer.py

tests/test_preflight_report.py

Acceptance criteria:

Unit tests cover triplet parsing, auto-select behavior, renderer substitution correctness, and preflight report schema stability.

CP-019: Documentation updates

Deps: CP-017

Files affected:

README.md

docs/ (if used)

Acceptance criteria:

README describes new Python control plane behavior and new dayctl infra ... commands, without changing prerequisites scope.

Do this next:

Implement CP-001 through CP-004 first, but lock the contracts (PreflightReport schema + Triplet semantics) before touching AWS logic.

For strict parity, start CP-012 with subprocess invocation of the existing spot price script, then convert to library call only after outputs match.

Treat S3 bucket validation as a non-negotiable gate: implement CP-006 early and ensure the workflow cannot reach any pcluster call if it fails.


10. Spec Hardening Addendum (Non-Negotiable Invariants)

This addendum tightens behavior preservation requirements and removes ambiguity.
These constraints override any interpretation ambiguity in previous sections.

10.1 Environment Variable Semantics (Parity Required)

The refactored system MUST preserve the following environment variable semantics exactly as they function in the current Bash implementation.

DAY_DISABLE_AUTO_SELECT

Behavior today:

When set (non-empty), disables automatic application of USESETVALUE triplets.

Forces interactive prompt path instead of silent auto-selection.

Refactor requirement:

EnvironmentResolver MUST read DAY_DISABLE_AUTO_SELECT before config resolution.

TripletResolver MUST incorporate this value when determining whether to auto-apply.

Behavior must match Bash semantics exactly:

If unset → auto-select allowed.

If set → auto-select disabled.

No reinterpretation or inversion allowed.

DAY_BREAK

Behavior today:

If DAY_BREAK=1, execution stops after pcluster dry-run.

Refactor requirement:

Control plane must read DAY_BREAK.

If value == "1":

Perform dry-run.

Exit immediately after dry-run success.

Do NOT perform real cluster creation.

Exit code must be 0 in this case.

AWS_PROFILE / AWS_REGION

Refactor requirement:

CLI flags override environment.

If CLI flag absent:

Respect AWS_PROFILE env.

Respect AWS_REGION env.

Region derived from --region-az always overrides both.

Resolution precedence:

CLI flag

Explicit config file

Environment variable

Hardcoded default (if any)

This resolution order must be documented and unit tested.

10.2 Artifact Naming and Path Parity (Deterministic Contract)

All file artifacts currently written under ~/.config/daylily/ must preserve:

Directory location

Filename structure

Timestamp format

Content ordering stability

Timestamp Format

Timestamp MUST be:

YYYYMMDDHHMMSS


Example:

20260211143722


No milliseconds.
No timezone suffix.
Use local system time exactly as Bash currently does.

Required Artifacts Per Run

For cluster name <cluster> and timestamp <ts>:

Raw template copy:

~/.config/daylily/<cluster>_cluster_<ts>.yaml.init


Rendered init template:

~/.config/daylily/<cluster>_init_template_<ts>.yaml


Final cluster config:

~/.config/daylily/<cluster>_cluster_<ts>.yaml


Resolved CLI config snapshot:

~/.config/daylily/<cluster>_resolved_cli_<ts>.yaml


Preflight report:

~/.config/daylily/preflight_<cluster>_<ts>.json


State record:

~/.config/daylily/state_<cluster>_<ts>.json

Ordering Stability

YAML keys must be rendered in stable order.

JSON output must be serialized with sorted keys.

No nondeterministic dict ordering allowed.

Unit tests must assert byte-stable output given identical inputs.

10.3 Headnode Configuration Parity

Headnode configuration currently:

Clones repository

Applies repo overrides

Installs miniconda / activates environment

Executes setup scripts

Performs tagging / environment init

Refactor must preserve:

Repo override semantics (--repo-override key:ref)

Branch vs tag resolution logic

Failure severity

Severity Rules (Must Match Bash)

Headnode configuration failures must:

NOT abort cluster creation.

Emit WARN-level event.

Be stored in StateStore under post_create_warnings.

Refactor MUST NOT silently ignore failures.
Refactor MUST NOT escalate them to fatal unless Bash currently does.

10.4 Exit Code Contract

Refactored entrypoint must use explicit exit codes:

Exit Code	Meaning
0	Success
1	Validation failure (config, quota, IAM, bucket, keypair)
2	AWS operation failure (CFN, IAM, Budgets, SNS, Scheduler, pcluster failure)
3	Drift detected (for drift command only)
4	Toolchain failure (missing python, wrong pcluster version, etc.)

Interactive "press enter to continue" flows:

If user aborts → exit 1.

If user continues → proceed normally.

10.5 Preflight Gating Order (Strict)

Preflight MUST execute in this exact order:

ToolchainValidator

AWS Identity Validator

IAM Permission Validator

ConfigValidator

QuotaValidator

S3 Bucket Selector

S3 Bucket Validator

KeyPair Selector

Baseline Network Inspector

If any FAIL occurs:

Stop immediately.

Do not mutate AWS resources.

Emit PreflightReport and exit 1.

10.6 No Hidden AWS State

Refactor MUST NOT introduce:

DynamoDB

New S3 state bucket

Parameter Store as state store

New CloudFormation stacks not currently created by scripts

CDK or SAM unless currently used

StateStore remains local filesystem JSON.

10.7 Parity Verification Gate (Mandatory)

Before legacy Bash script is removed:

A validation checklist MUST pass:

Create cluster with Bash script.

Create cluster with Python refactor.

Compare:

Generated YAML (structural equivalence)

Budgets created

Heartbeat resources

IAM policies created

Subnet selection

S3 bucket chosen

Spot price applied

Artifact files created

AWS-visible diff must show no behavioral difference.

Only after parity verification may Bash be removed.

10.8 Immutable Image Migration Guardrail (Future Phase)

Image baking (optional phase) must:

Produce identical installed software set.

Preserve Slurm wrapper behavior.

Preserve tagging scripts.

Preserve spot logging.

Pass a deterministic "node readiness check" script.

Image baking MUST be feature-flagged until parity validated.

End of Addendum