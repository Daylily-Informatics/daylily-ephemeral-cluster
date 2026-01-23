#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Bootstrap global IAM policy for Daylily ephemeral cluster workflows.

This script creates or updates the global Daylily managed policy and optionally
attaches it to a specified IAM *group* (recommended) and ensures the target IAM
user is a member of that group. Run this once per AWS account, or again if
updates to the policy are released.

USAGE:
  daylily_ephemeral_cluster_bootstrap_global.sh \
    --user USERNAME \
    [--group GROUP] \
    [--profile PROFILE]

OPTIONS:
  --user      IAM username to grant access to (required)
  --group     IAM group to attach the Daylily global policy to (default: daylily-ephemeral-cluster)
  --profile   AWS CLI profile with admin rights (optional)
USAGE
}

USER_NAME=""
GROUP_NAME="daylily-ephemeral-cluster"
PROFILE="${AWS_PROFILE:-}"

while (( $# )); do
  case "$1" in
    --user) USER_NAME="${2:-}"; shift 2 ;;
	--group) GROUP_NAME="${2:-}"; shift 2 ;;
    --profile) PROFILE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

: "${USER_NAME:?ERR: --user required}"

[[ -n "${GROUP_NAME}" ]] || { echo "ERR: --group cannot be empty" >&2; exit 2; }

AWS=(aws)
[[ -n "$PROFILE" ]] && AWS+=(--profile "$PROFILE")

ACCOUNT_ID="$("${AWS[@]}" sts get-caller-identity --query Account --output text)" || {
  echo "ERR: unable to query AWS account" >&2
  exit 3
}

GLOBAL_POLICY_NAME="DaylilyGlobalEClusterPolicy"

GLOBAL_POLICY_DOC=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": [
        "ec2:*","autoscaling:*","elasticloadbalancing:*","elasticfilesystem:*",
        "scheduler:*","route53:*","apigateway:*","secretsmanager:*","ecr:*"
      ], "Resource": "*" },
    { "Effect": "Allow", "Action": [
        "iam:List*","iam:Get*","iam:SimulatePrincipalPolicy","iam:Create*",
        "iam:DeleteInstanceProfile","iam:AddRoleToInstanceProfile","iam:RemoveRoleFromInstanceProfile",
        "iam:AttachRolePolicy","iam:DetachRolePolicy","iam:TagRole","iam:PutRolePolicy","iam:DeleteRole*"
      ], "Resource": "*" },
    { "Effect": "Allow", "Action": ["iam:PassRole"], "Resource": ["arn:aws:iam::${ACCOUNT_ID}:role/*"] },
    { "Effect": "Allow", "Action": "iam:PassRole", "Resource": "*",
      "Condition": { "StringEquals": { "iam:PassedToService": "scheduler.amazonaws.com" } } },
    { "Effect": "Allow", "Action": ["cognito-idp:*","servicequotas:GetServiceQuota","ssm:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": "iam:CreateServiceLinkedRole", "Resource": "*",
      "Condition": { "StringLike": { "iam:AWSServiceName": [
        "spot.amazonaws.com","fsx.amazonaws.com","s3.data-source.lustre.fsx.amazonaws.com",
        "imagebuilder.amazonaws.com","ec2.amazonaws.com","lambda.amazonaws.com"
      ] } } },
    { "Effect": "Allow", "Action": [
      "iam:DeleteServiceLinkedRole",
      "iam:GetServiceLinkedRoleDeletionStatus"
      ], "Resource": "arn:aws:iam::*:role/aws-service-role/*" },
    { "Effect": "Allow", "Action": [
      "iam:List*","iam:Get*","iam:SimulatePrincipalPolicy","iam:Create*",
      "iam:DeleteInstanceProfile","iam:AddRoleToInstanceProfile","iam:RemoveRoleFromInstanceProfile",
      "iam:AttachRolePolicy","iam:DetachRolePolicy",
      "iam:TagRole","iam:UntagRole",
      "iam:PutRolePolicy","iam:DeleteRole*", "lambda:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": "cloudformation:*", "Resource": "*" },
    { "Effect": "Allow", "Action": ["fsx:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["dynamodb:*"], "Resource": "arn:aws:dynamodb:*:${ACCOUNT_ID}:table/parallelcluster-*" },
    { "Effect": "Allow", "Action": ["s3:*","s3:ListAllMyBuckets"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["budgets:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["cloudwatch:*","logs:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["imagebuilder:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["sns:*"], "Resource": ["arn:aws:sns:*:${ACCOUNT_ID}:ParallelClusterImage-*"] },
    { "Effect": "Allow", "Action": ["tag:*"], "Resource": "*" }
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

GLOBAL_ARN="$(create_or_update_policy "${GLOBAL_POLICY_NAME}" "${GLOBAL_POLICY_DOC}")"

ensure_user_exists() {
  local user="$1"
  "${AWS[@]}" iam get-user --user-name "${user}" >/dev/null 2>&1 || {
    echo "ERR: IAM user '${user}' not found." >&2
    exit 4
  }
}

ensure_group_exists() {
  local group="$1"
  if ! "${AWS[@]}" iam get-group --group-name "${group}" >/dev/null 2>&1; then
    >&2 echo "Creating IAM group: ${group}"
    "${AWS[@]}" iam create-group --group-name "${group}" >/dev/null
  fi
}

ensure_policy_attached_to_group() {
  local group="$1" policy_arn="$2"
  local attached
  attached=$(
    "${AWS[@]}" iam list-attached-group-policies --group-name "${group}" \
      --query "AttachedPolicies[?PolicyArn=='${policy_arn}'] | length(@)" --output text 2>/dev/null || echo "0"
  )
  if [[ "${attached}" == "0" ]]; then
    >&2 echo "Attaching ${GLOBAL_POLICY_NAME} to group ${group}"
    "${AWS[@]}" iam attach-group-policy --group-name "${group}" --policy-arn "${policy_arn}"
  else
    >&2 echo "${GLOBAL_POLICY_NAME} already attached to group ${group}"
  fi
}

ensure_user_in_group() {
  local user="$1" group="$2"
  local in_group
  in_group=$(
    "${AWS[@]}" iam list-groups-for-user --user-name "${user}" \
      --query "Groups[?GroupName=='${group}'] | length(@)" --output text 2>/dev/null || echo "0"
  )
  if [[ "${in_group}" == "0" ]]; then
    >&2 echo "Adding user ${user} to group ${group}"
    "${AWS[@]}" iam add-user-to-group --user-name "${user}" --group-name "${group}"
  else
    >&2 echo "User ${user} already in group ${group}"
  fi
}

ensure_user_exists "${USER_NAME}"
ensure_group_exists "${GROUP_NAME}"
ensure_policy_attached_to_group "${GROUP_NAME}" "${GLOBAL_ARN}"
ensure_user_in_group "${USER_NAME}" "${GROUP_NAME}"

cat <<SUMMARY
✅ Done.
  - ${GLOBAL_POLICY_NAME}: ${GLOBAL_ARN} (attached to IAM group ${GROUP_NAME})
  - IAM user ${USER_NAME} is a member of ${GROUP_NAME}
SUMMARY
