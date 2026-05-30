set -euo pipefail
echo "before:"
du -sh /fsx/scratch/dayoa_bclconvert 2>/dev/null || true
find /fsx/scratch/dayoa_bclconvert -maxdepth 1 -mindepth 1 -type d -name '2654.*' -print -exec du -sh {} \; 2>/dev/null || true
find /fsx/scratch/dayoa_bclconvert -maxdepth 1 -mindepth 1 -type d -name '2654.*' -exec rm -rf {} +
echo "after:"
du -sh /fsx/scratch/dayoa_bclconvert 2>/dev/null || true
find /fsx/scratch/dayoa_bclconvert -maxdepth 1 -mindepth 1 -type d -name '2654.*' -print 2>/dev/null || true
