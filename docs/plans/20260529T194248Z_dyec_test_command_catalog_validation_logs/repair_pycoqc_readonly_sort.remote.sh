set -euo pipefail
python3 - <<'PYPYCOQC'
from pathlib import Path

roots = [Path("/fsx/resources/environments/conda/ubuntu")]
matches = []
for root in roots:
    if root.exists():
        matches.extend(root.glob("**/site-packages/pycoQC/pycoQC_plot.py"))

if not matches:
    print("[INFO] No installed pycoQC environment found for readonly-sort repair.")
    raise SystemExit(0)

old = "data = data.dropna().values\n        data.sort()"
new = "data = data.dropna().to_numpy(copy=True)\n        data.sort()"

for path in sorted(set(matches)):
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"[INFO] pycoQC readonly-sort repair already present: {path}")
        continue
    if old not in text:
        raise SystemExit(
            f"[ERROR] pycoQC readonly-sort repair target not found in {path}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[INFO] Patched pycoQC readonly-sort repair: {path}")
PYPYCOQC
