set -euo pipefail
session=ccv20260529r19_illumina_bclconvert
echo "=== slurm before ==="
squeue -n run_bclconvert-run_bclconvert -o '%i|%P|%C|%t|%M|%D|%R|%j' || true
scancel -n run_bclconvert-run_bclconvert || true
echo "=== tmux before ==="
tmux list-sessions 2>/dev/null | grep "$session" || true
tmux kill-session -t "$session" 2>/dev/null || true
status_file=/home/ubuntu/daylily-runs/$session/status.json
python3 - "$status_file" <<'PYSTATUS'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
payload["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
payload["exit_code"] = 130
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(path)
PYSTATUS
echo "=== slurm after ==="
squeue -n run_bclconvert-run_bclconvert -o '%i|%P|%C|%t|%M|%D|%R|%j' || true
echo "=== scratch candidates ==="
find /fsx/scratch/dayoa_bclconvert -mindepth 1 -maxdepth 1 -type d -printf '%p\n' 2>/dev/null || true
