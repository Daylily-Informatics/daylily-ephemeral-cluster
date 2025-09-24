#!/bin/bash

# Set required versions
required_versions=(
    "python3:3.11.0"
    "git:2.34.0"
    "wget:1.21.0"
)

# Check if pass_on_warn is set
pass_on_warn=${pass_on_warn:-0}

# Function to compare versions
check_version() {
    local required=$1
    local current=$2

    if [[ "$(printf '%s\n' "$required" "$current" | sort -V | head -n1)" != "$required" ]]; then
        return 1 # Current version is less than required
    fi
    return 0 # Current version meets or exceeds required
}

# Function to check each tool
check_tool() {
    local tool=$1
    local required_version=$2
    local version_command=$3

    # Get current version
    current_version=$(eval "$version_command" 2>/dev/null)
    if [[ -z "$current_version" ]]; then
        echo "Error: $tool is not installed."
        [[ "$pass_on_warn" -eq 1 ]] && return 0 || exit 1
    fi

    # Check version
    if ! check_version "$required_version" "$current_version"; then
        echo "Error: $tool version $current_version does not meet the required version $required_version."
        [[ "$pass_on_warn" -eq 1 ]] && return 0 || exit 1
    fi

    # Print success message if version is sufficient
    echo "$tool version $current_version meets the required version $required_version or higher."
}

# Loop through required tools and check
for entry in "${required_versions[@]}"; do
    tool=${entry%%:*}
    required_version=${entry#*:}

    case $tool in
        python3)
            check_tool "python3" "$required_version" "python3 --version | awk '{print \$2}'"
            ;;
        git)
            check_tool "git" "$required_version" "git --version | awk '{print \$3}'"
            ;;
        wget)
            check_tool "wget" "$required_version" "wget --version | head -n1 | awk '{print \$3}'"
            ;;
        *)
            echo "Unknown tool $tool."
            [[ "$pass_on_warn" -eq 1 ]] && continue || exit 1
            ;;
    esac
done

echo "All tools meet the required versions."
