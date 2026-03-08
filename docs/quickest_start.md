# Quickest Start

This is the shortest supported operator path from a repo checkout to a usable Daylily cluster. It uses the current Python control plane and current packaged scripts. For post-provisioning workflows, see [operations.md](operations.md). For architecture, benchmarks, and public-facing context, see [overview.md](overview.md).

## 1. AWS Operator Prerequisites

Create or reuse an IAM operator identity, typically `daylily-service`, and make sure it can:

- assume the Daylily operator role or act directly as the Daylily operator user
- create and inspect ParallelCluster resources in the target account
- manage the reference bucket used for FSx-backed data access

The repo ships the custom cluster policy at [`../config/aws/daylily-service-cluster-policy.json`](../config/aws/daylily-service-cluster-policy.json). The current operator docs assume:

- a CLI profile named `daylily-service`
- a PEM key for the target region stored in `~/.ssh/`
- a region-specific reference bucket whose name includes `omics-analysis`

Minimal AWS CLI profile example:

```ini
[daylily-service]
region = us-west-2
output = json
```

## 2. Local Prerequisites And Environment

From the repo root:

```bash
./bin/check_prereq_sw.sh
./bin/install_miniconda   # only if conda is not already installed
./bin/init_dayec
conda activate DAY-EC

python -m daylily_ec info
python -m daylily_ec version
```

`./bin/init_dayec` creates or updates the `DAY-EC` conda environment from [`../config/day/daycli.yaml`](../config/day/daycli.yaml) and installs this repo into it.

## 3. Create The Region Reference Bucket

Daylily expects a reference bucket in the target region. Use the installed `daylily-omics-references` CLI directly.

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

The resulting bucket name will include `omics-analysis`. With the standard clone flow that is typically `${BUCKET_PREFIX}-daylily-omics-analysis-${REGION}`.

Optional manual verification:

```bash
daylily-omics-references --profile "$AWS_PROFILE" --region "$REGION" \
  verify --bucket "${BUCKET_PREFIX}-daylily-omics-analysis-${REGION}" --exclude-b37
```

The Daylily preflight step also verifies the selected bucket before cluster creation.

## 4. Prepare The Cluster Config

Copy the template to a writable location, set `DAY_EX_CFG`, and pass it explicitly to the CLI.

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

Leave a key set to `PROMPTUSER` if you want the CLI to query AWS and prompt interactively. `DAY_EX_CFG` is just a shell convenience variable; the current Python CLI does not consume it implicitly, so pass `--config "$DAY_EX_CFG"` on every `preflight` and `create` invocation.

## 5. Optional Pricing Snapshot

If you want a raw spot-pricing snapshot before choosing an AZ:

```bash
python -m daylily_ec pricing snapshot \
  --region "$REGION" \
  --config config/day_cluster/prod_cluster.yaml \
  --profile "$AWS_PROFILE"
```

## 6. Run Preflight

```bash
export REGION_AZ=us-west-2c

python -m daylily_ec preflight \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --config "$DAY_EX_CFG"
```

Add `--pass-on-warn` if you have reviewed the warnings and intentionally want to continue past them.

## 7. Create The Cluster

```bash
python -m daylily_ec create \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --config "$DAY_EX_CFG"
```

Backward-compatible wrapper:

```bash
./bin/daylily-create-ephemeral-cluster \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --config "$DAY_EX_CFG"
```

The create workflow:

- runs preflight and aborts on failures
- resolves or creates baseline network resources as needed
- renders the cluster YAML and applies live spot pricing
- creates the cluster through ParallelCluster
- bootstraps the head node
- writes artifacts to `~/.config/daylily/`

## 8. What Success Looks Like

After a successful run:

- `~/.config/daylily/` contains a preflight report, a state snapshot, and rendered cluster YAML artifacts
- the head node has been bootstrapped with `DAY-EC`, `day-clone`, and the Daylily helper scripts
- you can continue with [operations.md](operations.md), starting at [Validate The Head Node](operations.md#validate-the-head-node)

If the cluster comes up but the head-node bootstrap needs to be re-run:

```bash
./bin/daylily-cfg-headnode \
  --pem ~/.ssh/<your-key>.pem \
  --region "$REGION" \
  --profile "$AWS_PROFILE" \
  --cluster <cluster-name>
```
