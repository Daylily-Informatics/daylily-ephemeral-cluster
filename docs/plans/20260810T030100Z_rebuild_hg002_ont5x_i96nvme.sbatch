#!/usr/bin/env bash
#SBATCH --job-name=hg002_ont5x_fast96
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

EXPECTED_BYTES=16810459174
EXPECTED_READS=1963980
EXPECTED_BASES=15447946531
EXPECTED_DEPTH=5.002136268
EXPECTED_SHA256=8758ef77c51ac473c145cbd777108373960f0d82c3f62d159e5d87d440f6cad1

test -d /scratch
test -w /scratch
available_kib=$(df -Pk /scratch | awk 'NR == 2 {print $4}')
test "${available_kib}" -ge 94371840
test -x "${SEQKIT_PATH}"
test "$("${SEQKIT_PATH}" version)" = "seqkit v2.13.0"

scratch_root=$(mktemp -d "/scratch/hg002-ont5x-${SLURM_JOB_ID}.XXXXXX")
source_fastq=${scratch_root}/HG002_BJUICEPREVAL_ONT_full.fastq.gz
output_fastq=${scratch_root}/HG002_BJUICEPREVAL_ONT_5x.fastq.gz
stats_partial=${scratch_root}/HG002_BJUICEPREVAL_ONT_5x.seqkit.stats.tsv
sha_partial=${scratch_root}/HG002_BJUICEPREVAL_ONT_5x.sha256

staging_root=${OUTPUT_ROOT}/fast96/staging
ont_dir=${staging_root}/ont
receipt_dir=${staging_root}/receipts
final_fastq=${ont_dir}/HG002_BJUICEPREVAL_ONT_5x.fastq.gz
final_stats=${receipt_dir}/HG002_BJUICEPREVAL_ONT_5x.seqkit.stats.tsv
final_sha=${receipt_dir}/HG002_BJUICEPREVAL_ONT_5x.sha256
final_receipt=${receipt_dir}/HG002_BJUICEPREVAL_ONT_5x.fast96_rebuild_receipt.json

mkdir -p "${ont_dir}" "${receipt_dir}"
for path in "${final_fastq}" "${final_stats}" "${final_sha}" "${final_receipt}"; do
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
"${SEQKIT_PATH}" sample \
  -s "${SEED}" \
  -p "${PROPORTION}" \
  -j "${SLURM_CPUS_PER_TASK}" \
  --compress-level 1 \
  -o "${output_fastq}" \
  "${source_fastq}"
sample_completed=$(date +%s)

validation_started=$(date +%s)
pigz -t "${output_fastq}" &
gzip_pid=$!
sha256sum "${output_fastq}" > "${sha_partial}" &
sha_pid=$!
"${SEQKIT_PATH}" stats -T -a -j "${SLURM_CPUS_PER_TASK}" "${output_fastq}" > "${stats_partial}"
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
  ' "${stats_partial}"
)
observed_bytes=$(stat -c %s "${output_fastq}")
observed_sha256=$(awk 'NR == 1 {print $1}' "${sha_partial}")
observed_depth=$(awk -v bases="${observed_bases}" -v genome="${GENOME_BASES}" 'BEGIN {printf "%.9f", bases / genome}')

test "${observed_bytes}" = "${EXPECTED_BYTES}"
test "${observed_reads}" = "${EXPECTED_READS}"
test "${observed_bases}" = "${EXPECTED_BASES}"
test "${observed_depth}" = "${EXPECTED_DEPTH}"
test "${observed_sha256}" = "${EXPECTED_SHA256}"
validation_completed=$(date +%s)

publish_started=$(date +%s)
cp "${output_fastq}" "${final_fastq}.partial"
test "$(stat -c %s "${final_fastq}.partial")" = "${EXPECTED_BYTES}"
mv "${final_fastq}.partial" "${final_fastq}"
cp "${stats_partial}" "${final_stats}"
printf '%s  %s\n' "${observed_sha256}" "${final_fastq}" > "${final_sha}"
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
  --argjson output_bytes "${observed_bytes}" \
  --argjson output_reads "${observed_reads}" \
  --argjson output_bases "${observed_bases}" \
  --arg output_depth "${observed_depth}" \
  --arg job_id "${SLURM_JOB_ID}" \
  --arg node "$(hostname)" \
  --arg scratch_root "${scratch_root}" \
  --argjson download_seconds "$((download_completed - download_started))" \
  --argjson sample_seconds "$((sample_completed - sample_started))" \
  --argjson validation_seconds "$((validation_completed - validation_started))" \
  --argjson publish_seconds "$((publish_completed - publish_started))" \
  '{
    schema: "lsmc.hg002_bjuice_ont_5x_fast96_rebuild/1.0",
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
      compression_level: 1,
      seqkit: {
        version: "2.13.0",
        binary: $seqkit_path,
        package_url: $seqkit_package_url,
        package_sha256: $seqkit_package_sha256
      }
    },
    output: {
      fsx_path: $output_path,
      bytes: $output_bytes,
      sha256: $output_sha256,
      read_count: $output_reads,
      sequenced_bases: $output_bases,
      measured_depth: ($output_depth | tonumber)
    },
    validation: {
      gzip_test: "pass",
      fastq_parse_to_eof: "pass",
      expected_byte_identity: "pass",
      expected_sha256_identity: "pass"
    },
    runtime: {
      download_seconds: $download_seconds,
      sample_seconds: $sample_seconds,
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

printf 'SUCCESS output=%s sha256=%s reads=%s bases=%s depth=%s total_seconds=%s receipt=%s\n' \
  "${final_fastq}" "${observed_sha256}" "${observed_reads}" \
  "${observed_bases}" "${observed_depth}" \
  "$((publish_completed - download_started))" "${final_receipt}"
