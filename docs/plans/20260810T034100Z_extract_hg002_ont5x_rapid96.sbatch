#!/usr/bin/env bash
#SBATCH --job-name=hg002_ont5x_rapid96
#SBATCH --partition=i96nvme
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=96
#SBATCH --time=00:20:00

set -Eeuo pipefail
umask 022

: "${OUTPUT_ROOT:?Set OUTPUT_ROOT to the locked analysis-root staging directory}"
: "${SEQKIT_PATH:?Set SEQKIT_PATH to the exact SeqKit 2.13.0 binary}"
: "${RAPIDGZIP_PATH:?Set RAPIDGZIP_PATH to the exact rapidgzip 0.16.0 binary}"
: "${RAPIDGZIP_WHEEL:?Set RAPIDGZIP_WHEEL to the retained rapidgzip wheel}"

SOURCE_BUCKET=lsmc-dayoa-references-usw2
SOURCE_KEY=genomic_data/organism_reads_slim/fastq/H_sapiens/giab/bjuice_preval_2026/HG002/ont/HG002_BJUICEPREVAL_ONT_5x.fastq.gz
SOURCE_S3_URI=s3://${SOURCE_BUCKET}/${SOURCE_KEY}
SOURCE_BYTES=62270705691
SOURCE_METADATA_SHA256=9bd2303e9a7c63e78b8e76cd8110ebad3b34828794336fd10b29393f320b6e21
SOURCE_READS=7759331
SOURCE_BASES=61029539852
SOURCE_DEPTH=19.7617

SEQKIT_PACKAGE_URL=https://conda.anaconda.org/bioconda/linux-64/seqkit-2.13.0-he881be0_0.conda
SEQKIT_PACKAGE_SHA256=538ff4ab33819598e45939fe36ea7f4505afba62e90a7cbd95c6f63493aee6d4
RAPIDGZIP_VERSION=0.16.0
RAPIDGZIP_WHEEL_SHA256=7162822e9e7aeb7f427420a7b9c6f9ee08212e41e5fba65c65ac3c564403a058
GENOME_BASES=3088269832
TARGET_DEPTH=5
TARGET_READS=1963980
MIN_ACCEPTED_DEPTH=2.5
MAX_ACCEPTED_DEPTH=7.5
DECOMPRESS_THREADS=36
HEAD_THREADS=4
STATS_THREADS=8
COMPRESS_THREADS=40
VALIDATION_THREADS=88

test -d /scratch
test -w /scratch
available_kib=$(df -Pk /scratch | awk 'NR == 2 {print $4}')
test "${available_kib}" -ge 104857600
test -x "${SEQKIT_PATH}"
test "$("${SEQKIT_PATH}" version)" = "seqkit v2.13.0"
test -x "${RAPIDGZIP_PATH}"
"${RAPIDGZIP_PATH}" --version | grep -Fq "version ${RAPIDGZIP_VERSION}"
test -f "${RAPIDGZIP_WHEEL}"
test "$(sha256sum "${RAPIDGZIP_WHEEL}" | awk 'NR == 1 {print $1}')" = "${RAPIDGZIP_WHEEL_SHA256}"
test "$(pigz --version 2>&1 | awk 'NR == 1 {print $2}')" = "2.6"

scratch_root=$(mktemp -d "/scratch/hg002-ont5x-rapid96-${SLURM_JOB_ID}.XXXXXX")
source_fastq=${scratch_root}/HG002_BJUICEPREVAL_ONT_full.fastq.gz
output_fastq=${scratch_root}/HG002_BJUICEPREVAL_ONT_5x.fastq.gz
raw_sha_fifo=${scratch_root}/raw-content-sha.fifo
stats_fifo=${scratch_root}/stats.fifo
raw_sha_file=${scratch_root}/raw-content.sha256
stats_file=${scratch_root}/HG002_BJUICEPREVAL_ONT_5x.seqkit.stats.tsv

staging_root=${OUTPUT_ROOT}/rapid96/staging
ont_dir=${staging_root}/ont
receipt_dir=${staging_root}/receipts
final_fastq=${ont_dir}/HG002_BJUICEPREVAL_ONT_5x.fastq.gz
final_stats=${receipt_dir}/HG002_BJUICEPREVAL_ONT_5x.seqkit.stats.tsv
final_sha=${receipt_dir}/HG002_BJUICEPREVAL_ONT_5x.sha256
final_raw_sha=${receipt_dir}/HG002_BJUICEPREVAL_ONT_5x.raw-content.sha256
final_receipt=${receipt_dir}/HG002_BJUICEPREVAL_ONT_5x.rapid96_rebuild_receipt.json

mkdir -p "${ont_dir}" "${receipt_dir}"
for path in \
  "${final_fastq}" "${final_stats}" "${final_sha}" \
  "${final_raw_sha}" "${final_receipt}"; do
  test ! -e "${path}"
