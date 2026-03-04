#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: proc_spot_price_logs.sh [-h|--help]

Processes /fsx/scratch/*price.log and prints summary spot pricing stats.

If sourced, exports:
  INSTANCE_TYPES
  INSTANCE_TYPES_LINE
  AVERAGE_SPOT_PRICE
  MEDIAN_SPOT_PRICE
  VCPU_COST_PER_MIN

If executed, prints the same values to stdout.
EOF
}

is_sourced=0
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  is_sourced=1
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  if [[ "$is_sourced" -eq 1 ]]; then
    return 0
  fi
  exit 0
fi

log_glob="/fsx/scratch/*price.log"
shopt -s nullglob
logs=( $log_glob )
shopt -u nullglob

if [[ ${#logs[@]} -eq 0 ]]; then
  echo "Error: no spot price logs found at ${log_glob}" >&2
  if [[ "$is_sourced" -eq 1 ]]; then
    return 1
  fi
  exit 1
fi

data="$(cat "${logs[@]}")"

instance_types="$(echo "$data" | awk -F ', ' '{print $3}' | sort | uniq)"
instance_types_line="$(echo "$instance_types" | tr '\n' ' ' | sed 's/ $//')"
instance_types_line="$(echo "$instance_types_line" | sed 's/Instance type://g')"

spot_prices="$(echo "$data" | grep -oP 'Spot price: \\K[0-9.]+')"
if [[ -z "$spot_prices" ]]; then
  echo "Error: no spot prices found in logs." >&2
  if [[ "$is_sourced" -eq 1 ]]; then
    return 1
  fi
  exit 1
fi

average_spot_price="$(echo "$spot_prices" | awk '{sum += $1; count++} END {print sum / count}')"
average_spot_price_fmt="$(printf "%.2f" "$average_spot_price")"

sorted_prices="$(echo "$spot_prices" | sort -n)"
price_count="$(echo "$sorted_prices" | wc -l | tr -d ' ')"
median_spot_price="$(echo "$sorted_prices" | awk -v n="$price_count" '
  BEGIN { if (n % 2 == 0) { mid1 = n / 2; mid2 = mid1 + 1 } else { mid1 = (n + 1) / 2; mid2 = mid1 } }
  { if (NR == mid1) val1 = $1; if (NR == mid2) val2 = $1 }
  END { print (val1 + val2) / 2 }')"
median_spot_price_fmt="$(printf "%.2f" "$median_spot_price")"

vcpu_cost_per_min="$(echo "$average_spot_price" | awk '{print ($1 / 192) / 60}')"

if [[ "$is_sourced" -eq 1 ]]; then
  export INSTANCE_TYPES="$instance_types"
  export INSTANCE_TYPES_LINE="$instance_types_line"
  export AVERAGE_SPOT_PRICE="$average_spot_price_fmt"
  export MEDIAN_SPOT_PRICE="$median_spot_price_fmt"
  export VCPU_COST_PER_MIN="$vcpu_cost_per_min"
else
  echo "Unique Instance Types:"
  echo "$instance_types_line"
  echo "$instance_types"
  echo
  echo "Average Spot Price (USD/hour): $average_spot_price_fmt"
  echo "Median Spot Price (USD/hour): $median_spot_price_fmt"
  echo "vCPU Cost (USD/min): $vcpu_cost_per_min"
fi

