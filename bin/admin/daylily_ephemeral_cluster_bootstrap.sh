#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Bootstrap IAM for Daylily ephemeral cluster workflows (one-time admin).

Creates/updates two managed policies:

  - DaylilyEClusterPolicy
    Broad ephemeral-cluster ops permissions, attaches to a user you specify.

  - DaylilyPClusterLambdaAdjustRoles
    Minimal policy giving ParallelCluster Lambda roles the right to
    iam:AttachRolePolicy / iam:DetachRolePolicy on cluster roles (RoleHeadNode,
    RoleComputeFleet, RoleLoginNode).

USAGE:
  daylily_ephemeral_cluster_bootstrap.sh --region REGION --user USERNAME [--profile PROFILE]

OPTIONS:
  --region    AWS region (required)
  --user      IAM username to attach the DaylilyEClusterPolicy to (required)
  --profile   AWS CLI profile with admin rights (optional)

This only needs to be run once per account/region.
EOF
}

USER_NAME=""
REGION=""
PROFILE="${AWS_PROFILE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) USER_NAME="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$USER_NAME" ]] || { echo "ERR: --user required" >&2; usage >&2; exit 2; }
[[ -n "$REGION" ]] || { echo "ERR: --region required" >&2; usage >&2; exit 2; }

AWS=(aws)
[[ -n "$PROFILE" ]] && AWS+=(--profile "$PROFILE")
AWS+=(--region "$REGION")

ACCOUNT_ID="$("${AWS[@]}" sts get-caller-identity --query Account --output text)" || {
  echo "ERR: cannot query STS"; exit 3; }

# ---- policy documents ----

OPS_POLICY_NAME="DaylilyEClusterPolicy"
ADJUST_POLICY_NAME="DaylilyPClusterLambdaAdjustRoles"

OPS_POLICY_DOC=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": [
        "ec2:*","autoscaling:*","elasticloadbalancing:*","elasticfilesystem:*",
        "sns:*","scheduler:*","route53:*","apigateway:*","secretsmanager:*","ecr:*"
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
    { "Effect": "Allow", "Action": ["lambda:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": "cloudformation:*", "Resource": "*" },
    { "Effect": "Allow", "Action": ["fsx:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["dynamodb:*"], "Resource": "arn:aws:dynamodb:*:${ACCOUNT_ID}:table/parallelcluster-*" },
    { "Effect": "Allow", "Action": ["s3:*","s3:ListAllMyBuckets"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["budgets:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["cloudwatch:*","logs:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["imagebuilder:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["sns:*"], "Resource": ["arn:aws:sns:*:${ACCOUNT_ID}:ParallelClusterImage-*"] },
    { "Effect": "Allow", "Action": ["tag:*"], "Resource": "*" },
    { "Effect": "Allow", "Action": [
        "sns:GetTopicAttributes","sns:SetTopicAttributes","sns:Subscribe",
        "sns:Unsubscribe","sns:Publish","sns:DeleteTopic"
      ], "Resource": "arn:aws:sns:${REGION}:${ACCOUNT_ID}:*" }
  ]
}
JSON
)

ADJUST_POLICY_DOC=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow",
      "Action": [ "iam:AttachRolePolicy", "iam:DetachRolePolicy" ],
      "Resource": "arn:aws:iam::${ACCOUNT_ID}:role/*-Role*(HeadNode|ComputeFleet|LoginNode)*"
    }
  ]
}
JSON
)

# ---- helpers ----
create_or_update_policy() {
  local name="$1" doc="$2"
  local arn
  set +e
  arn="$("${AWS[@]}" iam list-policies --scope Local \
    --query "Policies[?PolicyName=='${name}'].Arn | [0]" --output text 2>/dev/null)"
  set -e
  if [[ -z "$arn" || "$arn" == "None" ]]; then
    echo "Creating policy ${name}"
    arn="$("${AWS[@]}" iam create-policy --policy-name "${name}" \
      --policy-document "${doc}" --query Policy.Arn --output text)"
  else
    echo "Updating policy ${name}"
    "${AWS[@]}" iam create-policy-version --policy-arn "${arn}" \
      --policy-document "${doc}" --set-as-default >/dev/null
  fi
  echo "${arn}"
}

# ---- create/update both ----
OPS_ARN=$(create_or_update_policy "${OPS_POLICY_NAME}" "${OPS_POLICY_DOC}")
ADJUST_ARN=$(create_or_update_policy "${ADJUST_POLICY_NAME}" "${ADJUST_POLICY_DOC}")

# ---- attach ops policy to user ----
echo "Attaching ${OPS_POLICY_NAME} to user ${USER_NAME}"
"${AWS[@]}" iam attach-user-policy --user-name "${USER_NAME}" --policy-arn "${OPS_ARN}" || true

echo "✅ Done."
echo "  - ${OPS_POLICY_NAME}: ${OPS_ARN} (attached to ${USER_NAME})"
echo "  - ${ADJUST_POLICY_NAME}: ${ADJUST_ARN}"
