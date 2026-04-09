#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: $0 <cluster-name> <region>" >&2
  exit 0
fi

if [ $# -ne 2 ]; then
  echo "Usage: $0 <cluster-name> <region>" >&2
  exit 1
fi

CLUSTER_NAME="$1"
REGION="$2"

exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/daylily-ssh-into-headnode" \
  --cluster "$CLUSTER_NAME" \
  --region "$REGION"
