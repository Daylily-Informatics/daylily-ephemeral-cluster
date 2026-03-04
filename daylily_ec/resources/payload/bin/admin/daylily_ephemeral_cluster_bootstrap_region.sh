#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Bootstrap region-scoped IAM policies for Daylily ephemeral cluster workflows.

This script creates or updates the Daylily region policy alongside the
ParallelCluster Lambda adjust policy.

It attaches the region policy to an IAM *group* (recommended) and ensures the
target IAM user is a member of that group. Run this once per AWS region in which
you operate Daylily clusters.

USAGE:
  daylily_ephemeral_cluster_bootstrap_region.sh \\
    --region REGION --user USERNAME [--group GROUP] [--profile PROFILE]

OPTIONS:
  --region    AWS region to scope the policy to (required)
  --user      IAM username to grant access to (required)
  --group     IAM group to attach the Daylily region policy to (default: daylily-ephemeral-cluster)
  --profile   AWS CLI profile with admin rights (optional)
USAGE
}

USER_NAME=""
REGION=""
GROUP_NAME="daylily-ephemeral-cluster"
PROFILE="${AWS_PROFILE:-}"

while (( $# )); do
  case "$1" in
    --user) USER_NAME="${2:-}"; shift 2 ;;
    --region) REGION="${2:-}"; shift 2 ;;
	--group) GROUP_NAME="${2:-}"; shift 2 ;;
    --profile) PROFILE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

: "${USER_NAME:?ERR: --user required}"
: "${REGION:?ERR: --region required}"
[[ -n "${GROUP_NAME}" ]] || { echo "ERR: --group cannot be empty" >&2; exit 2; }

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
      "Resource": "*"
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
    mapfile -t OLD_VERSIONS < <(
      "${AWS[@]}" iam list-policy-versions \
        --policy-arn "${arn}" \
        --query 'Versions[?IsDefaultVersion==`false`]|sort_by(@,&CreateDate)[].VersionId' \
        --output text | tr '\t' '\n' | sed '/^$/d'
    )

    while (( ${#OLD_VERSIONS[@]} >= 4 )); do
      OLDEST_VERSION="${OLD_VERSIONS[0]}"
      >&2 echo "Deleting oldest non-default version ${OLDEST_VERSION} for ${name}"
      "${AWS[@]}" iam delete-policy-version \
        --policy-arn "${arn}" \
        --version-id "${OLDEST_VERSION}"
      mapfile -t OLD_VERSIONS < <(
        "${AWS[@]}" iam list-policy-versions \
          --policy-arn "${arn}" \
          --query 'Versions[?IsDefaultVersion==`false`]|sort_by(@,&CreateDate)[].VersionId' \
          --output text | tr '\t' '\n' | sed '/^$/d'
      )
    done

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
    echo "Creating IAM group: ${group}"
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
    echo "Attaching ${REGION_POLICY_NAME} to group ${group}"
    "${AWS[@]}" iam attach-group-policy --group-name "${group}" --policy-arn "${policy_arn}"
  else
    echo "${REGION_POLICY_NAME} already attached to group ${group}"
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
    echo "Adding user ${user} to group ${group}"
    "${AWS[@]}" iam add-user-to-group --user-name "${user}" --group-name "${group}"
  else
    echo "User ${user} already in group ${group}"
  fi
}

ensure_user_exists "${USER_NAME}"
ensure_group_exists "${GROUP_NAME}"
ensure_policy_attached_to_group "${GROUP_NAME}" "${REGION_ARN}"
ensure_user_in_group "${USER_NAME}" "${GROUP_NAME}"

cat <<SUMMARY
✅ Done.
  - ${REGION_POLICY_NAME}: ${REGION_ARN} (attached to IAM group ${GROUP_NAME})
  - IAM user ${USER_NAME} is a member of ${GROUP_NAME}
  - ${ADJUST_POLICY_NAME}: ${ADJUST_ARN}
SUMMARY
