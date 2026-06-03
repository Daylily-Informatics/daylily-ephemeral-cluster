
set -euo pipefail
run_dir=/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4
venv=/tmp/dyec-illuminate-spike-20260530
rm -rf "$venv"
python3 -m venv "$venv"
. "$venv/bin/activate"
python -m pip install --upgrade pip >/tmp/dyec-illuminate-pip-upgrade.log 2>&1 || true
python -m pip install illuminate >/tmp/dyec-illuminate-pip-install.log 2>&1
python - <<'PY2'
from pathlib import Path
import traceback
from illuminate import InteropDataset
run_dir = Path('/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4')
print(f'RUN_DIR={run_dir}')
print('INTEROP_FILES')
for path in sorted((run_dir / 'InterOp').glob('*')):
    print(f'{path.name}\t{path.stat().st_size}')
print('ILLUMINATE_PARSE')
ds = InteropDataset(str(run_dir))
for name in [
    'TileMetrics',
    'QualityMetrics',
    'IndexMetrics',
    'ControlMetrics',
    'CorrectedIntensityMetrics',
    'ExtractionMetrics',
    'ErrorMetrics',
]:
    try:
        parser = getattr(ds, name)
        obj = parser()
        df = getattr(obj, 'df', None)
        shape = getattr(df, 'shape', None)
        data = getattr(obj, 'data', None)
        keys = sorted(data.keys()) if isinstance(data, dict) else []
        print(f'{name}\tOK\tshape={shape}\tkeys={keys[:12]}')
    except Exception as exc:
        print(f'{name}\tFAIL\t{type(exc).__name__}: {exc}')
PY2
