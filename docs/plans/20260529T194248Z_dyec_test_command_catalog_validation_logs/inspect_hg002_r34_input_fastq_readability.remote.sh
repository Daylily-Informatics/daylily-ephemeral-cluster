set -euo pipefail

r1=/fsx/staging/staged_external_sequencing_data/remote_stage_20260529T202437Z_6ac53e3a/JEMILMN0P1_HG002-NOVASEQ-PF-gdna-0p1x_D0_0/HG002_0.1x_R1.fastq.gz
r2=/fsx/staging/staged_external_sequencing_data/remote_stage_20260529T202437Z_6ac53e3a/JEMILMN0P1_HG002-NOVASEQ-PF-gdna-0p1x_D0_0/HG002_0.1x_R2.fastq.gz

for fq in "${r1}" "${r2}"; do
  echo "=== ${fq} ==="
  ls -lh "${fq}" || true
  stat "${fq}" || true
  echo "--- gzip test ---"
  gzip -t "${fq}" && echo "gzip_ok" || echo "gzip_failed:$?"
  echo "--- first bytes ---"
  od -An -tx1 -N32 "${fq}" || true
  echo "--- first fastq lines ---"
  set +e
  gzip -dc -- "${fq}" | head -n 8
  rc=${PIPESTATUS[0]}
  set -e
  echo "gzip_dc_rc=${rc}"
done