done

started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
download_started=$(date +%s)
source_head=$(aws s3api head-object --bucket "${SOURCE_BUCKET}" --key "${SOURCE_KEY}" --output json)
test "$(jq -r '.ContentLength' <<<"${source_head}")" = "${SOURCE_BYTES}"
test "$(jq -r '.Metadata.sha256' <<<"${source_head}")" = "${SOURCE_METADATA_SHA256}"
aws s3 cp "${SOURCE_S3_URI}" "${source_fastq}" --only-show-errors
test "$(stat -c %s "${source_fastq}")" = "${SOURCE_BYTES}"
download_completed=$(date +%s)

extract_started=$(date +%s)
mkfifo "${raw_sha_fifo}" "${stats_fifo}"
sha256sum < "${raw_sha_fifo}" > "${raw_sha_file}" &
raw_sha_pid=$!
"${SEQKIT_PATH}" stats -T -j "${STATS_THREADS}" - < "${stats_fifo}" > "${stats_file}" &
stats_pid=$!

set +o pipefail
"${RAPIDGZIP_PATH}" -d -P "${DECOMPRESS_THREADS}" -c "${source_fastq}" \
  | "${SEQKIT_PATH}" head -n "${TARGET_READS}" -j "${HEAD_THREADS}" - \
  | tee "${raw_sha_fifo}" "${stats_fifo}" \
  | pigz -1 -p "${COMPRESS_THREADS}" > "${output_fastq}"
pipeline_status=("${PIPESTATUS[@]}")
set -o pipefail
test "${pipeline_status[0]}" = 0 || test "${pipeline_status[0]}" = 141
test "${pipeline_status[1]}" = 0
test "${pipeline_status[2]}" = 0
test "${pipeline_status[3]}" = 0
wait "${raw_sha_pid}"
wait "${stats_pid}"
rm "${raw_sha_fifo}" "${stats_fifo}"
extract_completed=$(date +%s)

read -r observed_reads observed_bases < <(
  awk -F '\t' '
    NR == 1 {
      for (i = 1; i <= NF; i++) {
        if ($i == "num_seqs") n = i
        if ($i == "sum_len") s = i
      }
      if (!n || !s) exit 2
    }
    NR == 2 {print $n, $s; found = 1}
    END {if (!found) exit 3}
  ' "${stats_file}"
)
observed_bytes=$(stat -c %s "${output_fastq}")
observed_raw_sha256=$(awk 'NR == 1 {print $1}' "${raw_sha_file}")
observed_depth=$(awk -v bases="${observed_bases}" -v genome="${GENOME_BASES}" 'BEGIN {printf "%.9f", bases / genome}')
test "${observed_reads}" = "${TARGET_READS}"
awk -v depth="${observed_depth}" -v min="${MIN_ACCEPTED_DEPTH}" -v max="${MAX_ACCEPTED_DEPTH}" \
  'BEGIN {exit !(depth >= min && depth <= max)}'

validation_started=$(date +%s)
"${RAPIDGZIP_PATH}" -d -P "${VALIDATION_THREADS}" -f -c "${output_fastq}" > /dev/null &
gzip_pid=$!
sha256sum "${output_fastq}" > "${output_fastq}.sha256" &
sha_pid=$!
wait "${gzip_pid}"
wait "${sha_pid}"
observed_sha256=$(awk 'NR == 1 {print $1}' "${output_fastq}.sha256")
validation_completed=$(date +%s)

publish_started=$(date +%s)
cp "${output_fastq}" "${final_fastq}.partial"
test "$(stat -c %s "${final_fastq}.partial")" = "${observed_bytes}"
mv "${final_fastq}.partial" "${final_fastq}"
cp "${stats_file}" "${final_stats}"
printf '%s  %s\n' "${observed_sha256}" "${final_fastq}" > "${final_sha}"
printf '%s  %s (uncompressed FASTQ stream)\n' \
  "${observed_raw_sha256}" "${final_fastq}" > "${final_raw_sha}"
publish_completed=$(date +%s)
completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

