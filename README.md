# Daylily Ephemeral Cluster

Daylily provisions ephemeral AWS ParallelCluster environments for bioinformatics workloads. It gives operators a Python control plane, shared reference-data plumbing, head-node bootstrap, workflow launch helpers, and a clean delete path.

## Highlights

### Single Command Cluster Creation

_once your local environment, AWS profile, and cluster config are in place_

```bash
daylily-ec create --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG"
```

### Architecture & Features

- **Repeatable cluster bring-up** with preflight checks, rendered cluster YAML, and automated head-node bootstrap.
- **Cost-aware infrastructure** with pricing snapshots, budgets, heartbeat notifications, and a clear export/delete lifecycle.
- **Shared FSx for Lustre storage** backed by a region-scoped S3 bucket for references, staged inputs, and results.
- **Pluggable workflow catalog** controlled by YAML and cloned via `day-clone`.
- **Laptop-to-cluster staging and launch helpers** for a practical remote operator flow.
- **Operator artifacts** including preflight reports, state snapshots, rendered YAML, and reusable config in `~/.config/daylily/`.

## Architecture at a Glance

Daylily composes a few AWS building blocks into a usable HPC environment:

1. **`daylily_ec`** is the control plane that validates prerequisites, renders cluster YAML, applies live spot pricing, creates the cluster, and records state snapshots.
2. **AWS ParallelCluster + Slurm** provide the compute fabric.
3. **FSx for Lustre** is mounted at `/fsx` and linked to a region-specific S3 bucket whose name includes `omics-analysis`.
4. **Auto-scaling EC2 workers** let the compute fleet expand and contract around real workload demand.
5. **VPC, subnets, and security groups** are resolved or created as part of the operator flow.
6. **Head-node Daylily utilities** handle staging, cloning, validation, and launch workflows.
7. **Workflow registry metadata** in [`config/daylily_available_repositories.yaml`](config/daylily_available_repositories.yaml) defines approved repos and default refs.
8. **Artifacts under `~/.config/daylily/`** preserve the exact config, state, and rendered templates that created a cluster.

---

## Workflow Catalog & Launch Path

The head node ships with a registry of vetted repositories defined in [`config/daylily_available_repositories.yaml`](config/daylily_available_repositories.yaml). Operators can clone approved pipelines with `day-clone`, override refs for development work, and launch through the bundled staging + tmux-based helpers.

Current bundled examples include `daylily-omics-analysis`, `rna-seq-star-deseq2`, and `daylily-sarek`. Because the compute layer is plain Slurm, any orchestrator that speaks Slurm can run once the repo is on the head node.

---

## Reference Data & Canned Controls

High-throughput analyses rely on predictable reference data access. Daylily expects a region-scoped reference bucket and uses FSx for Lustre so the whole cluster sees the same durable inputs.

- **verify your reference bucket exists**

  ```bash
  daylily-omics-references --profile "$AWS_PROFILE" --region "$REGION" \
    verify --bucket "${BUCKET_PREFIX}-daylily-omics-analysis-${REGION}" --exclude-b37
  ```

- **clone reference bundles** into a region-scoped S3 bucket using the installed `daylily-omics-references` CLI:

  ```bash
  export AWS_PROFILE=daylily-service
  export REGION=us-west-2
  export BUCKET_PREFIX=myorg

  REF_VERSION_FILE="$(find config/day_cluster -maxdepth 1 -name 'daylily_reference_version_*.info' | head -n 1)"
  REF_VERSION="$(basename "$REF_VERSION_FILE" .info)"
  REF_VERSION="${REF_VERSION#daylily_reference_version_}"

  daylily-omics-references --profile "$AWS_PROFILE" --region "$REGION" \
    clone --bucket-prefix "$BUCKET_PREFIX" --version "$REF_VERSION" --execute
  ```

- **automatic mounting via FSx** means all compute nodes see shared directories such as `/fsx/data`, `/fsx/resources`, and `/fsx/analysis_results`.
- **staging and controls** are handled by the bundled staging helpers and the workflow repos cloned onto the head node.

> The reference bucket is durable. The cluster is not. That is the point.

![Spot pricing example](docs/images/cost_est_table.png)

---

## Remote Data Staging & Pipeline Execution

Use the bundled helpers to stage on the head node, stage from a laptop through the FSx-backed S3 path, and launch workflows remotely in tmux. The full operator flow is documented later in this README and in [docs/operations.md](docs/operations.md).

---

## Cost Monitoring & Budget Enforcement

Daylily uses AWS Budgets, cost-allocation tags, pricing helpers, and heartbeat notifications to give operators per-cluster and per-project cost visibility:

