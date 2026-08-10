#!/usr/bin/env bash
#SBATCH --job-name=hg002_ont5x_rebuild
#SBATCH --partition=i8
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00

set -Eeuo pipefail
umask 022

: "${OUTPUT_ROOT:?Set OUTPUT_ROOT to the locked analysis-root staging directory}"
: "${SEQKIT_PATH:?Set SEQKIT_PATH to the exact SeqKit 2.13.0 binary}"

SOURCE=/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/bjuice_preval_2026/HG002/ont/HG002_BJUICEPREVAL_ONT_5x.fastq.gz
SOURCE_S3_URI=s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/bjuice_preval_2026/HG002/ont/HG002_BJUICEPREVAL_ONT_5x.fastq.gz
SOURCE_BYTES=62270705691
SOURCE_SHA256=9bd2303e9a7c63e78b8e76cd8110ebad3b34828794336fd10b29393f320b6e21
SOURCE_READS=7759331
SOURCE_BASES=61029539852

REF_FAI=/fsx/references/genomic_data/organism_references/H_sapiens/hg38/fasta_fai_minalt/GRCh38_no_alt_analysis_set.fasta.fai
REF_FAI_SHA256=502a1b8fb73ccd53285c28a0f12df90c818b4fe3de1e862ef47c593ef1a0a4b4
GENOME_BASES=3088269832

SEQKIT_PACKAGE_URL=https://conda.anaconda.org/bioconda/linux-64/seqkit-2.13.0-he881be0_0.conda
SEQKIT_PACKAGE_SHA256=538ff4ab33819598e45939fe36ea7f4505afba62e90a7cbd95c6f63493aee6d4
SEED=1340
PROPORTION=0.253014346781

EXPECTED_BYTES=16810459174
EXPECTED_READS=1963980
EXPECTED_BASES=15447946531
EXPECTED_DEPTH=5.002136268
EXPECTED_SHA256=8758ef77c51ac473c145cbd777108373960f0d82c3f62d159e5d87d440f6cad1

WORK_DIR=${OUTPUT_ROOT}/work
STAGING_ROOT=${OUTPUT_ROOT}/staging
ONT_DIR=${STAGING_ROOT}/ont
RECEIPT_DIR=${STAGING_ROOT}/receipts
TMP_FASTQ=${WORK_DIR}/.HG002_BJUICEPREVAL_ONT_5x.seqkit-sample-seed1340.partial.fastq.gz
FINAL_FASTQ=${ONT_DIR}/HG002_BJUICEPREVAL_ONT_5x.fastq.gz
STATS=${RECEIPT_DIR}/HG002_BJUICEPREVAL_ONT_5x.seqkit.stats.tsv
SHA_FILE=${RECEIPT_DIR}/HG002_BJUICEPREVAL_ONT_5x.sha256
RECEIPT=${RECEIPT_DIR}/HG002_BJUICEPREVAL_ONT_5x.rebuild_receipt.json

mkdir -p "${WORK_DIR}" "${ONT_DIR}" "${RECEIPT_DIR}"
for path in "${TMP_FASTQ}" "${FINAL_FASTQ}" "${STATS}" "${SHA_FILE}" "${RECEIPT}"; do
  test ! -e "${path}"
done

test -f "${SOURCE}"
test ! -L "${SOURCE}"
test "$(stat -c %s "${SOURCE}")" = "${SOURCE_BYTES}"
test -f "${REF_FAI}"
test ! -L "${REF_FAI}"
test "$(sha256sum "${REF_FAI}" | awk '{print $1}')" = "${REF_FAI_SHA256}"
test "$(${SEQKIT_PATH} version)" = "seqkit v2.13.0"

started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"${SEQKIT_PATH}" sample \
  -s "${SEED}" \
  -p "${PROPORTION}" \
  -j "${SLURM_CPUS_PER_TASK}" \
  --compress-level 1 \
  -o "${TMP_FASTQ}" \
  "${SOURCE}"