jq -n \
  --arg started_at "${started_at}" \
  --arg completed_at "${completed_at}" \
  --arg source_s3_uri "${SOURCE_S3_URI}" \
  --arg source_metadata_sha256 "${SOURCE_METADATA_SHA256}" \
  --argjson source_bytes "${SOURCE_BYTES}" \
  --argjson source_reads "${SOURCE_READS}" \
  --argjson source_bases "${SOURCE_BASES}" \
  --arg source_depth "${SOURCE_DEPTH}" \
  --argjson target_reads "${TARGET_READS}" \
  --argjson target_depth "${TARGET_DEPTH}" \
  --arg min_accepted_depth "${MIN_ACCEPTED_DEPTH}" \
  --arg max_accepted_depth "${MAX_ACCEPTED_DEPTH}" \
  --arg seqkit_path "${SEQKIT_PATH}" \
  --arg seqkit_package_url "${SEQKIT_PACKAGE_URL}" \
  --arg seqkit_package_sha256 "${SEQKIT_PACKAGE_SHA256}" \
  --arg rapidgzip_path "${RAPIDGZIP_PATH}" \
  --arg rapidgzip_version "${RAPIDGZIP_VERSION}" \
  --arg rapidgzip_wheel "${RAPIDGZIP_WHEEL}" \
  --arg rapidgzip_wheel_sha256 "${RAPIDGZIP_WHEEL_SHA256}" \
  --arg output_path "${final_fastq}" \
  --arg output_sha256 "${observed_sha256}" \
  --arg output_raw_sha256 "${observed_raw_sha256}" \
  --argjson output_bytes "${observed_bytes}" \
  --argjson output_reads "${observed_reads}" \
  --argjson output_bases "${observed_bases}" \
  --arg output_depth "${observed_depth}" \
  --arg job_id "${SLURM_JOB_ID}" \
  --arg node "$(hostname)" \
  --arg scratch_root "${scratch_root}" \
  --arg pigz_version "$(pigz --version 2>&1 | awk 'NR == 1 {print $2}')" \
  --argjson decompress_threads "${DECOMPRESS_THREADS}" \
  --argjson head_threads "${HEAD_THREADS}" \
  --argjson stats_threads "${STATS_THREADS}" \
  --argjson compress_threads "${COMPRESS_THREADS}" \
  --argjson validation_threads "${VALIDATION_THREADS}" \
  --argjson download_seconds "$((download_completed - download_started))" \
  --argjson extract_compress_stats_seconds "$((extract_completed - extract_started))" \
  --argjson validation_seconds "$((validation_completed - validation_started))" \
  --argjson publish_seconds "$((publish_completed - publish_started))" \
  '{
    schema: "lsmc.hg002_bjuice_ont_5x_rapid96/1.0",
    status: "SUCCESS",
    s3_replacement_status: "STAGED_NOT_APPLIED",
    started_at: $started_at,
    completed_at: $completed_at,
    source: {
      s3_uri: $source_s3_uri,
      bytes: $source_bytes,
      metadata_sha256: $source_metadata_sha256,
      read_count: $source_reads,
      sequenced_bases: $source_bases,
      measured_depth: ($source_depth | tonumber)
    },
    algorithm: {
      method: "parallel gzip prefix extraction by estimated read count",
      target_depth: $target_depth,
      target_reads: $target_reads,
      estimate: "source_reads * target_depth / source_measured_depth, rounded to 1963980 complete FASTQ records",
      accepted_depth_range: [($min_accepted_depth | tonumber), ($max_accepted_depth | tonumber)],
      seqkit: {
        version: "2.13.0",
        binary: $seqkit_path,
        package_url: $seqkit_package_url,
        package_sha256: $seqkit_package_sha256,
        head_threads: $head_threads,
        stats_threads: $stats_threads
      },
      decompression: {
        tool: "rapidgzip",
        version: $rapidgzip_version,
        binary: $rapidgzip_path,
        wheel: $rapidgzip_wheel,
        wheel_sha256: $rapidgzip_wheel_sha256,
        threads: $decompress_threads
      },
      compression: {
        tool: "pigz",
        version: $pigz_version,
        level: 1,
        threads: $compress_threads
      }
    },
    output: {
      fsx_path: $output_path,
      bytes: $output_bytes,
      sha256: $output_sha256,
      uncompressed_fastq_sha256: $output_raw_sha256,
      read_count: $output_reads,
      sequenced_bases: $output_bases,
      measured_depth: ($output_depth | tonumber)
    },
    validation: {
      rapidgzip_crc_to_eof: "pass",
      fastq_stream_stats: "pass",
      exact_target_read_count: "pass",
      accepted_depth_range: "pass",
      threads: $validation_threads
    },
    runtime: {
      download_seconds: $download_seconds,
      extract_compress_and_stats_seconds: $extract_compress_stats_seconds,
      validation_seconds: $validation_seconds,
      publish_to_fsx_seconds: $publish_seconds
    },
    slurm: {
      job_id: $job_id,
      node: $node,
      partition: "i96nvme",
      cpus: 96,
      scratch_root: $scratch_root,
      cost_center: "RnD"
    }
  }' > "${final_receipt}.partial"
mv "${final_receipt}.partial" "${final_receipt}"

printf 'SUCCESS output=%s sha256=%s raw_sha256=%s bytes=%s reads=%s bases=%s depth=%s total_seconds=%s receipt=%s\n' \
  "${final_fastq}" "${observed_sha256}" "${observed_raw_sha256}" \
  "${observed_bytes}" "${observed_reads}" "${observed_bases}" \
  "${observed_depth}" "$((publish_completed - download_started))" "${final_receipt}"
