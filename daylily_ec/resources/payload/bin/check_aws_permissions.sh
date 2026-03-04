#!/bin/bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: check_aws_permissions.sh [options] <iam-username>

Simulate whether an IAM user has the permissions required by the Daylily
service-cluster policy template (packaged with this repo).

Options:
  --profile PROFILE   AWS CLI profile to use (defaults to AWS_PROFILE)
  --region REGION     AWS region for AWS CLI calls (defaults to AWS_REGION/AWS_DEFAULT_REGION, else us-west-2)
  -h, --help          Show this help message and exit

Requires:
  aws, jq, perl
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required command '$1' not found in PATH" >&2
    exit 1
  fi
}

resolve_daylily_res_dir() {
  if [[ -n "${DAYLILY_EC_RESOURCES_DIR:-}" ]]; then
    echo "${DAYLILY_EC_RESOURCES_DIR}"
    return 0
  fi
  if command -v daylily-ec >/dev/null 2>&1; then
    daylily-ec resources-dir
    return 0
  fi
  local script_dir repo_root
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  repo_root="$(cd "${script_dir}/.." && pwd)"
  if [[ -d "${repo_root}/config" ]]; then
    echo "${repo_root}"
    return 0
  fi
  echo "Error: could not resolve Daylily resources dir. Set DAYLILY_EC_RESOURCES_DIR or install daylily-ephemeral-cluster." >&2
  return 1
}

aws_profile="${AWS_PROFILE:-}"
region="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-west-2}}"
iam_username=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --profile)
      aws_profile="$2"
      shift 2
      ;;
    --region)
      region="$2"
      shift 2
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      if [[ -z "$iam_username" ]]; then
        iam_username="$1"
        shift
      else
        echo "Unexpected argument: $1" >&2
        usage
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$iam_username" ]]; then
  echo "Error: IAM username is required." >&2
  usage
  exit 1
fi
if [[ -z "$aws_profile" ]]; then
  echo "Error: AWS profile not specified. Set AWS_PROFILE or pass --profile." >&2
  exit 1
fi

require_cmd aws
require_cmd jq
require_cmd perl

RES_DIR="$(resolve_daylily_res_dir)" || exit 1

# Variables
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text --profile "$aws_profile" --region "$region")"
USER_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:user/${iam_username}"

TMP_FILE="$(mktemp)"
cleanup() { rm -f "$TMP_FILE" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# Copy the template JSON file to a temporary file
cp "${RES_DIR}/config/aws/daylily-service-cluster-policy.json" "$TMP_FILE"

# Replace placeholders in the temporary file (<AWS_ACCOUNT_ID>)
perl -pi -e "s/<AWS_ACCOUNT_ID>/${AWS_ACCOUNT_ID}/g" "$TMP_FILE"

POLICY_FILE=$TMP_FILE

# Extract actions and resources
ACTIONS=($(jq -r '[.Statement[].Action] | flatten | .[]' "$POLICY_FILE"))
RESOURCES=($(jq -r '[.Statement[].Resource] | flatten | .[]' "$POLICY_FILE"))

# Batch size for actions (AWS limit is 128 characters per action; we'll use 10 actions per batch for safety)
BATCH_SIZE=10

# Loop through actions in batches
for ((i = 0; i < ${#ACTIONS[@]}; i += BATCH_SIZE)); do
    ACTION_BATCH=("${ACTIONS[@]:i:BATCH_SIZE}")
    ACTION_BATCH_STRING=$(printf ",%s" "${ACTION_BATCH[@]}")
    ACTION_BATCH_STRING=${ACTION_BATCH_STRING:1} # Remove leading comma

    echo "Testing actions: $ACTION_BATCH_STRING"

    # Run simulation for the current action batch
    aws iam simulate-principal-policy \
        --policy-source-arn "$USER_ARN" \
        --action-names $ACTION_BATCH_STRING \
        --resource-arns $(printf "%s " "${RESOURCES[@]}") \
        --profile "$aws_profile" \
        --region "$region"
done
