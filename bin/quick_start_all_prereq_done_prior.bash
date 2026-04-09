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

S3_BUCKET_URL=""
S3_BUCKET_NAME=""
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

DEFAULT_S3_BUCKET_NAME="$(python3 -c '
import os
import boto3
from daylily_ec.config import load_config, get_effective_default, resolve_value

cfg = load_config(os.environ["DAY_EX_CFG"])
triplet = cfg.ephemeral_cluster.config.get("s3_bucket_name")
cfg_value = (resolve_value(triplet) if triplet else "") or get_effective_default(cfg, "s3_bucket_name", "")
cfg_value = (cfg_value or "").removeprefix("s3://").split("/", 1)[0]
profile = os.environ["AWS_PROFILE"]
region = os.environ["REGION"]
candidates = []
non_public = []
choice = ""

try:
    session = boto3.Session(profile_name=profile, region_name=region)
    s3 = session.client("s3")
    buckets = [bucket.get("Name", "") for bucket in s3.list_buckets().get("Buckets", [])]
    for name in buckets:
        if "omics-analysis" not in name:
            continue
        try:
            loc = s3.get_bucket_location(Bucket=name).get("LocationConstraint")
            bucket_region = "us-east-1" if loc is None else str(loc)
        except Exception:
            continue
        if bucket_region == region:
            candidates.append(name)
    non_public = [candidate for candidate in sorted(candidates) if "public" not in candidate]
except Exception:
    candidates = []
    non_public = []

preferred = [
    cfg_value,
    f"{profile}-omics-analysis-{region}",
    f"{profile}-dayoa-omics-analysis-{region}",
]
for candidate in preferred:
    if candidate and candidate in candidates:
        choice = candidate
        break

if not choice and len(non_public) == 1:
    choice = non_public[0]
if not choice and len(candidates) == 1:
    choice = sorted(candidates)[0]
if not choice and cfg_value:
    choice = cfg_value

print(choice, end="")
')"
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
DEFAULT_S3_BUCKET_URL=""
[ -n "$DEFAULT_S3_BUCKET_NAME" ] && DEFAULT_S3_BUCKET_URL="s3://${DEFAULT_S3_BUCKET_NAME}"

if [ -z "${S3_BUCKET_URL:-}" ] && [ -n "$DEFAULT_S3_BUCKET_URL" ]; then
  S3_BUCKET_URL="$DEFAULT_S3_BUCKET_URL"
  printf 'Reference bucket URL [%s]\n' "$S3_BUCKET_URL"
fi
while [ -z "${S3_BUCKET_URL:-}" ]; do
  printf 'Reference bucket URL (s3://bucket)'
  [ -n "$DEFAULT_S3_BUCKET_URL" ] && printf ' [%s]' "$DEFAULT_S3_BUCKET_URL"
  printf ': '
  read -r S3_BUCKET_URL
  S3_BUCKET_URL="${S3_BUCKET_URL:-$DEFAULT_S3_BUCKET_URL}"
done
S3_BUCKET_URL="${S3_BUCKET_URL%/}"
S3_BUCKET_NAME="${S3_BUCKET_URL#s3://}"
S3_BUCKET_NAME="${S3_BUCKET_NAME%%/*}"
S3_BUCKET_URL="s3://${S3_BUCKET_NAME}"

while [ -z "${DAY_CONTACT_EMAIL:-}" ]; do
  printf 'Budget / heartbeat email'
  [ -n "$DEFAULT_DAY_CONTACT_EMAIL" ] && printf ' [%s]' "$DEFAULT_DAY_CONTACT_EMAIL"
  printf ': '
  read -r DAY_CONTACT_EMAIL
  DAY_CONTACT_EMAIL="${DAY_CONTACT_EMAIL:-$DEFAULT_DAY_CONTACT_EMAIL}"
done

export S3_BUCKET_URL S3_BUCKET_NAME DAY_CONTACT_EMAIL

python3 -c '
import os
from daylily_ec.config import load_config, write_config

cfg = load_config(os.environ["DAY_EX_CFG"])
updates = {
    "cluster_name": os.environ["CLUSTER_NAME"],
    "s3_bucket_name": os.environ["S3_BUCKET_NAME"],
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
