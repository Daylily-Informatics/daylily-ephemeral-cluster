set -euo pipefail
echo '=== local VEP paths ==='
for p in /fsx/references/runtime_assets/tool_specific_resources/vep /fsx/data/runtime_assets/tool_specific_resources/vep /fsx/references/runtime_assets/tool_specific_resources; do
  echo "--- $p"
  if [[ -e "$p" ]]; then
    ls -la "$p" | head -n 80
    find "$p" -maxdepth 5 -type d \( -iname '*vep*' -o -iname '*GRCh38*' -o -iname 'homo_sapiens' \) -print | sort | head -n 200
  else
    echo 'missing'
  fi
done
echo '=== S3 VEP prefixes ==='
for uri in s3://lsmc-dayoa-references-usw2/runtime_assets/tool_specific_resources/vep/homo_sapiens/ s3://daylily-dayoa-references-usw2/runtime_assets/tool_specific_resources/vep/homo_sapiens/ s3://lsmc-dayoa-control-data-usw2/runtime_assets/tool_specific_resources/vep/homo_sapiens/ s3://lsmc-dayoa-control-data-usw2/tool_specific_resources/vep/homo_sapiens/; do
  echo "--- $uri"
  aws s3 ls "$uri" --recursive | head -n 80 || true
done