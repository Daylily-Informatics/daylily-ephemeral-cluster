#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Bootstrap global IAM policy for Daylily ephemeral cluster workflows.

This script creates or updates the global Daylily managed policy and optionally
attaches it to a specified IAM user. Run this once per AWS account, or again if
updates to the policy are released.

USAGE:
  daylily_ephemeral_cluster_bootstrap_global.sh --user USERNAME [--profile PROFILE]

OPTIONS:
  --user      IAM username to attach the Daylily global policy to (required)
  --profile   AWS CLI profile with admin rights (optional)
USAGE
}

USER_NAME=""
PROFILE="${AWS_PROFILE:-}"

while (( $# )); do
  case "$1" in
    --user) USER_NAME="${2:-}"; shift 2 ;;
    --profile) PROFILE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

: "${USER_NAME:?ERR: --user required}"

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

>&2 echo "Attaching ${GLOBAL_POLICY_NAME} to user ${USER_NAME}"
"${AWS[@]}" iam attach-user-policy --user-name "${USER_NAME}" --policy-arn "${GLOBAL_ARN}" || true

cat <<SUMMARY
✅ Done.
  - ${GLOBAL_POLICY_NAME}: ${GLOBAL_ARN} (attached to ${USER_NAME})
SUMMARY
