#!/bin/bash
set -euo pipefail

resolve_daylily_res_dir() {
    if [[ -n "${DAYLILY_EC_RESOURCES_DIR:-}" ]]; then
        echo "${DAYLILY_EC_RESOURCES_DIR}"
        return 0
    fi
    if command -v daylily-ec >/dev/null 2>&1; then
        daylily-ec resources-dir
        return 0
    fi
    local script_dir repo_root
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    repo_root="$(cd "${script_dir}/.." && pwd)"
    if [[ -d "${repo_root}/config" ]]; then
        echo "${repo_root}"
        return 0
    fi
    echo "Error: could not resolve Daylily resources dir. Set DAYLILY_EC_RESOURCES_DIR or install daylily-ephemeral-cluster." >&2
    return 1
}

RES_DIR="$(resolve_daylily_res_dir)" || exit 1

# Check if we're in a Git repository
if git rev-parse --is-inside-work-tree &>/dev/null; then
    # Get the repository name (extract from remote URL)
    repo_name=$(basename -s .git "$(git config --get remote.origin.url 2>/dev/null)")

    # Get the current branch name (if on a branch)
    branch_name=$(git symbolic-ref --short HEAD 2>/dev/null || echo "N/A")

    # Get the latest commit hash
    commit_hash=$(git rev-parse HEAD 2>/dev/null)
else
    repo_name="daylily-ephemeral-cluster"
    branch_name="N/A"
    commit_hash="N/A"
fi

GLOBAL_CONFIG_FILE="${RES_DIR}/config/daylily_cli_global.yaml"
git_tag=$(python - "$GLOBAL_CONFIG_FILE" <<'PY'
import sys
import yaml

cfg = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
print((cfg.get("daylily", {}) or {}).get("git_ephemeral_cluster_repo_tag", ""))
PY
)

# Output results
echo $repo_name-$branch_name-$commit_hash-$git_tag