- **preflight before mutation** so obvious IAM/quota/bucket mistakes fail early
- **pricing snapshots** through `daylily-ec pricing snapshot`
- **budget-aware lifecycle hooks** in the cluster config flow
- **heartbeat notifications** so stale FSx/EBS resources are harder to forget
- **tagged-resource reporting** for finding orphaned spend and drift

> For ephemeral infrastructure, cost is part of operations, not an appendix.

![Tagged cost tracking example](docs/images/assets/day_aws_tagged_costs_by_hour_project.png)

# Installation -- Quickest Start

_only useful if you already have AWS account configuration, a target region, and a reference bucket in place_

The shortest supported operator path from a fresh checkout is:

```bash
./bin/check_prereq_sw.sh
./bin/install_miniconda   # only if conda is not already installed
./bin/init_dayec
source ./activate

export AWS_PROFILE=daylily-service
export REGION=us-west-2
export REGION_AZ=us-west-2c

mkdir -p ~/.config/daylily
cp config/daylily_ephemeral_cluster_template.yaml \
  ~/.config/daylily/daylily_ephemeral_cluster.yaml
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"

daylily-ec preflight --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG"
daylily-ec create --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG"
```

See [docs/quickest_start.md](docs/quickest_start.md) for the shortest canonical runbook and [docs/operations.md](docs/operations.md) for day-2 operations.

# Installation -- Detailed

## AWS

### Operator Identity

Create or reuse an AWS operator identity, typically `daylily-service`, and make sure it can:

- create and inspect ParallelCluster resources in the target account
- manage the reference bucket used for FSx-backed data access
- create or inspect network resources needed for the cluster lifecycle

The repo ships the cluster policy template at [`config/aws/daylily-service-cluster-policy.json`](config/aws/daylily-service-cluster-policy.json).

#### Create Service Linked Role `VERY IMPORTANT`

> If this role is missing, spot capacity can fail in annoying ways even when the head node looks fine.

```bash
aws iam list-roles --query "Roles[?RoleName=='AWSServiceRoleForEC2Spot'].RoleName"
aws iam create-service-linked-role --aws-service-name spot.amazonaws.com
```

#### Quotas, Cost Tags, And Other AWS Considerations

Daylily preflight checks the common blockers, but you should still be aware of them up front:

- EC2 on-demand quota for the head node
- EC2 spot quota for the target fleet shape
- FSx for Lustre quota in the target region
- VPC/subnet/networking limits if operating across many clusters or regions
- budget and cost-allocation-tag permissions if you want cost reporting and enforcement

Historically, under-provisioned spot quotas and missing FSx quota were the easiest ways to waste time before the first successful cluster build.

#### AWS CLI Profile

Minimal profile example:

```ini
[daylily-service]
region = us-west-2
output = json
```

> Be explicit with `AWS_PROFILE`; avoid leaning on `default`.

#### SSH Key Pair(s)

- Keep the PEM in `~/.ssh/`
- use the same region as your target cluster
- naming it with `-omics-` remains the easiest convention to recognize later

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
chmod 400 ~/.ssh/<your-key>.pem
```

## Prerequisites (On Your Local Machine)

From the repo root:

```bash
./bin/check_prereq_sw.sh
./bin/install_miniconda   # only if needed
./bin/init_dayec
source ./activate

daylily-ec info
daylily-ec version
```

`./bin/init_dayec` creates or updates the `DAY-EC` conda environment and installs this repo into it. `source ./activate` activates `DAY-EC` when present, adds [`bin/`](bin/) to `PATH`, and exposes `daylily-ec` in the current shell.

## Clone Reference Bucket (only needs to be done once per region, or whenever it is missing)

_`daylily-ec preflight` and `daylily-ec create` will fail if the expected reference bucket is not detected in the region you run in._

```bash
export AWS_PROFILE=daylily-service
export REGION=us-west-2
export BUCKET_PREFIX=myorg

REF_VERSION_FILE="$(find config/day_cluster -maxdepth 1 -name 'daylily_reference_version_*.info' | head -n 1)"
REF_VERSION="$(basename "$REF_VERSION_FILE" .info)"
REF_VERSION="${REF_VERSION#daylily_reference_version_}"

daylily-omics-references --profile "$AWS_PROFILE" --region "$REGION" \
  clone --bucket-prefix "$BUCKET_PREFIX" --version "$REF_VERSION" --execute
```

Optional manual verification:

```bash
daylily-omics-references --profile "$AWS_PROFILE" --region "$REGION" \
  verify --bucket "${BUCKET_PREFIX}-daylily-omics-analysis-${REGION}" --exclude-b37
