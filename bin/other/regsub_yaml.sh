#!/bin/bash

cluster_init_values=$1
cluster_cfg_yaml=$2

# Check if the files are provided as arguments
if [[ -z "$cluster_init_values" || -z "$cluster_cfg_yaml" ]]; then
    echo "Usage: $0 <cluster_init_values.txt> <cluster_cfg_yaml.yaml>"
    exit 1
fi

# Check if the files exist
if [[ ! -f "$cluster_init_values" ]]; then
    echo "Error: '$cluster_init_values' not found!"
    exit 1
fi

if [[ ! -f "$cluster_cfg_yaml" ]]; then
    echo "Error: '$cluster_cfg_yaml' not found!"
    exit 1
fi

# Build Perl substitution commands from the init values file
perl_cmd=""

if yq -e '.substitutions' "$cluster_init_values" >/dev/null 2>&1; then
    # New YAML-based template format
    while IFS=$'\t' read -r key value; do
        [[ -z "$key" ]] && continue

        escaped_key=$(printf '%s' "$key" | sed 's/[]\/$*.^|[]/\\&/g')
        escaped_value=$(printf '%s' "$value" | sed 's/[\/&]/\\&/g')
        perl_cmd="$perl_cmd;s/$escaped_key/$escaped_value/g"
    done < <(yq -r '.substitutions | to_entries[] | select(.value != null) | "\(.key)\t\(.value)"' "$cluster_init_values")
else
    # Legacy key=value format
    while IFS='=' read -r key value; do
        [[ -z "$key" || -z "$value" ]] && continue

        escaped_key=$(printf '%s' "$key" | sed 's/[]\/$*.^|[]/\\&/g')
        escaped_value=$(printf '%s' "$value" | sed 's/[\/&]/\\&/g')
        perl_cmd="$perl_cmd;s/$escaped_key/$escaped_value/g"
    done < "$cluster_init_values"
fi

# Run the substitutions in-place
perl -pi -e "$perl_cmd" "$cluster_cfg_yaml"

echo ""
echo "Substitutions completed in $cluster_cfg_yaml."
echo ""
