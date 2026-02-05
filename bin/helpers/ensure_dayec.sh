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

    # Check if already active
    if [[ "${CONDA_DEFAULT_ENV:-}" == "$env_name" ]]; then
        if [[ "$quiet" != "true" ]]; then
            echo "✓ $env_name conda environment is active." >&2
        fi
        return 0
    fi

    # DAY-EC is not active - try to activate it
    echo "⚠ $env_name is not active. Attempting to activate..." >&2

    # Source conda if not already available
    if ! command -v conda &>/dev/null; then
        # Try common conda locations
        for conda_path in \
            "${HOME}/miniconda3/etc/profile.d/conda.sh" \
            "${HOME}/anaconda3/etc/profile.d/conda.sh" \
            "/opt/conda/etc/profile.d/conda.sh" \
            "/usr/local/miniconda3/etc/profile.d/conda.sh"; do
            if [[ -f "$conda_path" ]]; then
                # shellcheck source=/dev/null
                source "$conda_path"
                break
            fi
        done
    fi

    # Still no conda?
    if ! command -v conda &>/dev/null; then
        echo "" >&2
        echo "============================================================" >&2
        echo "ERROR: Conda is not available in this shell." >&2
        echo "============================================================" >&2
        echo "" >&2
        echo "Install Miniconda with:" >&2
        echo "" >&2
        echo "    ./bin/install_miniconda" >&2
        echo "" >&2
        return 1
    fi

    # Check if DAY-EC environment exists
    if conda env list 2>/dev/null | grep -q "^${env_name} "; then
        # Environment exists, try to activate
        # shellcheck source=/dev/null
        source "$(conda info --base)/etc/profile.d/conda.sh"
        conda activate "$env_name"

        # Verify activation succeeded
        if [[ "${CONDA_DEFAULT_ENV:-}" == "$env_name" ]]; then
            echo "✓ Successfully activated $env_name." >&2
            return 0
        else
            echo "" >&2
            echo "============================================================" >&2
            echo "ERROR: Failed to activate $env_name environment." >&2
            echo "============================================================" >&2
            echo "" >&2
            echo "Try manually activating:" >&2
            echo "" >&2
            echo "    conda activate $env_name" >&2
            echo "" >&2
            return 1
        fi
    else
        # Environment does not exist
        echo "" >&2
        echo "============================================================" >&2
        echo "ERROR: The $env_name conda environment does not exist." >&2
        echo "============================================================" >&2
        echo "" >&2
        echo "Create it by running:" >&2
        echo "" >&2
        echo "    ./bin/init_dayec" >&2
        echo "" >&2
        echo "Then activate with:" >&2
        echo "" >&2
        echo "    conda activate $env_name" >&2
        echo "" >&2
        echo "And re-run this script." >&2
        echo "" >&2
        return 1
    fi
}

# If run directly (not sourced), execute the check
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    ensure_dayec "$@"
    exit $?
fi

