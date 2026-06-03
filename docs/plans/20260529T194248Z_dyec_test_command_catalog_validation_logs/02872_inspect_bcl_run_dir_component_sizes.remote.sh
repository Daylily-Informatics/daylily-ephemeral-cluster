set -euo pipefail
run=/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4
repo=/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis
scratch=$repo/.bclconvert_scratch/3310.25321
out=$scratch/fastqs
echo "=== timestamp ==="; date -u +%Y-%m-%dT%H:%M:%SZ
echo "=== top-level tree ==="; find "$run" -maxdepth 2 -mindepth 1 -printf '%y %p\n' | sort | sed -n '1,160p'
echo "=== component byte sizes ==="
size(){ label=$1; path=$2; if [[ -e "$path" ]]; then bytes=$(du -sB1 "$path" | awk '{print $1}'); human=$(du -sh "$path" | awk '{print $1}'); files=$(find "$path" -type f 2>/dev/null | wc -l | tr -d ' '); printf '%s\t%s\t%s\t%s\n' "$label" "$bytes" "$human" "$files"; else printf '%s\t0\tmissing\t0\n' "$label"; fi; }
size total_run "$run"
size basecalls "$run/Data/Intensities/BaseCalls"
size intensities_top "$run/Data/Intensities"
size data "$run/Data"
size interop "$run/InterOp"
size analysis "$run/Analysis"
size recipes "$run/Recipe"
size logs "$run/Logs"
size thumbnails "$run/Thumbnail_Images"
size root_files "$run/.root_files_only"
echo "=== root and intensity top file bytes ==="
root_file_bytes=$(find "$run" -maxdepth 1 -type f -printf '%s\n' | awk '{s+=$1} END {print s+0}')
intensities_file_bytes=$(find "$run/Data/Intensities" -maxdepth 1 -type f -printf '%s\n' 2>/dev/null | awk '{s+=$1} END {print s+0}')
basecalls_bytes=$(du -sB1 "$run/Data/Intensities/BaseCalls" | awk '{print $1}')
interop_bytes=$(du -sB1 "$run/InterOp" 2>/dev/null | awk '{print $1+0}')
total_bytes=$(du -sB1 "$run" | awk '{print $1}')
staged_bcl_bytes=$((root_file_bytes + intensities_file_bytes + basecalls_bytes))
runqc_core_bytes=$((root_file_bytes + interop_bytes))
printf 'root_file_bytes\t%s\n' "$root_file_bytes"
printf 'intensities_file_bytes\t%s\n' "$intensities_file_bytes"
printf 'basecalls_bytes\t%s\n' "$basecalls_bytes"
printf 'interop_bytes\t%s\n' "$interop_bytes"
printf 'total_bytes\t%s\n' "$total_bytes"
printf 'current_bcl_staged_bytes\t%s\n' "$staged_bcl_bytes"
printf 'runqc_core_bytes_root_plus_interop\t%s\n' "$runqc_core_bytes"
python3 - <<PY2
from decimal import Decimal
vals = dict(total=$total_bytes, basecalls=$basecalls_bytes, bcl=$staged_bcl_bytes, runqc=$runqc_core_bytes, interop=$interop_bytes)
for k,v in vals.items():
    print(f"pct_{k}_of_total\t{(Decimal(v)*100/Decimal(vals['total'])) if vals['total'] else 0:.4f}")
PY2
echo "=== current scratch output ==="
if [[ -d "$out" ]]; then du -sB1 "$out"; du -sh "$out"; find "$out" -type f | wc -l; fi
echo "=== current fsx ==="; df -h /fsx; if command -v lfs >/dev/null 2>&1; then lfs df -h /fsx | tail -n 12; fi
