#!/bin/bash
set -euo pipefail

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

git_tag=$(python -c 'from daylily_ec.versioning import get_version; print(get_version())')

# Output results
echo $repo_name-$branch_name-$commit_hash-$git_tag