pigz -t "${TMP_FASTQ}"
sha256sum "${TMP_FASTQ}" > "${SHA_FILE}.partial" &
sha_pid=$!
"${SEQKIT_PATH}" stats -T -a -j "${SLURM_CPUS_PER_TASK}" "${TMP_FASTQ}" > "${STATS}.partial"
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
  ' "${STATS}.partial"
)
observed_bytes=$(stat -c %s "${TMP_FASTQ}")
observed_sha256=$(awk 'NR == 1 {print $1}' "${SHA_FILE}.partial")
observed_depth=$(awk -v bases="${observed_bases}" -v genome="${GENOME_BASES}" 'BEGIN {printf "%.9f", bases / genome}')

test "${observed_bytes}" = "${EXPECTED_BYTES}"
test "${observed_reads}" = "${EXPECTED_READS}"
test "${observed_bases}" = "${EXPECTED_BASES}"
test "${observed_depth}" = "${EXPECTED_DEPTH}"
test "${observed_sha256}" = "${EXPECTED_SHA256}"

mv "${TMP_FASTQ}" "${FINAL_FASTQ}"
mv "${STATS}.partial" "${STATS}"
printf '%s  %s\n' "${observed_sha256}" "${FINAL_FASTQ}" > "${SHA_FILE}"
rm -f "${SHA_FILE}.partial"
completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

jq -n \
  --arg started_at "${started_at}" \
  --arg completed_at "${completed_at}" \
  --arg source_path "${SOURCE}" \
  --arg source_s3_uri "${SOURCE_S3_URI}" \
  --arg source_sha256 "${SOURCE_SHA256}" \
  --argjson source_bytes "${SOURCE_BYTES}" \
  --argjson source_reads "${SOURCE_READS}" \
  --argjson source_bases "${SOURCE_BASES}" \
  --arg ref_fai "${REF_FAI}" \
  --arg ref_fai_sha256 "${REF_FAI_SHA256}" \
  --argjson genome_bases "${GENOME_BASES}" \
  --arg seqkit_path "${SEQKIT_PATH}" \
  --arg seqkit_package_url "${SEQKIT_PACKAGE_URL}" \
  --arg seqkit_package_sha256 "${SEQKIT_PACKAGE_SHA256}" \
  --argjson seed "${SEED}" \
  --arg proportion "${PROPORTION}" \
  --arg output_path "${FINAL_FASTQ}" \
  --arg output_sha256 "${observed_sha256}" \
  --argjson output_bytes "${observed_bytes}" \
  --argjson output_reads "${observed_reads}" \
  --argjson output_bases "${observed_bases}" \
  --arg output_depth "${observed_depth}" \
  --arg job_id "${SLURM_JOB_ID}" \
  --arg node "$(hostname)" \
  '{
    schema: "lsmc.hg002_bjuice_ont_5x_rebuild/1.0",
    status: "SUCCESS",
    s3_replacement_status: "STAGED_NOT_APPLIED",
    started_at: $started_at,
    completed_at: $completed_at,
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
    genome_denominator: {
      reference_fai: $ref_fai,
      reference_fai_sha256: $ref_fai_sha256,
      contig_policy: "24 primary contigs; exclude names containing underscore, chrM, and chrEBV",
      bases: $genome_bases
    },
    source: {
      fsx_path: $source_path,
      s3_uri: $source_s3_uri,
      bytes: $source_bytes,
      sha256: $source_sha256,
      read_count: $source_reads,
      sequenced_bases: $source_bases,
      measured_depth: ($source_bases / $genome_bases),
      note: "The pre-existing key is mislabeled 5x but contains full-coverage HG002 ONT data."
    },
    output: {
      fsx_path: $output_path,
      intended_s3_uri: $source_s3_uri,
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
    slurm: {
      job_id: $job_id,
      node: $node,
      partition: "i8",
      cost_center: "RnD",
      cpus: 8
    }
  }' > "${RECEIPT}.partial"
mv "${RECEIPT}.partial" "${RECEIPT}"

printf 'SUCCESS output=%s sha256=%s reads=%s bases=%s depth=%s receipt=%s\n' \
  "${FINAL_FASTQ}" "${observed_sha256}" "${observed_reads}" \
  "${observed_bases}" "${observed_depth}" "${RECEIPT}"
