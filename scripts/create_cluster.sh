#!/bin/sh
set -e
cd /Users/jmajor/projects/daylily/daylily-ephemeral-cluster-mega/daylily-ephemeral-cluster

eval "$(conda shell.zsh hook 2>/dev/null)"
conda activate DAY-EC

export AWS_PROFILE=lsmc

python -m daylily_ec create \
  --region-az us-west-2d \
  --profile lsmc \
  --config ~/.config/daylily/day-forge-usw2d_cli_cfg.yaml \
  --pass-on-warn \
  --non-interactive

