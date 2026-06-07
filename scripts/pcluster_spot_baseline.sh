#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/pcluster_spot_baseline.sh [--profile PROFILE] [--region REGION] [--az AZ] [--config PATH]

Read-only Spot baseline helper for the DAY-EC v8 ParallelCluster template.
Writes:
  docs/spot-baselines/pcluster-spot-baseline-<az>.csv
  docs/spot-baselines/pcluster-spot-baseline-<az>.md
USAGE
}

profile=""
region="us-west-2"
az="us-west-2d"
config="config/day_cluster/prod_cluster_v8.yaml"

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --profile) profile="${2:?--profile requires a value}"; shift 2 ;;
    --region) region="${2:?--region requires a value}"; shift 2 ;;
    --az) az="${2:?--az requires a value}"; shift 2 ;;
    --config) config="${2:?--config requires a value}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 64 ;;
  esac
done

if [[ ! -f "$config" ]]; then
  echo "Cluster config not found: $config" >&2
  exit 66
fi
command -v aws >/dev/null || { echo "Missing required command: aws" >&2; exit 69; }
command -v python >/dev/null || { echo "Missing required command: python" >&2; exit 69; }

aws_args=(aws)
if [[ -n "$profile" ]]; then
  aws_args+=(--profile "$profile")
fi

out_dir="docs/spot-baselines"
mkdir -p "$out_dir"
csv="$out_dir/pcluster-spot-baseline-${az}.csv"
md="$out_dir/pcluster-spot-baseline-${az}.md"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

python - "$config" > "$tmp_dir/instances.tsv" <<'PY'
from pathlib import Path
import sys
import yaml

path = Path(sys.argv[1])
data = yaml.safe_load(path.read_text(encoding="utf-8"))
for queue in data["Scheduling"]["SlurmQueues"]:
    qname = queue["Name"]
    for resource in queue["ComputeResources"]:
        rname = resource["Name"]
        for instance in resource.get("Instances", []):
            print("\t".join([qname, rname, instance["InstanceType"]]))
PY

instance_types=()
while IFS= read -r instance_type; do
  instance_types+=("$instance_type")
done < <(cut -f3 "$tmp_dir/instances.tsv" | sort -u)
"${aws_args[@]}" ec2 describe-instance-types \
  --region "$region" \
  --instance-types "${instance_types[@]}" \
  --output json > "$tmp_dir/specs.json"

{
  echo "queue,compute_resource,instance_type,az,spot_price_per_hour,spot_timestamp,vcpu,memory_gib,local_scratch_summary,local_scratch_total_tb,network_performance,ebs_optimized_bandwidth"
  while IFS=$'\t' read -r queue resource instance_type; do
    "${aws_args[@]}" ec2 describe-spot-price-history \
      --region "$region" \
      --availability-zone "$az" \
      --instance-types "$instance_type" \
      --product-descriptions "Linux/UNIX" \
      --max-results 1 \
      --output json > "$tmp_dir/spot.json"
    python - "$tmp_dir/specs.json" "$tmp_dir/spot.json" "$queue" "$resource" "$instance_type" "$az" <<'PY'
import csv
import json
import sys

specs = json.load(open(sys.argv[1], encoding="utf-8"))["InstanceTypes"]
spot = json.load(open(sys.argv[2], encoding="utf-8")).get("SpotPriceHistory", [])
queue, resource, instance_type, az = sys.argv[3:7]
spec = next(item for item in specs if item["InstanceType"] == instance_type)
price = spot[0]["SpotPrice"] if spot else ""
timestamp = spot[0]["Timestamp"] if spot else ""
disks = spec.get("InstanceStorageInfo", {}).get("Disks", [])
scratch_gb = sum(d.get("SizeInGB", 0) * d.get("Count", 0) for d in disks)
scratch_summary = "+".join(f"{d.get('Count', 0)}x{d.get('SizeInGB', 0)}GB" for d in disks) or "none"
writer = csv.writer(sys.stdout)
writer.writerow([
    queue,
    resource,
    instance_type,
    az,
    price,
    timestamp,
    spec["VCpuInfo"]["DefaultVCpus"],
    round(spec["MemoryInfo"]["SizeInMiB"] / 1024, 3),
    scratch_summary,
    round(scratch_gb / 1024, 3),
    spec.get("NetworkInfo", {}).get("NetworkPerformance", ""),
    spec.get("EbsInfo", {}).get("EbsOptimizedInfo", {}).get("BaselineBandwidthInMbps", ""),
])
PY
  done < "$tmp_dir/instances.tsv"
} > "$csv"

python - "$csv" "$md" "$config" "$region" "$az" <<'PY'
import csv
import sys
from pathlib import Path

csv_path = Path(sys.argv[1])
md_path = Path(sys.argv[2])
config = sys.argv[3]
region = sys.argv[4]
az = sys.argv[5]
rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
headers = rows[0].keys() if rows else []
with md_path.open("w", encoding="utf-8") as out:
    out.write(f"# ParallelCluster Spot Baseline: {az}\n\n")
    out.write(f"- Region: `{region}`\n")
    out.write(f"- Availability Zone: `{az}`\n")
    out.write(f"- Cluster config: `{config}`\n")
    out.write(f"- CSV: `{csv_path}`\n\n")
    out.write("| " + " | ".join(headers) + " |\n")
    out.write("| " + " | ".join("---" for _ in headers) + " |\n")
    for row in rows:
        out.write("| " + " | ".join(str(row[h]) for h in headers) + " |\n")
PY

echo "Wrote $csv"
echo "Wrote $md"
