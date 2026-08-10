#!/usr/bin/env bash
#SBATCH --job-name=hg002_ont5x_stream96
#SBATCH --partition=i96nvme
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=96
#SBATCH --time=00:20:00

set -Eeuo pipefail
umask 022

: "${OUTPUT_ROOT:?Set OUTPUT_ROOT to the locked analysis-root staging directory}"
: "${SEQKIT_PATH:?Set SEQKIT_PATH to the exact SeqKit 2.13.0 binary}"

SOURCE_BUCKET=lsmc-dayoa-references-usw2
SOURCE_KEY=genomic_data/organism_reads_slim/fastq/H_sapiens/giab/bjuice_preval_2026/HG002/ont/HG002_BJUICEPREVAL_ONT_5x.fastq.gz
SOURCE_S3_URI=s3://${SOURCE_BUCKET}/${SOURCE_KEY}
SOURCE_BYTES=62270705691
SOURCE_METADATA_SHA256=9bd2303e9a7c63e78b8e76cd8110ebad3b34828794336fd10b29393f320b6e21

SEQKIT_PACKAGE_URL=https://conda.anaconda.org/bioconda/linux-64/seqkit-2.13.0-he881be0_0.conda
SEQKIT_PACKAGE_SHA256=538ff4ab33819598e45939fe36ea7f4505afba62e90a7cbd95c6f63493aee6d4
SEED=1340
PROPORTION=0.253014346781
GENOME_BASES=3088269832
DECOMPRESS_THREADS=44
SEQKIT_THREADS=8
COMPRESS_THREADS=44

EXPECTED_READS=1963980
EXPECTED_BASES=15447946531
EXPECTED_DEPTH=5.002136268

test -d /scratch
test -w /scratch
available_kib=$(df -Pk /scratch | awk 'NR == 2 {print $4}')
test "${available_kib}" -ge 104857600
test -x "${SEQKIT_PATH}"
test "$("${SEQKIT_PATH}" version)" = "seqkit v2.13.0"
test "$(pigz --version 2>&1 | awk 'NR == 1 {print $2}')" = "2.6"

scratch_root=$(mktemp -d "/scratch/hg002-ont5x-stream96-${SLURM_JOB_ID}.XXXXXX")
source_fastq=${scratch_root}/HG002_BJUICEPREVAL_ONT_full.fastq.gz
output_fastq=${scratch_root}/HG002_BJUICEPREVAL_ONT_5x.fastq.gz
raw_sha_fifo=${scratch_root}/raw-content-sha.fifo
raw_sha_file=${scratch_root}/raw-content.sha256
stats_file=${scratch_root}/HG002_BJUICEPREVAL_ONT_5x.seqkit.stats.tsv

staging_root=${OUTPUT_ROOT}/stream96_external/staging
ont_dir=${staging_root}/ont
receipt_dir=${staging_root}/receipts
final_fastq=${ont_dir}/HG002_BJUICEPREVAL_ONT_5x.fastq.gz
final_stats=${receipt_dir}/HG002_BJUICEPREVAL_ONT_5x.seqkit.stats.tsv
final_sha=${receipt_dir}/HG002_BJUICEPREVAL_ONT_5x.sha256
final_raw_sha=${receipt_dir}/HG002_BJUICEPREVAL_ONT_5x.raw-content.sha256
final_receipt=${receipt_dir}/HG002_BJUICEPREVAL_ONT_5x.stream96_rebuild_receipt.json

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

sample_started=$(date +%s)
mkfifo "${raw_sha_fifo}"
sha256sum < "${raw_sha_fifo}" > "${raw_sha_file}" &
raw_sha_pid=$!
pigz -dc -p "${DECOMPRESS_THREADS}" "${source_fastq}" \
  | "${SEQKIT_PATH}" sample \
  -s "${SEED}" \
  -p "${PROPORTION}" \
  -j "${SEQKIT_THREADS}" \
  - \
  | tee "${raw_sha_fifo}" \
  | pigz -1 -p "${COMPRESS_THREADS}" > "${output_fastq}"
wait "${raw_sha_pid}"
rm "${raw_sha_fifo}"
sample_completed=$(date +%s)

validation_started=$(date +%s)
pigz -t "${output_fastq}" &
gzip_pid=$!
sha256sum "${output_fastq}" > "${output_fastq}.sha256" &
sha_pid=$!
"${SEQKIT_PATH}" stats -T -a -j "${SLURM_CPUS_PER_TASK}" "${output_fastq}" > "${stats_file}"
wait "${gzip_pid}"
wait "${sha_pid}"

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
observed_sha256=$(awk 'NR == 1 {print $1}' "${output_fastq}.sha256")
observed_raw_sha256=$(awk 'NR == 1 {print $1}' "${raw_sha_file}")
observed_depth=$(awk -v bases="${observed_bases}" -v genome="${GENOME_BASES}" 'BEGIN {printf "%.9f", bases / genome}')

test "${observed_reads}" = "${EXPECTED_READS}"
test "${observed_bases}" = "${EXPECTED_BASES}"
test "${observed_depth}" = "${EXPECTED_DEPTH}"
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
  --arg seqkit_path "${SEQKIT_PATH}" \
  --arg seqkit_package_url "${SEQKIT_PACKAGE_URL}" \
  --arg seqkit_package_sha256 "${SEQKIT_PACKAGE_SHA256}" \
  --argjson seed "${SEED}" \
  --arg proportion "${PROPORTION}" \
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
  --argjson seqkit_threads "${SEQKIT_THREADS}" \
  --argjson compress_threads "${COMPRESS_THREADS}" \
  --argjson download_seconds "$((download_completed - download_started))" \
  --argjson sample_compress_seconds "$((sample_completed - sample_started))" \
  --argjson validation_seconds "$((validation_completed - validation_started))" \
  --argjson publish_seconds "$((publish_completed - publish_started))" \
  '{
    schema: "lsmc.hg002_bjuice_ont_5x_stream96_rebuild/1.0",
    status: "SUCCESS",
    s3_replacement_status: "STAGED_NOT_APPLIED",
    started_at: $started_at,
    completed_at: $completed_at,
    source: {
      s3_uri: $source_s3_uri,
      bytes: $source_bytes,
      metadata_sha256: $source_metadata_sha256
    },
    algorithm: {
      method: "deterministic read-level Bernoulli sampling by proportion",
      seed: $seed,
      proportion: ($proportion | tonumber),
      seqkit: {
        version: "2.13.0",
        binary: $seqkit_path,
        package_url: $seqkit_package_url,
        package_sha256: $seqkit_package_sha256,
        threads: $seqkit_threads
      },
      compression: {
        tool: "pigz",
        version: $pigz_version,
        level: 1,
        decompress_threads: $decompress_threads,
        compress_threads: $compress_threads
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
      gzip_test: "pass",
      fastq_parse_to_eof: "pass",
      expected_read_count: "pass",
      expected_base_count: "pass",
      expected_depth: "pass"
    },
    runtime: {
      download_seconds: $download_seconds,
      sample_and_compress_seconds: $sample_compress_seconds,
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
