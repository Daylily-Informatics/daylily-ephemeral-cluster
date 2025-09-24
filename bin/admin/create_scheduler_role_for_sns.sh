#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'

** TO BE RUN BY AN ADMIN LEVEL USER **

*** run 1x per region ***

Create or update an IAM role that EventBridge Scheduler can assume to publish to SNS.

USAGE:
  create_scheduler_role_for_sns.sh --region REGION [--profile PROFILE(admin)] [--role-name NAME]

Defaults:
  --role-name eventbridge-scheduler-to-sns

Outputs:
  Prints the IAM Role ARN on success.

Notes:
  - Grants sns:Publish ONLY to topics named: daylily-*-heartbeat in the target account+region.
  - Idempotent: safe to re-run; it will update trust and inline policy if needed.
EOF
}

ROLE_NAME="eventbridge-scheduler-to-sns"
REGION=""
PROFILE=""

# --- arg parse
while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)   REGION="$2"; shift 2 ;;
    --profile)  PROFILE="$2"; shift 2 ;;
    --role-name) ROLE_NAME="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$REGION" ]] || { echo "ERR: --region is required" >&2; usage >&2; exit 2; }

AWS=(aws)
[[ -n "${PROFILE}" ]] && AWS+=(--profile "$PROFILE")
AWS+=(--region "$REGION")

# --- sanity
"${AWS[@]}" sts get-caller-identity >/dev/null 2>&1 || {
  echo "ERR: Cannot call STS with provided credentials/region." >&2
  exit 3
}

ACCOUNT_ID="$("${AWS[@]}" sts get-caller-identity --query Account --output text)"

# --- documents
TRUST_DOC=$(cat <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowEventBridgeSchedulerAssume",
      "Effect": "Allow",
      "Principal": { "Service": "scheduler.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON
)

POLICY_DOC_TEMPLATE='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowPublishToDaylilyHeartbeatTopics",
      "Effect": "Allow",
      "Action": ["sns:Publish"],
      "Resource": "arn:aws:sns:__REGION__:__ACCOUNT__:daylily-*-heartbeat"
    }
  ]
}'

POLICY_DOC="${POLICY_DOC_TEMPLATE/__REGION__/${REGION}}"
POLICY_DOC="${POLICY_DOC/__ACCOUNT__/${ACCOUNT_ID}}"

INLINE_POLICY_NAME="eventbridge-scheduler-to-sns-inline"

# --- ensure role exists (idempotent)
ROLE_ARN=""
set +e
ROLE_ARN="$("${AWS[@]}" iam get-role --role-name "$ROLE_NAME" \
  --query 'Role.Arn' --output text 2>/dev/null)"
rc=$?
set -e

if [[ $rc -ne 0 || -z "$ROLE_ARN" || "$ROLE_ARN" == "None" ]]; then
  echo "Creating role: $ROLE_NAME"
  ROLE_ARN="$("${AWS[@]}" iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$TRUST_DOC" \
    --description "Role assumed by EventBridge Scheduler to publish to SNS (Daylily heartbeat)" \
    --query 'Role.Arn' --output text)"
  # small propagation delay
  sleep 5
else
  echo "Role exists: $ROLE_ARN"
  echo "Updating trust policy"
  "${AWS[@]}" iam update-assume-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-document "$TRUST_DOC"
fi

# --- attach inline policy (create or replace)
echo "Putting inline policy: $INLINE_POLICY_NAME"
"${AWS[@]}" iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "$INLINE_POLICY_NAME" \
  --policy-document "$POLICY_DOC"

# Optional: tag the role (helps audits)
"${AWS[@]}" iam tag-role --role-name "$ROLE_NAME" \
  --tags Key=Owner,Value=Daylily Key=Purpose,Value=SchedulerToSNS >/dev/null || true

# --- final echo
echo ""
echo "✅ Scheduler execution role is ready."
echo "ROLE ARN: ${ROLE_ARN}"
echo "Region:   ${REGION}"
echo "Account:  ${ACCOUNT_ID}"
