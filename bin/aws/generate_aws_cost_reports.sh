# Set a 7‑day window; tweak as needed
START=$(date -u -d '7 days ago' +%Y-%m-%dT00:00:00Z); END=$(date -u +%Y-%m-%dT00:00:00Z)

# 1) Hourly cost by cluster/instance/market (Spot/On-Demand)
aws ce get-cost-and-usage \
  --time-period Start=${START%T*},End=${END%T*} \
  --granularity HOURLY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=INSTANCE_TYPE \
             Type=TAG,Key=parallelcluster:cluster-name \
             Type=DIMENSION,Key=PURCHASE_TYPE \
  --query 'ResultsByTime[].Groups[].{ts:Keys,amount:Metrics.UnblendedCost.Amount}' \
  --output json > ce_hourly.json

# 2) Spot interruptions (events) via EC2 Spot Instance Interruption Warnings
aws cloudwatch get-metric-statistics \
  --namespace "AWS/EC2" --metric-name "SpotInterruptionWarning" \
  --statistics Sum --period 3600 --start-time "$START" --end-time "$END" \
  --dimensions Name=State,Value=terminated \
  --output json > spot_interruptions.json

# 3) FSx for Lustre capacity & throughput
FSX_IDS=$(aws fsx describe-file-systems --query 'FileSystems[?FileSystemType==`LUSTRE`].FileSystemId' --output text)
for id in $FSX_IDS; do
  for metric in DataReadBytes DataWriteBytes MetadataOps FreeDataStorageCapacity; do
    aws cloudwatch get-metric-statistics \
      --namespace "AWS/FSx" --metric-name "$metric" \
      --statistics Sum Average Maximum \
      --period 3600 --start-time "$START" --end-time "$END" \
      --dimensions Name=FileSystemId,Value="$id" \
      --output json > "fsx_${id}_${metric}.json"
  done
done

# 4) Node idle detector (no Slurm load, but instances running)
aws cloudwatch get-metric-statistics \
  --namespace "AWS/EC2" --metric-name CPUUtilization \
  --statistics Average --period 300 \
  --start-time "$START" --end-time "$END" \
  --output json > ec2_cpu_5min.json

# 5) Cheap egress sniff (S3/EC2 data out)
aws cloudwatch get-metric-statistics \
  --namespace "AWS/S3" --metric-name "BytesDownloaded" \
  --statistics Sum --period 3600 --start-time "$START" --end-time "$END" \
  --output json > s3_bytes_downloaded.json
