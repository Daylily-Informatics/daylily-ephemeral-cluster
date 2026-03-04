#!/bin/bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: detect_azs.sh [-h|--help]

Writes a TSV of all regions and available availability zones to ./azs.tsv.

Requires:
  aws (configured credentials)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "Error: required command 'aws' not found in PATH" >&2
  exit 1
fi

echo -e "Region\tAvailabilityZone" > azs.tsv

for region in $(aws ec2 describe-regions --query "Regions[].RegionName" --output text); do
  aws ec2 describe-availability-zones --region "$region" --query "AvailabilityZones[?State=='available'].ZoneName" --output text | while read -r az; do
    echo -e "$region\t$az" >> azs.tsv
  done
done
