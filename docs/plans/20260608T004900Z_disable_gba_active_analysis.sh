#!/usr/bin/env bash
set -euo pipefail

analysis="/fsx/analysis_results/hyb-only/hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z/daylily-omics-analysis"
cd "$analysis"

stamp="20260608T004900Z"
files=(
  "config/day_profiles/slurm/templates/rule_config.yaml"
  "config/day_profiles/slurm/rule_config.yaml"
)

for file in "${files[@]}"; do
  cp "$file" "${file}.pre_no_gba_${stamp}"
  perl -0pi -e 's/segdup_genes: "CFH,CYP11B1,CYP2D6,GBA,NCF1,PMS2,SMN1,STRC,HBA"/segdup_genes: "CFH,CYP11B1,CYP2D6,NCF1,PMS2,SMN1,STRC,HBA"/g; s/segdup_genes: CFH,CYP11B1,CYP2D6,GBA,NCF1,PMS2,SMN1,STRC,HBA/segdup_genes: CFH,CYP11B1,CYP2D6,NCF1,PMS2,SMN1,STRC,HBA/g' "$file"
done

echo "UPDATED"
grep -n "segdup_genes" "${files[@]}"

if grep -R "segdup_genes:.*GBA" "${files[@]}"; then
  echo "STILL_HAS_GBA"
  exit 1
fi
