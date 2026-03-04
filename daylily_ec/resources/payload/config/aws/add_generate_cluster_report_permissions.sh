#!/usr/bin/env sh
set -eu

# Example helper for granting Daylily cost-report permissions via an IAM group.
#
# Run this as an admin (or equivalent) profile.

export AWS_PROFILE="YOURADMINUSERPROFILE"

GROUP_NAME="${GROUP_NAME:-daylily-ephemeral-cluster}"
USER_NAME="${USER_NAME:-daylily-service}"
ACCOUNT_ID="${ACCOUNT_ID:-108782052779}"

aws iam create-policy \
  --policy-name DaylilyCostRead \
  --policy-document file://config/aws/generate_cluster_report.json >/dev/null 2>&1 || true

aws iam create-group --group-name "${GROUP_NAME}" >/dev/null 2>&1 || true

aws iam attach-group-policy \
  --group-name "${GROUP_NAME}" \
  --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/DaylilyCostRead" >/dev/null 2>&1 || true

aws iam add-user-to-group \
  --user-name "${USER_NAME}" \
  --group-name "${GROUP_NAME}" >/dev/null 2>&1 || true

echo "Done: ensured DaylilyCostRead is attached to group '${GROUP_NAME}' and user '${USER_NAME}' is a member." >&2