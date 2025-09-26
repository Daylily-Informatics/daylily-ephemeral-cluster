#!/usr/bin/env bash
set -euo pipefail

cat <<'MSG'
This helper has been split into two dedicated bootstrap scripts:

  - bin/admin/daylily_ephemeral_cluster_bootstrap_global.sh
      Run once per AWS account to create the global Daylily policy and
      attach it to the target IAM users.

  - bin/admin/daylily_ephemeral_cluster_bootstrap_region.sh
      Run once per AWS region to create the region-scoped policy and update
      the ParallelCluster Lambda adjust policy.

Please invoke the appropriate script directly.
MSG
