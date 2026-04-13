# Ultra Rapid Start

This is the shortest repo-checkout path for operators who already have:

- a valid `DAY_EX_CFG`
- a reference bucket
- an AWS CLI profile with the required permissions

```bash
source ./activate

export AWS_PROFILE=daylily-service-lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER_NAME=daylily-demo-cluster
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"

daylily-ec preflight \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --config "$DAY_EX_CFG"

daylily-ec create \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --config "$DAY_EX_CFG"

bin/daylily-ssh-into-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

When the run is complete:

```bash
daylily-ec export \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION" \
  --target-uri analysis_results/ubuntu \
  --output-dir .

daylily-ec delete \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION"
```

For staging and workflow launch helpers, continue with [operations.md](operations.md).
