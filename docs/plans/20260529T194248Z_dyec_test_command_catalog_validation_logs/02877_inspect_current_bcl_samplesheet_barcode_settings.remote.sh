
set -euo pipefail
run=/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4
dry=/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert_dryrun/daylily-omics-analysis/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/normalized.SampleSheet.csv
live_deleted=/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/normalized.SampleSheet.csv
printf 'RUN_DIR=%s\n' "$run"
printf 'RUN_DIR_EXISTS=%s\n' "$(test -d "$run" && echo yes || echo no)"
printf 'DRY_NORMALIZED_EXISTS=%s\n' "$(test -f "$dry" && echo yes || echo no)"
printf 'LIVE_NORMALIZED_EXISTS_AFTER_DELETE=%s\n' "$(test -f "$live_deleted" && echo yes || echo no)"
printf '\nCANDIDATE_SAMPLE_SHEETS\n'
find "$run" -maxdepth 3 -type f \( -iname '*samplesheet*.csv' -o -iname '*sample_sheet*.csv' \) -print | sort | sed -n '1,20p'
python3 - <<'PY2'
from pathlib import Path
import csv, hashlib
candidates = [
    Path('/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert_dryrun/daylily-omics-analysis/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/normalized.SampleSheet.csv'),
    Path('/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/SampleSheet.csv'),
]
for path in candidates:
    print(f"\nSAMPLESHEET={path}")
    if not path.exists():
        print('exists=no')
        continue
    data = path.read_bytes()
    print('exists=yes')
    print('sha256=' + hashlib.sha256(data).hexdigest())
    text = data.decode('utf-8-sig', errors='replace').splitlines()
    section = None
    settings = []
    data_header = None
    data_rows = 0
    data_barcode_columns = []
    for raw in text:
        line = raw.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line.strip('[]')
            continue
        if section in {'Settings','settings','BCLConvert_Settings'}:
            row = next(csv.reader([raw]))
            key = row[0].strip() if row else ''
            if key:
                settings.append(row)
        elif section in {'Data','data','BCLConvert_Data'}:
            row = next(csv.reader([raw]))
            if data_header is None:
                data_header = row
                data_barcode_columns = [c for c in row if 'BarcodeMismatch' in c or 'BarcodeMismatches' in c]
            else:
                data_rows += 1
    wanted = { 'BarcodeMismatchesIndex1','BarcodeMismatchesIndex2','NoLaneSplitting','OverrideCycles','AdapterRead1','AdapterRead2','AdapterBehavior','AdapterStringency','MinimumTrimmedReadLength','MaskShortReads','CreateFastqForIndexReads','TrimUMI' }
    print('settings_section_rows:')
    for row in settings:
        key = row[0].strip()
        if key in wanted or 'BarcodeMismatch' in key or 'BarcodeMismatches' in key:
            print('  ' + ','.join(row))
    if not settings:
        print('  <none>')
    print('data_header=' + (','.join(data_header) if data_header else '<none>'))
    print('data_rows=' + str(data_rows))
    print('data_barcode_mismatch_columns=' + (','.join(data_barcode_columns) if data_barcode_columns else '<none>'))
PY2
