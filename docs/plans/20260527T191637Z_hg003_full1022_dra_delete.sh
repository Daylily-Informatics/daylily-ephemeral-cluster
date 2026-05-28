#!/usr/bin/env bash
set -o pipefail
cd /Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster
source ./activate
printf 'UTC_START=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'COMMAND=dyec mounts delete --association-id dra-0daa2bf3e769b75d2 --region us-west-2 --profile lsmc --wait\n'
set +e
dyec mounts delete --association-id dra-0daa2bf3e769b75d2 --region us-west-2 --profile lsmc --wait 2>&1
rc=$?
set -e
printf 'UTC_END=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'RC=%s\n' "$rc"
printf '%s\n' "$rc" > /Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/$RC
exec bash -l
