#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "Usage: $0 <cluster-name> <region>" >&2
  exit 1
fi

CLUSTER_NAME="$1"
REGION="$2"

echo "THIS IS NOT WORKING YET. DO NOT USE THIS SCRIPT." >&2
echo "Please use 'pcluster ssh' instead, which is the recommended way to connect for now." >&2
exit 1

# Ensure required commands exist
for cmd in aws pcluster; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: '$cmd' not found in PATH" >&2
    exit 1
  fi
done


if [ -z "$REGION" ] || [ "$REGION" = "None" ]; then
  echo "ERROR: Could not determine AWS region" >&2
  exit 1
fi

# Get head node instance ID
HEADNODE_INSTANCE_ID="$(pcluster describe-cluster-instances \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION" \
  --query 'instances[?nodeType==`HeadNode`].instanceId | [0]' \
  --output text)"

if [ -z "$HEADNODE_INSTANCE_ID" ] || [ "$HEADNODE_INSTANCE_ID" = "None" ]; then
  echo "ERROR: Could not find head node instance for cluster '$CLUSTER_NAME'" >&2
  exit 1
fi

echo "Connecting to head node via SSM"
echo "  Cluster : $CLUSTER_NAME"
echo "  Region  : $REGION"
echo "  Instance: $HEADNODE_INSTANCE_ID"
echo

exec aws ssm start-session \
  --region "$REGION" \
  --target "$HEADNODE_INSTANCE_ID"
