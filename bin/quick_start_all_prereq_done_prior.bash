#!/bin/bash


printf 'AWS profile [daylily-service]: '
read -r AWS_PROFILE
AWS_PROFILE="${AWS_PROFILE:-daylily-service}"

printf 'AWS region [us-west-2]: '
read -r REGION
REGION="${REGION:-us-west-2}"

printf 'AWS region-AZ [us-west-2d]: '
read -r REGION_AZ
REGION_AZ="${REGION_AZ:-us-west-2d}"

printf 'Cluster name [daylily-demo-cluster]: '
read -r CLUSTER_NAME
CLUSTER_NAME="${CLUSTER_NAME:-daylily-demo-cluster}"

REF_S3_URI="${REF_S3_URI:-}"
CONTROL_DATA_S3_URI="${CONTROL_DATA_S3_URI:-}"
STAGE_S3_URI="${STAGE_S3_URI:-}"
DAY_CONTACT_EMAIL=""

export AWS_PROFILE REGION REGION_AZ CLUSTER_NAME
export REPO_DIR=daylily-ephemeral-cluster-0.7.620

if [ -f ./activate ] && [ -f ./environment.yaml ]; then
  :
elif [ -f "./${REPO_DIR}/activate" ] && [ -f "./${REPO_DIR}/environment.yaml" ]; then
  cd "./${REPO_DIR}" || return 1 2>/dev/null || exit 1
else
  git clone --branch 0.7.620 --depth 1 https://github.com/Daylily-Informatics/daylily-ephemeral-cluster.git "./${REPO_DIR}" || return 1 2>/dev/null || exit 1
  cd "./${REPO_DIR}" || return 1 2>/dev/null || exit 1
fi

source ./activate

mkdir -p ~/.config/daylily
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
if [ ! -f "$DAY_EX_CFG" ]; then
  cp config/daylily_ephemeral_cluster_template.yaml "$DAY_EX_CFG"
fi

DEFAULT_DAY_CONTACT_EMAIL="$(python3 -c '
import os
from daylily_ec.config import load_config, get_effective_default, resolve_value

cfg = load_config(os.environ["DAY_EX_CFG"])
budget = cfg.ephemeral_cluster.config.get("budget_email")
heartbeat = cfg.ephemeral_cluster.config.get("heartbeat_email")
value = (
    (resolve_value(budget) if budget else "")
    or get_effective_default(cfg, "budget_email", "")
    or (resolve_value(heartbeat) if heartbeat else "")
    or get_effective_default(cfg, "heartbeat_email", "")
)
print((value or ""), end="")
')"

prompt_required_s3_uri() {
  local var_name="$1"
  local label="$2"
  local value
  eval "value=\"\${${var_name}:-}\""
  while [ -z "$value" ]; do
    printf '%s (s3://...): ' "$label"
    read -r value
  done
  value="${value%/}"
  if [[ "$value" != s3://* ]]; then
    printf 'Error: %s must be an s3:// URI\n' "$label" >&2
    exit 2
  fi
  eval "${var_name}=\"\$value\""
}

prompt_required_s3_uri REF_S3_URI "Reference S3 URI"
prompt_required_s3_uri CONTROL_DATA_S3_URI "Control-data S3 URI"
prompt_required_s3_uri STAGE_S3_URI "Staging S3 URI"

while [ -z "${DAY_CONTACT_EMAIL:-}" ]; do
  printf 'Budget / heartbeat email'
  [ -n "$DEFAULT_DAY_CONTACT_EMAIL" ] && printf ' [%s]' "$DEFAULT_DAY_CONTACT_EMAIL"
  printf ': '
  read -r DAY_CONTACT_EMAIL
  DAY_CONTACT_EMAIL="${DAY_CONTACT_EMAIL:-$DEFAULT_DAY_CONTACT_EMAIL}"
done

export REF_S3_URI CONTROL_DATA_S3_URI STAGE_S3_URI DAY_CONTACT_EMAIL

python3 -c '
import os
from daylily_ec.config import load_config, write_config

cfg = load_config(os.environ["DAY_EX_CFG"])
updates = {
    "cluster_name": os.environ["CLUSTER_NAME"],
    "reference_s3_uri": os.environ["REF_S3_URI"],
    "control_data_s3_uri": os.environ["CONTROL_DATA_S3_URI"],
    "stage_s3_uri": os.environ["STAGE_S3_URI"],
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
daylily-ec preflight --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG" --pass-on-warn
yes '' | daylily-ec create --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG" --pass-on-warn
