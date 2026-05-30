set -euo pipefail
base=/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG003
find "$base" -maxdepth 3 -type f | sed 's#^#FILE # ' | head -n 80
find "$base" -maxdepth 3 -type d | sed 's#^#DIR # ' | head -n 80
