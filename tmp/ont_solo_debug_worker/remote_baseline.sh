set -euo pipefail
echo "== whoami =="
id -un
echo "== date =="
date -u +%Y-%m-%dT%H:%M:%SZ
echo "== matching run dirs =="
find /home/ubuntu/daylily-runs -maxdepth 1 -type d -name '*ont*preserve*' -o -name '*ont*191*' 2>/dev/null | sort || true
echo "== matching fsx analysis dirs =="
find /fsx/analysis_results/johnm -maxdepth 1 -type d -name '*ont*preserve*' -o -name '*ont*191*' 2>/dev/null | sort || true
echo "== current jobs =="
squeue -o '%.18i %.9P %.40j %.12u %.10T %.10M %.6D %.25R %.8C %.12m' || true
echo "== fsx space =="
df -h /fsx
echo "== stage manifests =="
ls -l /fsx/data/staged_sample_data/remote_stage_20260522T203135Z
echo "== stage units ont fields =="
python3 -c "import csv; p='/fsx/data/staged_sample_data/remote_stage_20260522T203135Z/20260522T203135Z_units.tsv'; rows=list(csv.DictReader(open(p), delimiter='\t')); print(len(rows)); print(rows[0].get('ONT_CRAM')); print(rows[0].get('ONT_CRAM_ALIGNER'), rows[0].get('ONT_CRAM_SNV_CALLER'))"
