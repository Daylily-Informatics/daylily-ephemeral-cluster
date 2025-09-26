#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Bootstrap region-scoped IAM policies for Daylily ephemeral cluster workflows.

This script creates or updates the Daylily region policy alongside the
ParallelCluster Lambda adjust policy, and attaches the region policy to a given
user. Run this once per AWS region in which you operate Daylily clusters.

USAGE:
  daylily_ephemeral_cluster_bootstrap_region.sh \\
    --region REGION --user USERNAME [--profile PROFILE]

OPTIONS:
  --region    AWS region to scope the policy to (required)
  --user      IAM username to attach the Daylily region policy to (required)
  --profile   AWS CLI profile with admin rights (optional)
USAGE
}

USER_NAME=""
REGION=""
PROFILE="${AWS_PROFILE:-}"

while (( $# )); do
  case "$1" in
    --user) USER_NAME="${2:-}"; shift 2 ;;
    --region) REGION="${2:-}"; shift 2 ;;
    --profile) PROFILE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

: "${USER_NAME:?ERR: --user required}"
: "${REGION:?ERR: --region required}"

AWS=(aws)
[[ -n "$PROFILE" ]] && AWS+=(--profile "$PROFILE")
AWS+=(--region "$REGION")

ACCOUNT_ID="$("${AWS[@]}" sts get-caller-identity --query Account --output text)" || {
  echo "ERR: unable to query AWS account" >&2
  exit 3
}

REGION_POLICY_NAME="DaylilyRegionalEClusterPolicy-${REGION}"
ADJUST_POLICY_NAME="DaylilyPClusterLambdaAdjustRoles"

REGION_POLICY_DOC=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sns:GetTopicAttributes",
        "sns:SetTopicAttributes",
        "sns:Subscribe",
        "sns:Unsubscribe",
        "sns:Publish",
        "sns:DeleteTopic"
      ],
      "Resource": "arn:aws:sns:${REGION}:${ACCOUNT_ID}:*"
    }
  ]
}
JSON
)

ADJUST_POLICY_DOC=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [ "iam:AttachRolePolicy", "iam:DetachRolePolicy" ],
      "Resource": [
        "arn:aws:iam::${ACCOUNT_ID}:role/*-RoleHeadNode-*",
        "arn:aws:iam::${ACCOUNT_ID}:role/*-RoleComputeFleet-*",
        "arn:aws:iam::${ACCOUNT_ID}:role/*-RoleLoginNode-*"
      ]
    }
  ]
}
JSON
)

create_or_update_policy() {
  local name="$1" doc="$2" arn tmp_json
  arn="$("${AWS[@]}" iam list-policies --scope Local \
         --query "Policies[?PolicyName=='${name}'].Arn | [0]" \
         --output text 2>/dev/null || true)"

  tmp_json="$(mktemp)"
  printf '%s\n' "${doc}" > "${tmp_json}"

  if [[ -z "$arn" || "$arn" == "None" ]]; then
    >&2 echo "Creating policy ${name}"
    arn="$("${AWS[@]}" iam create-policy \
            --policy-name "${name}" \
            --policy-document "file://${tmp_json}" \
            --query Policy.Arn --output text)"
  else
    >&2 echo "Updating policy ${name}"
    "${AWS[@]}" iam create-policy-version \
      --policy-arn "${arn}" \
      --policy-document "file://${tmp_json}" \
      --set-as-default >/dev/null
  fi

  rm -f "${tmp_json}"
  printf '%s\n' "${arn}"
}

REGION_ARN="$(create_or_update_policy "${REGION_POLICY_NAME}" "${REGION_POLICY_DOC}")"
ADJUST_ARN="$(create_or_update_policy "${ADJUST_POLICY_NAME}" "${ADJUST_POLICY_DOC}")"

sleep 7

echo "Scanning for ParallelCluster Lambda roles to grant attach/detach..."
ROLE_NAMES="$("${AWS[@]}" iam list-roles \
  --query "Roles[?starts_with(RoleName, 'ParallelClusterLambdaRole-')].RoleName" \
  --output text || true)"

if [[ -z "${ROLE_NAMES}" ]]; then
  echo "No ParallelClusterLambdaRole-* roles found yet. Create a cluster and re-run this script to attach the adjust policy."
else
  for RN in ${ROLE_NAMES}; do
    echo "Ensuring ${ADJUST_POLICY_NAME} is attached to role: ${RN}"
    ATTACHED="$("${AWS[@]}" iam list-attached-role-policies --role-name "${RN}" \
      --query "AttachedPolicies[?PolicyArn=='${ADJUST_ARN}'] | length(@)" --output text)"
    if [[ "${ATTACHED}" != "0" ]]; then
      echo "  - already attached"
    else
      "${AWS[@]}" iam attach-role-policy --role-name "${RN}" --policy-arn "${ADJUST_ARN}"
      echo "  - attached"
    fi
  done
fi

echo "Attaching ${REGION_POLICY_NAME} to user ${USER_NAME}"
"${AWS[@]}" iam attach-user-policy --user-name "${USER_NAME}" --policy-arn "${REGION_ARN}" || true

cat <<SUMMARY
✅ Done.
  - ${REGION_POLICY_NAME}: ${REGION_ARN} (attached to ${USER_NAME})
  - ${ADJUST_POLICY_NAME}: ${ADJUST_ARN}
SUMMARY