```

## Prepare The Cluster Config

Configuration for the create flow lives in a user-managed YAML file. Copy the template to a writable location and set `DAY_EX_CFG` for convenience:

```bash
mkdir -p ~/.config/daylily
cp config/daylily_ephemeral_cluster_template.yaml \
  ~/.config/daylily/daylily_ephemeral_cluster.yaml
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
```

Recommended keys to fill in before the first run:

- `cluster_name`
- `s3_bucket_name`
- `budget_email`
- `allowed_budget_users`
- `global_allowed_budget_users`
- `heartbeat_email`

Optional if you want fewer prompts:

- `ssh_key_name`
- `public_subnet_id`
- `private_subnet_id`
- `iam_policy_arn`

Leave any value set to `PROMPTUSER` if you want the CLI to query AWS and prompt interactively.

> `DAY_EX_CFG` is a shell convenience variable. The current Python CLI does **not** consume it implicitly, so always pass `--config "$DAY_EX_CFG"`.

## Generate Analysis Cost Estimates per Availability Zone

If you want a raw pricing snapshot before choosing an AZ:

```bash
daylily-ec pricing snapshot \
  --region "$REGION" \
  --config config/day_cluster/prod_cluster.yaml \
  --profile "$AWS_PROFILE"
```

This is the current supported path for spot-pricing inspection.

## Create An Ephemeral Cluster

_from your local machine, in the Daylily repo root_

```bash
export REGION_AZ=us-west-2c

daylily-ec preflight \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --config "$DAY_EX_CFG"

daylily-ec create \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --config "$DAY_EX_CFG"
```

Add `--pass-on-warn` to `preflight` only when you have reviewed the warnings and intend to continue.

**What the flow does:**

- your AWS credentials are used to query required resources
- the CLI validates the selected reference bucket before provisioning
- baseline network resources are resolved or created as needed
- cluster YAML is rendered and spot pricing is applied
- the cluster is created through ParallelCluster
- the head node is bootstrapped with `DAY-EC`, `day-clone`, and bundled helpers
- preflight reports, state snapshots, and rendered artifacts are written to `~/.config/daylily/`

> Cluster creation is not instant. Expect a real wait while ParallelCluster, FSx, and head-node bootstrap finish.

If you need to debug a failure, the CloudFormation console still gives the best low-level event trail.

## What Success Looks Like

After a successful run:

- `~/.config/daylily/` contains the preflight report, state snapshot, and rendered cluster YAML
- the head node has `DAY-EC`, `day-clone`, and the Daylily helper scripts ready to use

![Remote test success example](docs/images/daylily_remote_test_success.png)

# Costs

## Monitoring, Tags, And Budgets

Daylily-created resources are intended to be tagged well enough for operators to monitor costs, find stale infrastructure, and reason about run economics per cluster or per project.

Budget-aware lifecycle hooks still exist conceptually in the Daylily flow, but treat hard enforcement as something to test in your own account before trusting it.

## Typical Cost Drivers

These are still the right cost buckets to watch:

1. **head node**: steady on-demand cost while the cluster exists
2. **FSx for Lustre**: the biggest idle-cluster cost driver in many runs
3. **spot fleet**: burst cost during real workload execution
4. **reference bucket**: durable monthly storage cost
5. **retained EBS / retained FSx**: easy-to-forget stale-resource cost

> Historically, the most expensive mistake was not running the cluster — it was forgetting what you chose to retain after deleting it.

## Operator Advice

- run `daylily-ec pricing snapshot` before choosing an AZ if price sensitivity matters
- keep an eye on retained FSx and root volumes
- export results promptly and delete the cluster promptly
- do not treat the ephemeral cluster as long-term storage

# Working With The Ephemeral Clusters

## Connect To A Cluster

List clusters in a region:

```bash
daylily-ec cluster-info --region "$REGION" --profile "$AWS_PROFILE"
```

SSH to the head node:

```bash
ssh -i ~/.ssh/<your-key>.pem ubuntu@<headnode-ip>
```

Use `daylily-ec cluster-info` or `pcluster describe-cluster` to find the head-node public IP.

## Validate The Head Node

Once connected to the head node:

```bash
cd ~/projects/daylily-ephemeral-cluster
conda activate DAY-EC

daylily-ec info
day-clone --list
ls -lth /fsx/
```

You want to see the Daylily CLI available, the workflow registry available, and the expected shared filesystem directories present.

![Example results tree](docs/images/assets/daylily_tree.png)

## Stage Sample Data & Build `config/samples.tsv` and `config/units.tsv`

### Run Directly On The Head Node

```bash
cd ~/projects/daylily-ephemeral-cluster
./bin/daylily-stage-analysis-samples-headnode /path/to/analysis_samples.tsv

