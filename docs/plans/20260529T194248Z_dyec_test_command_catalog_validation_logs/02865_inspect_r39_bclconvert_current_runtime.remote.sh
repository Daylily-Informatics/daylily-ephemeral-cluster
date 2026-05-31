set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis
run=20260514_LH01106_0009_B23TVLGLT4
log="$repo/results/runs/$run/bclconvert/logs/run_bclconvert.log"
echo "=== now ==="; date -u +%Y-%m-%dT%H:%M:%SZ
echo "=== status ==="; cat /home/ubuntu/daylily-runs/ccv20260529r39_illumina_bclconvert/status.json || true
echo "=== squeue ==="; squeue -j 3310 -o '%i|%P|%C|%t|%M|%D|%R|%j'
echo "=== repo config bclconvert ==="; python - <<'PY2'
from pathlib import Path
p=Path('/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis/config/day_profiles/slurm/rule_config.yaml')
text=p.read_text()
lines=text.splitlines()
for i,line in enumerate(lines):
    if line.startswith('bclconvert:'):
        for j in range(i, min(len(lines), i+80)):
            if j>i and lines[j] and not lines[j].startswith(' ') and not lines[j].startswith('	'):
                break
            print(f'{j+1}:{lines[j]}')
        break
PY2
echo "=== run log exists ==="; ls -lh "$log" || true
echo "=== bcl command/progress markers ==="; grep -nE '^(run_bclconvert started|staging_mode|scratch_|mounted_stage_|bcl_num_|bcl-convert command|INFO|WARNING|ERROR|Moving|Removing|run_bclconvert finished|BCLConvert|Processing|Writing|Total|Demultiplex)' "$log" | tail -120 || true
echo "=== run log tail ==="; tail -n 160 "$log" || true
echo "=== scratch dirs ==="; find /dev/shm -maxdepth 3 -mindepth 1 -name '*3310*' -o -path '/dev/shm/*/run' 2>/dev/null | head -80 || true
echo "=== result sizes ==="; du -sh "$repo/results/runs/$run/bclconvert" 2>/dev/null || true; find "$repo/results/runs/$run/bclconvert" -maxdepth 3 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p
' 2>/dev/null | sort | tail -60 || true
