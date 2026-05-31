
set -euo pipefail
sample=/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/SampleSheet.csv
python3 - <<'PY2'
from pathlib import Path
import csv
sample = Path('/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/SampleSheet.csv')
print(f'SAMPLESHEET={sample}')
section = None
header = None
rows = []
for raw in sample.read_text(encoding='utf-8-sig').splitlines():
    line = raw.strip()
    if not line:
        continue
    if line.startswith('[') and line.endswith(']'):
        section = line.strip('[]')
        header = None
        continue
    if section not in {'Data','data','BCLConvert_Data'}:
        continue
    row = next(csv.reader([raw]))
    if header is None:
        header = [col.strip() for col in row]
        continue
    values = [cell.strip() for cell in row] + [''] * (len(header) - len(row))
    record = dict(zip(header, values))
    sample_id = record.get('Sample_ID') or record.get('SampleID') or record.get('Sample_Name') or ''
    idx1 = record.get('Index') or record.get('index') or record.get('index1') or ''
    idx2 = record.get('Index2') or record.get('index2') or ''
    lane = record.get('Lane') or record.get('lane') or '*'
    rows.append((lane, sample_id, idx1, idx2))
print('count\tlane\tsample_id\tindex1_i7\tindex2_i5')
for n, (lane, sample_id, idx1, idx2) in enumerate(rows, start=1):
    print(f'{n}\t{lane}\t{sample_id}\t{idx1}\t{idx2}')
PY2
