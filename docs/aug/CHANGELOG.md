## Changelog

### [Unreleased] — Python Control Plane Refactor (CP-001 through CP-019)

**Added**
- `daylily_ec/` Python package — 3-layer control plane replacing the 2585-line Bash monolith
- `daylily-ec` CLI with `create`, `preflight`, and `drift` commands (built on `cli-core-yo`)
- Structured preflight validation with machine-readable JSON reports
- Local JSON-based state store and drift detection (`~/.config/daylily/`)
- Spot-price optimization integrated as a library import
- Budget management (global + per-cluster) via Python
- Heartbeat scheduling (EventBridge + SNS) via Python
- Cluster creation monitoring with configurable polling
- 468 unit tests, 85% coverage (no AWS credentials required)
- Exit codes: 0=success, 1=validation failure, 2=AWS error, 3=drift, 4=toolchain failure

**Changed**
- `bin/daylily-create-ephemeral-cluster` is now a thin 30-line Bash wrapper delegating to `python -m daylily_ec create`
- Config triplet parsing moved from shell to Python with full normalization and auto-select logic
- YAML rendering moved from `yq`/`sed` to `ruamel.yaml` with roundtrip comment preservation
- CloudFormation stack ensure moved from `bin/init_cloudstackformation.sh` to Python
- IAM policy checks and ensures moved to Python
- S3 bucket selection and validation moved to Python
- Subnet and policy selection moved to Python

**Preserved**
- Original Bash monolith at `bin/legacy/daylily-create-ephemeral-cluster.bash`
- All existing CLI flags and interactive prompts
- All AWS resource shapes (budgets, heartbeat, CFN stacks, IAM policies)
- All environment variable semantics (`DAY_DISABLE_AUTO_SELECT`, `DAY_BREAK`, `AWS_PROFILE`)

### [0.7.200]
- ...
