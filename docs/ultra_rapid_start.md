# Ultra Rapid Start

This is the shortest copy-pasteable path to clone `main`, activate Daylily, create a cluster, connect to it, inspect it, check pricing, and delete it.

## One Paste To Start The Build

Paste this block into your shell. It prompts for the values used later in this doc, clones `main`, activates the repo, prepares the config, runs pricing and preflight, then starts `daylily-ec create`. The `yes '' |` line feeds Enter to any remaining create-time prompts so the shown defaults or option `[1]` are accepted automatically.

```bash
printf 'AWS profile [daylily-service]: '
read -r AWS_PROFILE
AWS_PROFILE="${AWS_PROFILE:-daylily-service}"

printf 'AWS region [us-west-2]: '
read -r REGION
REGION="${REGION:-us-west-2}"

printf 'AWS region-AZ [us-west-2c]: '
read -r REGION_AZ
REGION_AZ="${REGION_AZ:-us-west-2c}"

printf 'Cluster name [daylily-demo-cluster]: '
read -r CLUSTER_NAME
CLUSTER_NAME="${CLUSTER_NAME:-daylily-demo-cluster}"

while [ -z "${S3_BUCKET_NAME:-}" ]; do
  printf 'Reference bucket name (the omics-analysis bucket): '
  read -r S3_BUCKET_NAME
done

while [ -z "${SSH_KEY_NAME:-}" ]; do
  printf 'SSH key name (without .pem): '
  read -r SSH_KEY_NAME
done

while [ -z "${DAY_CONTACT_EMAIL:-}" ]; do
  printf 'Budget / heartbeat email: '
  read -r DAY_CONTACT_EMAIL
done

export AWS_PROFILE REGION REGION_AZ CLUSTER_NAME S3_BUCKET_NAME SSH_KEY_NAME DAY_CONTACT_EMAIL
export PEM_PATH="$HOME/.ssh/${SSH_KEY_NAME}.pem"

git clone -b main https://github.com/Daylily-Informatics/daylily-ephemeral-cluster.git
cd daylily-ephemeral-cluster
source ./activate

mkdir -p ~/.config/daylily
cp config/daylily_ephemeral_cluster_template.yaml ~/.config/daylily/daylily_ephemeral_cluster.yaml
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"

python3 -c '
import os
from daylily_ec.config import load_config, write_config

cfg = load_config(os.environ["DAY_EX_CFG"])
updates = {
    "cluster_name": os.environ["CLUSTER_NAME"],
    "s3_bucket_name": os.environ["S3_BUCKET_NAME"],
    "ssh_key_name": os.environ["SSH_KEY_NAME"],
    "budget_email": os.environ["DAY_CONTACT_EMAIL"],
    "heartbeat_email": os.environ["DAY_CONTACT_EMAIL"],
}
for key, value in updates.items():
    triplet = cfg.ephemeral_cluster.config[key]
    triplet.action = "USESETVALUE"
    triplet.default_value = value
    triplet.set_value = value
write_config(cfg, os.environ["DAY_EX_CFG"])
'

daylily-ec pricing snapshot --region "$REGION" --config config/day_cluster/prod_cluster.yaml --profile "$AWS_PROFILE"
daylily-ec preflight --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG"
yes '' | daylily-ec create --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG"
```

If you want to answer prompts manually instead, remove `yes '' |` from the final command.

The rest of this doc shows the same lifecycle as separate commands.

## Clone Main

```bash
git clone -b main https://github.com/Daylily-Informatics/daylily-ephemeral-cluster.git
cd daylily-ephemeral-cluster
```

## Activate

```bash
source ./activate
```

## Prepare Config

```bash
mkdir -p ~/.config/daylily
cp config/daylily_ephemeral_cluster_template.yaml ~/.config/daylily/daylily_ephemeral_cluster.yaml
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
```

Set `cluster_name:` in `"$DAY_EX_CFG"` to `daylily-demo-cluster` before you create the cluster so the later info and delete commands match the created name.

## Set Operator Variables

```bash
export AWS_PROFILE=daylily-service
export REGION=us-west-2
export REGION_AZ=us-west-2c
export CLUSTER_NAME=daylily-demo-cluster
export SSH_KEY_NAME=daylily-demo-key
export PEM_PATH="$HOME/.ssh/${SSH_KEY_NAME}.pem"
```

## Check Pricing First

```bash
daylily-ec pricing snapshot --region "$REGION" --config config/day_cluster/prod_cluster.yaml --profile "$AWS_PROFILE"
```

## Preflight

```bash
daylily-ec preflight --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG"
```

## Create The Cluster

```bash
daylily-ec create --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG"
```

The real SSH command is also printed by `daylily-ec create` at the end of a successful run.

## SSH Into The Headnode

Hypothetical example IP:

```bash
ssh -i "$PEM_PATH" ubuntu@54.218.10.25
```

## Check Cluster Info

```bash
daylily-ec cluster-info --region "$REGION" --profile "$AWS_PROFILE"
pcluster describe-cluster -n "$CLUSTER_NAME" --region "$REGION"
```

## Get AWS Region-AZ Pricing Info

```bash
daylily-ec pricing snapshot --region "$REGION" --config config/day_cluster/prod_cluster.yaml --profile "$AWS_PROFILE"
```

Use the snapshot output to compare instance pricing before choosing or changing `REGION_AZ`.

## Delete The Cluster

```bash
daylily-ec delete --cluster-name "$CLUSTER_NAME" --region "$REGION"
```
