#!/usr/bin/env bash
set -e
cd /Users/jmajor/projects/daylily/daylily-ephemeral-cluster-mega/daylily-ephemeral-cluster
eval "$(conda shell.bash hook 2>/dev/null)"
conda activate DAY-EC
export AWS_PROFILE=daylily-service-lsmc
echo "=== Running headnode configuration for day-test-uswest2d ==="
source ./bin/daylily-cfg-headnode ~/.ssh/lsmc-omics-us-west-2.pem us-west-2 daylily-service-lsmc day-test-uswest2d
echo ""
echo "=== Headnode configuration script completed ==="
