#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Grant minimal permissions for a non-admin IAM user to wire heartbeat schedules.

USAGE:
  grant_daylily_heartbeat_perms.sh \
    --region REGION \
    --user USERNAME \
    --scheduler-role-arn ARN \
    [--profile PROFILE] \
    [--policy-name NAME]

Defaults:
  --policy-name daylily-heartbeat-wire

Grants (scoped):
  - scheduler:Create/Update/Delete/GetSchedule on:
      arn:aws:scheduler:REGION:ACCOUNT:schedule/default/daylily-*-heartbeat
    Also allows ListSchedules on * (List APIs are generally not resource-scoped).
  - iam:PassRole on the provided scheduler role ARN, with condition:
      iam:PassedToService = scheduler.amazonaws.com
  - sns:CreateTopic (CreateTopic does not support resource ARNs) but constrained by Condition:
      sns:TopicName = "daylily-*-heartbeat"
    and:
      sns:Subscribe, sns:GetTopicAttributes, sns:ListSubscriptionsByTopic
      on arn:aws:sns:REGION:ACCOUNT:daylily-*-heartbeat
EOF
}

REGION=""
USERNAME=""
SCHED_ROLE_ARN=""
PROFILE=""
POLICY_NAME="daylily-heartbeat-wire"

# --- arg parse
while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2 ;;
    --user) USERNAME="$2"; shift 2 ;;
    --scheduler-role-arn) SCHED_ROLE_ARN="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --policy-name) POL
ICY_NAME="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$REGION" ]] || { echo "ERR: --region is required" >&2; usage >&2; exit 2; }
[[ -n "$USERNAME" ]] || { echo "ERR: --user is required" >&2; usage >&2; exit 2; }
[[ -n "$SCHED_ROLE_ARN" ]] || { echo "ERR: --scheduler-role-arn is required" >&2; usage >&2; exit 2; }

AWS=(aws)
[[ -n "${PROFILE}" ]] && AWS+=(--profile "$PROFILE")
AWS+=(--region "$REGION")

# --- sanity: can we talk to STS?
"${AWS[@]}" sts get-caller-identity >/dev/null 2>&1 || {
  echo "ERR: Cannot call STS with provided credentials/region." >&2
  exit 3
}

ACCOUNT_ID="$("${AWS[@]}" sts get-caller-identity --query Account --output text)"

# Ensure the target IAM user exists
if ! "${AWS[@]}" iam get-user --user-name "$USERNAME" >/dev/null 2>&1; then
  echo "ERR: IAM user '$USERNAME' not found." >&2
  exit 4
fi

# Policy JSON (inline to user)
read -r -d '' POLICY_DOC <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SchedulerCRUDHeartbeat",
      "Effect": "Allow",
      "Action": [
        "scheduler:CreateSchedule",
        "scheduler:UpdateSchedule",
        "scheduler:DeleteSchedule",
        "scheduler:GetSchedule"
      ],
      "Resource": "arn:aws:scheduler:${REGION}:${ACCOUNT_ID}:schedule/default/daylily-*-heartbeat"
    },
    {
      "Sid": "SchedulerList",
      "Effect": "Allow",
      "Action": [
        "scheduler:ListSchedules"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowPassSchedulerRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "${SCHED_ROLE_ARN}",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "scheduler.amazonaws.com"
        }
      }
    },
    {
      "Sid": "AllowCreateSpecificTopicsByName",
      "Effect": "Allow",
      "Action": "sns:CreateTopic",
      "Resource": "*",
      "Condition": {
        "StringLike": {
          "sns:TopicName": "daylily-*-heartbeat"
        }
      }
    },
    {
      "Sid": "AllowManageHeartbeatTopics",
      "Effect": "Allow",
      "Action": [
        "sns:Subscribe",
        "sns:GetTopicAttributes",
        "sns:ListSubscriptionsByTopic"
      ],
      "Resource": "arn:aws:sns:${REGION}:${ACCOUNT_ID}:daylily-*-heartbeat"
    }
  ]
}
JSON

echo "Attaching inline policy '${POLICY_NAME}' to user '${USERNAME}' in ${REGION} (acct ${ACCOUNT_ID})..."
"${AWS[@]}" iam put-user-policy \
  --user-name "${USERNAME}" \
  --policy-name "${POLICY_NAME}" \
  --policy-document "${POLICY_DOC}"

echo "✅ Granted minimal heartbeat wiring permissions to user '${USERNAME}'."
echo "   - scheduler:Create/Update/Delete/GetSchedule on default/daylily-*-heartbeat"
echo "   - scheduler:ListSchedules on *"
echo "   - iam:PassRole for ${SCHED_ROLE_ARN} (to scheduler.amazonaws.com)"
echo "   - sns:CreateTopic constrained by TopicName daylily-*-heartbeat"
echo "   - sns:Subscribe/GetTopicAttributes/ListSubscriptionsByTopic on daylily-*-heartbeat"
