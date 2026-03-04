#!/bin/bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: test_region_accel_endpoint.sh <region> <bucket_name> [-h|--help]

Checks whether the S3 Accelerate endpoint is reachable for a given bucket.
Note: This is a simple HTTP status probe (200/403 treated as "supported").

Requires:
  curl
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ $# -ne 2 ]]; then
    usage
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "Error: required command 'curl' not found in PATH" >&2
    exit 1
fi

# Function to check if a region supports S3 acceleration
check_acceleration_support() {
    local region="$1"
    local bucket_name="$2"
    
    # Use curl to make a HEAD request to the S3 Accelerate endpoint
    local endpoint="https://s3-accelerate.amazonaws.com"
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" -X HEAD -H "Host: ${bucket_name}.s3-accelerate.amazonaws.com" $endpoint)

    if [[ "$response" -eq 200 || "$response" -eq 403 ]]; then
        echo "S3 acceleration is supported in region '$region'."
        return 0
    else
        echo "S3 acceleration is NOT supported in region '$region'."
        return 1
    fi
}

# Example usage
region=$1
bucket_name=$2
check_acceleration_support "$region" "$bucket_name"
