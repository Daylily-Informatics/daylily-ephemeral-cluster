#!/bin/sh
set -e
cd /Users/jmajor/projects/daylily/daylily-ephemeral-cluster-mega/daylily-ephemeral-cluster
eval "$(conda shell.zsh hook 2>/dev/null)"
conda activate DAY-EC
export AWS_PROFILE=lsmc

CLUSTER=day-forge-usw2d
REGION=us-west-2
MAX_POLLS=30
INTERVAL=60

i=0
while [ "$i" -lt "$MAX_POLLS" ]; do
    STATUS=$(pcluster describe-cluster -n "$CLUSTER" --region "$REGION" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('clusterStatus','UNKNOWN'))")
    echo "$(date '+%H:%M:%S') poll=$i status=$STATUS"
    if [ "$STATUS" = "CREATE_COMPLETE" ] || [ "$STATUS" = "CREATE_FAILED" ]; then
        echo "FINAL_STATUS=$STATUS"
        pcluster describe-cluster -n "$CLUSTER" --region "$REGION" 2>/dev/null
        exit 0
    fi
    i=$((i + 1))
    sleep "$INTERVAL"
done
echo "TIMEOUT after $MAX_POLLS polls"
exit 1

