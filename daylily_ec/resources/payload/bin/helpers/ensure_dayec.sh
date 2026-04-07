#!/usr/bin/env bash
# DAY-EC Conda Environment Checker
#
# Source this file to get the ensure_dayec function, or run directly to check.
#
# Usage in scripts:
#   source "$(dirname "${BASH_SOURCE[0]}")/helpers/ensure_dayec.sh"
#   ensure_dayec
#
# Or from bin/ directory:
#   source ./helpers/ensure_dayec.sh
#   ensure_dayec

ensure_dayec() {
    local env_name="DAY-EC"
    local quiet="${1:-false}"
    local repo_root

    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

    # Check if already active
    if [[ "${CONDA_DEFAULT_ENV:-}" == "$env_name" ]]; then
        if [[ "$quiet" != "true" ]]; then
            echo "✓ $env_name conda environment is active." >&2
        fi
        return 0
    fi

    if [[ -f "$repo_root/activate" ]]; then
        # shellcheck source=/dev/null
        source "$repo_root/activate"
        if [[ "${CONDA_DEFAULT_ENV:-}" == "$env_name" ]]; then
            if [[ "$quiet" != "true" ]]; then
                echo "✓ $env_name conda environment is active." >&2
            fi
            return 0
        fi
    fi

    echo "⚠ $env_name is not active. Attempting to bootstrap via ./activate..." >&2
    echo "" >&2
    echo "============================================================" >&2
    echo "ERROR: $env_name is still not active." >&2
    echo "============================================================" >&2
    echo "" >&2
    echo "Create or activate it with:" >&2
    echo "" >&2
    echo "    source \"$repo_root/activate\"" >&2
    echo "    eval \"\$(daylily-ec headnode init --emit-shell --non-interactive)\"" >&2
    echo "" >&2
    echo "And re-run this script." >&2
    echo "" >&2
    return 1
}

# If run directly (not sourced), execute the check
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    ensure_dayec "$@"
    exit $?
fi