# optionally override the stage target
./bin/daylily-stage-analysis-samples-headnode \
  /path/to/analysis_samples.tsv \
  /fsx/custom_stage_dir
```

### Launch Staging From Your Laptop

```bash
./bin/daylily-stage-samples-from-local-to-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "s3://myorg-daylily-omics-analysis-${REGION}" \
  --config-dir ./generated-config \
  ./analysis_samples.tsv
```

Important details:

- this flow stages through the S3-backed FSx repository, not by copying large files over SSH
- its default staging base is `/data/staged_sample_data`, which appears on the cluster as `/fsx/data/staged_sample_data/remote_stage_<timestamp>/`
- local `samples.tsv` and `units.tsv` copies are written into `--config-dir` or next to the source TSV if omitted

## Clone & Launch the Workflow From Your Laptop

```bash
./bin/daylily-run-omics-analysis-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --pem ~/.ssh/<your-key>.pem \
  --stage-base /fsx/data/staged_sample_data
```

Useful launch flags include `--stage-dir`, `--repository`, `--project`, `--target`, `--jobs`, and `--dry-run`.

The launcher clones the workflow via `day-clone`, copies staged config files into the repo, and starts the run inside a tmux session on the head node.

## Slurm Monitoring

On the head node:

```bash
sinfo
squeue -o "%.18i %.8u %.8T %.10M %.30N %.50j"
tmux ls
tmux attach -t <session-name>
```

Use `watch squeue` or your preferred terminal workflow if you want a live scheduler view.

## Export `fsx` Analysis Results Back To S3

Use the AWS FSx console or CLI to create a data-repository export task for the filesystem associated with the cluster.

> Be sure you export results from `/fsx/analysis_results` before deleting the cluster. FSx is scratch-like high-performance working storage, not your final archive.

## Delete The Cluster

When the workload is complete and results have been exported:

```bash
pcluster delete-cluster -n "$CLUSTER_NAME" --region "$REGION"
```

If you retained FSx or root volumes by choice, go confirm their fate explicitly. Those are the resources most likely to keep costing money after you think you are done.

# PCUI (technically optional, but you will be missing out)

PCUI is not required for the supported Daylily operator flow, but it is still useful if you want a browser-driven interface for cluster visibility and interactive shell access.

- use the AWS ParallelCluster PCUI docs for installation
- use the VPC and subnet associated with a working Daylily cluster in the region
- enable SSM if you want browser-shell access; from there you will usually want `sudo su - ubuntu`

The CLI/SSH path remains the canonical Daylily workflow, but PCUI is still a legitimate companion tool.

# Other Monitoring Tools

## AWS CloudWatch

CloudWatch remains useful for low-level cluster and node inspection, especially when debugging failures or inspecting logs outside the terminal that launched the cluster.

## Drift And Tagged Resources

Useful operator commands:

```bash
daylily-ec drift --state-file ~/.config/daylily/state_<cluster>_<timestamp>.json --profile "$AWS_PROFILE"
daylily-ec cluster-info --region "$REGION" --profile "$AWS_PROFILE"
```

## SNS Notifications (cluster heartbeat - experimental)

Heartbeat notifications are intended to keep noisy, pricey stale resources from quietly hanging around forever.

# Documentation

- [docs/quickest_start.md](docs/quickest_start.md): the shortest canonical install and cluster creation runbook
- [docs/operations.md](docs/operations.md): validation, staging, launch, monitoring, export, and delete
- [docs/overview.md](docs/overview.md): architecture, cost context, benchmark links, and system model
- [docs/pip_install.md](docs/pip_install.md): pip-based usage and packaged resources
- [docs/DAY_EC_ENVIRONMENT.md](docs/DAY_EC_ENVIRONMENT.md): local environment and CLI diagnostics
- [CONTRIBUTING.md](CONTRIBUTING.md): development and docs contribution guide

# Historical Material

Older long-form docs and retired notes live under [`docs/archive/`](docs/archive/). They remain useful for background and screenshots, but the supported workflows are described by this README and the live docs above.

# Known Issues

The old README was correct about one thing: known issues belong in operator docs.

- very large or poorly prepared reference buckets can still make FSx-backed cluster creation painful
- low spot or FSx quotas are still among the easiest ways to fail before a first successful build
- CloudFormation remains the best place to inspect low-level failure events during provisioning

# Contributing

[Contributing Guidelines](CONTRIBUTING.md)

# Versioning

Daylily uses tagged releases. For currently available versions, see the [tags on this repository](https://github.com/Daylily-Informatics/daylily-ephemeral-cluster/tags).
 
