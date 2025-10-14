#!/bin/bash

# Check if we're in a Git repository
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    echo "Not inside a Git repository."
    exit 1
fi

# Get the repository name (extract from remote URL)
repo_name=$(basename -s .git "$(git config --get remote.origin.url 2>/dev/null)")

# Get the current branch name (if on a branch)
branch_name=$(git symbolic-ref --short HEAD 2>/dev/null || echo "N/A")

# Get the latest commit hash
commit_hash=$(git rev-parse HEAD 2>/dev/null)

GLOBAL_CONFIG_FILE=config/daylily_cli_global.yaml
git_tag=$(yq -r '.daylily.git_ephemeral_cluster_repo_tag' "$GLOBAL_CONFIG_FILE")

# Output results
echo $repo_name-$branch_name-$commit_hash-$git_tag
