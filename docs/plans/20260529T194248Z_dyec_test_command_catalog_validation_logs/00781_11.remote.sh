set -euo pipefail
plot=$(find /fsx/resources/environments/conda/ubuntu -path '*/site-packages/pycoQC/pycoQC_plot.py' | head -n 1)
echo "$plot"
sed -n '1,80p' "$plot"
sed -n '1450,1485p' "$plot"
