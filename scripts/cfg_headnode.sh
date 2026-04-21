#!/bin/bash
set -e
cd /Users/jmajor/projects/daylily/daylily-ephemeral-cluster-mega/daylily-ephemeral-cluster

eval "$(conda shell.bash hook 2>/dev/null)"
conda activate DAY-EC

export AWS_PROFILE=lsmc

source bin/daylily-cfg-headnode \
  ~/.ssh/lsmc-omics-us-west-2.pem \
  us-west-2 \
  lsmc \
  day-forge-usw2d

