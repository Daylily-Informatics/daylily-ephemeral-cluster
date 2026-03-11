# Daylily Ephemeral Cluster

Daylily provisions ephemeral AWS ParallelCluster environments for bioinformatics workloads. It combines a Python control plane, region-scoped reference data, head-node bootstrap, workflow launch helpers, and lifecycle operations so operators can create Slurm clusters when needed and tear them down cleanly when they do not.

## What Daylily Covers

- Preflight validation for IAM, quotas, network prerequisites, local toolchain, and reference-bucket readiness
- Cluster creation through `python -m daylily_ec create` or the thin wrapper `./bin/daylily-create-ephemeral-cluster`
- A region-scoped S3 and FSx for Lustre layout for shared references, staged inputs, and results
- Head-node bootstrap that installs `DAY-EC`, `day-clone`, and the packaged Daylily helpers
- Operator workflows for validation, staging, workflow launch, export, drift checks, and delete

## Architecture Snapshot

1. `daylily_ec` is the control plane that runs preflight, renders cluster YAML, applies spot pricing, creates the cluster, and records state snapshots.
2. AWS ParallelCluster and Slurm provide the compute fabric.
3. A region-specific S3 bucket whose name includes `omics-analysis` backs FSx for Lustre so references and staged data are shared across the cluster.
4. The head node installs Daylily utilities from [`bin/`](bin/) and workflow definitions from [`config/daylily_available_repositories.yaml`](config/daylily_available_repositories.yaml).
5. Optional budgets and heartbeat notifications help operators track cost and stale resources.

## Fast Path

Use the full runbook in [docs/quickest_start.md](docs/quickest_start.md). The shortest supported path from a repo checkout is:

```bash
./bin/check_prereq_sw.sh
./bin/init_dayec
conda activate DAY-EC

export AWS_PROFILE=daylily-service
export REGION_AZ=us-west-2c
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"

python -m daylily_ec preflight --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG"
python -m daylily_ec create --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG"
```

Before `create`, make sure the reference bucket for the target region exists and your config file points at it. [docs/quickest_start.md](docs/quickest_start.md) shows the supported `daylily-omics-references` workflow and the template-copy step.

## CLI Surface

The current CLI surface is:

- `python -m daylily_ec version`
- `python -m daylily_ec info`
- `python -m daylily_ec create --region-az <region-az> ...`
- `python -m daylily_ec preflight --region-az <region-az> ...`
- `python -m daylily_ec drift --state-file <path> ...`
- `python -m daylily_ec resources-dir`
- `python -m daylily_ec pricing snapshot --region <region> --config config/day_cluster/prod_cluster.yaml`

Run `python -m daylily_ec --help` for the current command tree.

## Documentation

- [docs/quickest_start.md](docs/quickest_start.md): operator-first install and cluster creation runbook
- [docs/operations.md](docs/operations.md): head-node validation, staging, launch, monitoring, export, and delete
- [docs/overview.md](docs/overview.md): public-facing architecture, workflow narrative, cost context, and benchmark links
- [docs/pip_install.md](docs/pip_install.md): pip-based usage and packaged resources
- [docs/DAY_EC_ENVIRONMENT.md](docs/DAY_EC_ENVIRONMENT.md): local development environment and CLI diagnostics
- [CONTRIBUTING.md](CONTRIBUTING.md): development and docs contribution guide
- [docs/archive/README.md](docs/archive/README.md): historical material preserved for reference

## Repository Highlights

- [`config/daylily_ephemeral_cluster_template.yaml`](config/daylily_ephemeral_cluster_template.yaml): config triplets for cluster creation defaults
- [`config/daylily_cli_global.yaml`](config/daylily_cli_global.yaml): shared global settings deployed to head nodes
- [`config/daylily_available_repositories.yaml`](config/daylily_available_repositories.yaml): workflow registry used by `day-clone`
- [`docs/benchmarks/`](docs/benchmarks/): benchmark reference material used by the overview doc

## Historical Material

Older long-form docs and retired notes live under [`docs/archive/`](docs/archive/). They are preserved for historical context and are not canonical for current operator workflows.
 
