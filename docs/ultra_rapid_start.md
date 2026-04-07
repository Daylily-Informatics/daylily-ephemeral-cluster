# Ultra Rapid Start

This is the shortest copy-pasteable path to clone `main`, activate Daylily, create a cluster, connect to it, inspect it, check pricing, and delete it.

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
ssh -i ~/.ssh/daylily-demo-key.pem ubuntu@54.218.10.25
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
