# Daylily Ephemeral Cluster

Daylily provisions short-lived AWS ParallelCluster environments for bioinformatics workflows, bootstraps the head node with the Daylily control-plane tools, stages data into FSx-backed storage, launches workflow repos from the operator machine, exports results back to S3, and tears the cluster down when the run is done.

The supported operator path is:

1. `source ./activate`
2. `daylily-ec preflight`
3. `daylily-ec create`
4. `bin/daylily-ssh-into-headnode`
5. `bin/daylily-stage-samples-from-local-to-headnode`
6. `bin/daylily-run-omics-analysis-headnode`
7. `daylily-ec export --target-uri analysis_results/ubuntu`
8. `daylily-ec delete`

The current supported remote access path is AWS Systems Manager Session Manager landing directly in the `ubuntu` login shell. The repo no longer treats PEM-driven access as part of the supported operator flow.

## Quick Start

From a repo checkout:

```bash
source ./activate

export AWS_PROFILE=daylily-service-lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"

daylily-ec preflight \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --config "$DAY_EX_CFG"

daylily-ec create \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --config "$DAY_EX_CFG"
```

After create completes, continue with:

```bash
bin/daylily-ssh-into-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "<cluster-name>"
```

For the complete operator walkthrough, see [docs/quickest_start.md](docs/quickest_start.md) and [docs/operations.md](docs/operations.md).

## What The Repo Provides

- `daylily-ec`: the supported CLI for preflight, create, export, delete, drift, pricing, and headnode shell helpers
- `environment.yaml` plus `pyproject.toml`: the `DAY-EC` environment contract for checkout and packaged installs
- `bin/daylily-ssh-into-headnode`: Session Manager access that validates the account document lands in an `ubuntu` login shell
- `bin/daylily-stage-samples-from-local-to-headnode`: laptop-side staging into the FSx-backed data repository
- `bin/daylily-run-omics-analysis-headnode`: workflow launcher that clones the configured repo, writes staged config, starts tmux, and records durable run state
- `daylily_ec/ssh_to_ssm_e2e_runner.py`: a real AWS-backed acceptance runner for the supported lifecycle

## Supported Docs

- [docs/overview.md](docs/overview.md)
- [docs/quickest_start.md](docs/quickest_start.md)
- [docs/ultra_rapid_start.md](docs/ultra_rapid_start.md)
- [docs/operations.md](docs/operations.md)
- [docs/DAY_EC_ENVIRONMENT.md](docs/DAY_EC_ENVIRONMENT.md)
- [docs/pip_install.md](docs/pip_install.md)

Archived or historical materials live under [docs/archive/](docs/archive/README.md). They are reference material, not the supported operator path.
