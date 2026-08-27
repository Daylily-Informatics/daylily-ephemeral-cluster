#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ID="ganon2_blood_oral_ref_20260827_v1"
GANON_VERSION="2.4.2"
GANON_ENV="/fsx/resources/environments/conda/ubuntu/bjuiceval-19024-f9659ef0-9f51-11f1-88c8-0aaa3ce07dcb/433d4cfa1fd26a4990882bc52989499d_"
GANON="${GANON_ENV}/bin/ganon"
GENOME_UPDATER="${GANON_ENV}/bin/genome_updater.sh"
export PATH="${GANON_ENV}/bin:${PATH}"
THREADS="${SLURM_CPUS_PER_TASK:-192}"
# NCBI serves one file per selected assembly. A 64-way first attempt was
# measured to reject most requests from one node, so keep the downloader at the
# upstream example's conservative concurrency while retaining all 192 threads
# for index construction.
DOWNLOAD_THREADS=12
DOWNLOAD_RETRY_BATCHES=10
KMER_SIZE=27
WINDOW_SIZE=51
MAX_FP=0.001
STAGING_ROOT="/fsx/analysis_results/bjuiceval-19024/${BUNDLE_ID}"
SCRIPT_DIR="${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is required}"
BUILD_ROOT="/scratch/${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
WORK_ROOT="${BUILD_ROOT}/${BUNDLE_ID}"
COMPONENT_ROOT="${WORK_ROOT}/components"
DOWNLOAD_ROOT="${WORK_ROOT}/downloads"
MANIFEST_ROOT="${WORK_ROOT}/manifests"
LOG_ROOT="${WORK_ROOT}/logs"
RELEASE_ROOT="${WORK_ROOT}/release/${BUNDLE_ID}"
START_EPOCH="$(date +%s)"

mkdir -p "${COMPONENT_ROOT}" "${DOWNLOAD_ROOT}" "${MANIFEST_ROOT}" "${LOG_ROOT}" "${RELEASE_ROOT}"

exec > >(tee -a "${LOG_ROOT}/build.stdout.log") 2> >(tee -a "${LOG_ROOT}/build.stderr.log" >&2)

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

require_file() {
    local path="$1"
    [[ -s "${path}" ]] || fail "required non-empty file is missing: ${path}"
}

require_no_download_failures() {
    local label="$1"
    local root="$2"
    local failure_report
    failure_report="$(find "${root}" -type f -name '*_url_failed.txt' -size +0c -print -quit)"
    [[ -z "${failure_report}" ]] || fail \
        "${label} retained unresolved selected-source downloads: ${failure_report}"
}

run_timed() {
    local label="$1"
    shift
    printf 'START\t%s\t%s\n' "${label}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    /usr/bin/time -v -o "${LOG_ROOT}/${label}.time.txt" "$@"
    printf 'END\t%s\t%s\n' "${label}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

[[ "$(id -un)" == "ubuntu" ]] || fail "database build must run as ubuntu"
[[ -x "${GANON}" ]] || fail "pinned ganon executable is missing: ${GANON}"
[[ -x "${GENOME_UPDATER}" ]] || fail "pinned genome_updater is missing: ${GENOME_UPDATER}"
[[ "$("${GANON}" --version | awk '{print $NF}')" == "${GANON_VERSION}" ]] || fail "ganon version is not ${GANON_VERSION}"
[[ "${THREADS}" == "192" ]] || fail "expected 192 build threads, saw ${THREADS}"
[[ "${WORK_ROOT}" == /scratch/${SLURM_JOB_ID}/* ]] || fail "build root is not job-local scratch"
[[ -s "${SCRIPT_DIR}/food_watchlist.tsv" ]] || fail "food watchlist is missing beside build script"
[[ -s "${SCRIPT_DIR}/medical_parasite_watchlist.tsv" ]] || fail "parasite watchlist is missing beside build script"

{
    printf 'bundle_id\t%s\n' "${BUNDLE_ID}"
    printf 'ganon_version\t%s\n' "${GANON_VERSION}"
    printf 'build_started_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'slurm_job_id\t%s\n' "${SLURM_JOB_ID}"
    printf 'slurm_job_name\t%s\n' "${SLURM_JOB_NAME:-unknown}"
    printf 'slurm_partition\t%s\n' "${SLURM_JOB_PARTITION:-unknown}"
    printf 'node\t%s\n' "$(hostname -f)"
    printf 'threads\t%s\n' "${THREADS}"
    printf 'download_threads\t%s\n' "${DOWNLOAD_THREADS}"
    printf 'kmer_size\t%s\n' "${KMER_SIZE}"
    printf 'window_size\t%s\n' "${WINDOW_SIZE}"
    printf 'max_fp\t%s\n' "${MAX_FP}"
    printf 'scratch_root\t%s\n' "${BUILD_ROOT}"
    printf 'staging_root\t%s\n' "${STAGING_ROOT}"
} > "${MANIFEST_ROOT}/build_context.tsv"

cp "${SCRIPT_DIR}/food_watchlist.tsv" "${MANIFEST_ROOT}/food_watchlist.tsv"
cp "${SCRIPT_DIR}/medical_parasite_watchlist.tsv" "${MANIFEST_ROOT}/medical_parasite_watchlist.tsv"
sha256sum "${BASH_SOURCE[0]}" "${SCRIPT_DIR}/food_watchlist.tsv" \
    "${SCRIPT_DIR}/medical_parasite_watchlist.tsv" \
    > "${MANIFEST_ROOT}/small_input_sha256.tsv"

TAXDUMP="${DOWNLOAD_ROOT}/taxdump_20260827.tar.gz"
curl --fail --location --retry 5 --retry-delay 10 \
    --dump-header "${MANIFEST_ROOT}/ncbi_taxdump_headers.txt" \
    --output "${TAXDUMP}" \
    "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz"
require_file "${TAXDUMP}"

HUMAN_FASTA="/fsx/references/genomic_data/organism_references/H_sapiens/hg38/fasta_fai_minalt/GRCh38_no_alt_analysis_set.fasta"
require_file "${HUMAN_FASTA}"
HOST_INPUT_ROOT="${DOWNLOAD_ROOT}/host_qc"
mkdir -p "${HOST_INPUT_ROOT}"
cp "${HUMAN_FASTA}" "${HOST_INPUT_ROOT}/GRCh38_no_alt_analysis_set.fasta"
curl --fail --location --retry 5 --retry-delay 10 \
    --output "${HOST_INPUT_ROOT}/phix174_NC_001422.1.fasta" \
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_001422.1&rettype=fasta&retmode=text"
curl --fail --location --retry 5 --retry-delay 10 \
    --dump-header "${MANIFEST_ROOT}/univec_core_headers.txt" \
    --output "${HOST_INPUT_ROOT}/UniVec_Core.fasta" \
    "https://ftp.ncbi.nlm.nih.gov/pub/UniVec/UniVec_Core"
cat > "${HOST_INPUT_ROOT}/library_adapters.fasta" <<'EOF'
>illumina_truseq_universal
AGATCGGAAGAGCACACGTCTGAACTCCAGTCA
>illumina_truseq_indexed
AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT
>illumina_nextera_transposase
CTGTCTCTTATACACATCT
>ont_ligation_adapter_lsk109
GCAATACGTAACTGAACGAAGT
>ont_ligation_adapter_lsk110
TTTCTGTTGGTGCTGATATTGC
EOF
printf '%s\t%s\t%s\t%s\t%s\n' \
    "${HOST_INPUT_ROOT}/GRCh38_no_alt_analysis_set.fasta" host_human_file 9606 host_human "Homo sapiens GRCh38 no-alt" \
    "${HOST_INPUT_ROOT}/phix174_NC_001422.1.fasta" host_phix_file 10847 host_phix "PhiX174 control" \
    "${HOST_INPUT_ROOT}/UniVec_Core.fasta" host_univec_file 81077 host_univec "UniVec Core" \
    "${HOST_INPUT_ROOT}/library_adapters.fasta" host_adapters_file 81077 host_adapters "Library adapters" \
    > "${HOST_INPUT_ROOT}/host_qc_input.tsv"

run_timed host_qc \
    "${GANON}" build-custom \
    --input-file "${HOST_INPUT_ROOT}/host_qc_input.tsv" \
    --db-prefix "${COMPONENT_ROOT}/host_qc" \
    --level custom \
    --taxonomy ncbi \
    --taxonomy-files "${TAXDUMP}" \
    --skip-genome-size \
    --threads "${THREADS}" \
    --filter-type hibf \
    --max-fp "${MAX_FP}" \
    --kmer-size "${KMER_SIZE}" \
    --window-size "${WINDOW_SIZE}" \
    --write-info-file \
    --verbose

run_timed abfv_refseq_species1 \
    "${GANON}" build \
    --source refseq \
    --organism-group archaea bacteria fungi viral \
    --db-prefix "${COMPONENT_ROOT}/abfv_refseq_species1" \
    --level species \
    --taxonomy ncbi \
    --taxonomy-files "${TAXDUMP}" \
    --genome-updater "-A 'species:1' -m -u -p -n 1 -R ${DOWNLOAD_RETRY_BATCHES}" \
    --download-threads "${DOWNLOAD_THREADS}" \
    --threads "${THREADS}" \
    --filter-type hibf \
    --max-fp "${MAX_FP}" \
    --kmer-size "${KMER_SIZE}" \
    --window-size "${WINDOW_SIZE}" \
    --write-info-file \
    --verbose
require_no_download_failures abfv_refseq_species1 \
    "${COMPONENT_ROOT}/abfv_refseq_species1_files"

run_timed broad_euk_refseq_species1 \
    "${GANON}" build \
    --source refseq \
    --organism-group plant protozoa invertebrate vertebrate_mammalian vertebrate_other \
    --db-prefix "${COMPONENT_ROOT}/broad_euk_refseq_species1" \
    --level species \
    --taxonomy ncbi \
    --taxonomy-files "${TAXDUMP}" \
    --genome-updater "-A 'species:1' -T '^9606' -m -u -p -n 1 -R ${DOWNLOAD_RETRY_BATCHES}" \
    --download-threads "${DOWNLOAD_THREADS}" \
    --threads "${THREADS}" \
    --filter-type hibf \
    --max-fp "${MAX_FP}" \
    --kmer-size "${KMER_SIZE}" \
    --window-size "${WINDOW_SIZE}" \
    --write-info-file \
    --verbose
require_no_download_failures broad_euk_refseq_species1 \
    "${COMPONENT_ROOT}/broad_euk_refseq_species1_files"

SUMMARY_ROOT="${DOWNLOAD_ROOT}/assembly_summaries"
mkdir -p "${SUMMARY_ROOT}/refseq" "${SUMMARY_ROOT}/genbank"
ORGANISM_GROUPS=(archaea bacteria fungi viral plant protozoa invertebrate vertebrate_mammalian vertebrate_other)
for group in "${ORGANISM_GROUPS[@]}"; do
    for source in refseq genbank; do
        curl --fail --location --retry 5 --retry-delay 10 \
            --output "${SUMMARY_ROOT}/${source}/${group}.assembly_summary.txt" \
            "https://ftp.ncbi.nlm.nih.gov/genomes/${source}/${group}/assembly_summary.txt"
    done
done
awk -F '\t' '!/^#/ && $7 ~ /^[0-9]+$/ {print $7}' \
    "${SUMMARY_ROOT}"/refseq/*.assembly_summary.txt | sort -u \
    > "${MANIFEST_ROOT}/refseq_species_taxids.txt"
GAP_SUMMARY="${MANIFEST_ROOT}/genbank_species_gap_assembly_summary.txt"
head -n 2 "${SUMMARY_ROOT}/genbank/archaea.assembly_summary.txt" > "${GAP_SUMMARY}"
awk -F '\t' 'NR==FNR {seen[$1]=1; next} !/^#/ && $7 ~ /^[0-9]+$/ && $7 != 9606 && !seen[$7] {print}' \
    "${MANIFEST_ROOT}/refseq_species_taxids.txt" \
    "${SUMMARY_ROOT}"/genbank/*.assembly_summary.txt \
    | LC_ALL=C sort -t $'\t' -k7,7n -k1,1 \
    >> "${GAP_SUMMARY}"
require_file "${GAP_SUMMARY}"

GAP_DOWNLOAD="${DOWNLOAD_ROOT}/genbank_species_gap"
run_timed genbank_species_gap_download \
    "${GENOME_UPDATER}" \
    -e "${GAP_SUMMARY}" \
    -f genomic.fna.gz \
    -M ncbi \
    -A species:1 \
    -o "${GAP_DOWNLOAD}" \
    -b snapshot_20260827 \
    -N split \
    -t "${DOWNLOAD_THREADS}" \
    -R "${DOWNLOAD_RETRY_BATCHES}" \
    -n 1 \
    -L curl \
    -G -m -u -p
require_no_download_failures genbank_species_gap_download "${GAP_DOWNLOAD}"
mapfile -t GAP_FILES_DIRS < <(find "${GAP_DOWNLOAD}" -mindepth 2 -maxdepth 3 -type d -name files -print)
[[ "${#GAP_FILES_DIRS[@]}" -eq 1 ]] || fail "expected exactly one genome_updater files directory for GenBank gaps"
run_timed genbank_species_gap_species1 \
    "${GANON}" build-custom \
    --input "${GAP_FILES_DIRS[0]}" \
    --input-extension fna.gz \
    --input-recursive \
    --db-prefix "${COMPONENT_ROOT}/genbank_species_gap_species1" \
    --ncbi-file-info "${GAP_SUMMARY}" \
    --level species \
    --taxonomy ncbi \
    --taxonomy-files "${TAXDUMP}" \
    --threads "${THREADS}" \
    --filter-type hibf \
    --max-fp "${MAX_FP}" \
    --kmer-size "${KMER_SIZE}" \
    --window-size "${WINDOW_SIZE}" \
    --write-info-file \
    --verbose

ORAL_ROOT="${DOWNLOAD_ROOT}/mgnify_human_oral_v1.0.1"
mkdir -p "${ORAL_ROOT}/genomes"
ORAL_METADATA="${ORAL_ROOT}/genomes-all_metadata.tsv"
curl --fail --location --retry 5 --retry-delay 10 \
    --dump-header "${MANIFEST_ROOT}/mgnify_human_oral_headers.txt" \
    --output "${ORAL_METADATA}" \
    "https://ftp.ebi.ac.uk/pub/databases/metagenomics/mgnify_genomes/human-oral/v1.0.1/genomes-all_metadata.tsv"
require_file "${ORAL_METADATA}"
export ORAL_OUTPUT_DIR="${ORAL_ROOT}/genomes"
tail -n +2 "${ORAL_METADATA}" | cut -f 1,20 \
    | xargs -P "${DOWNLOAD_THREADS}" -n 2 bash -c '
        set -euo pipefail
        genome_id="$1"
        source_url="$2"
        curl --fail --location --retry 5 --retry-delay 10 --silent "${source_url}" \
            | gzip -d \
            | sed -e "1,/##FASTA/ d" \
            | gzip -1 -n > "${ORAL_OUTPUT_DIR}/${genome_id}.fna.gz"
        test -s "${ORAL_OUTPUT_DIR}/${genome_id}.fna.gz"
    ' _
ORAL_INPUT="${MANIFEST_ROOT}/mgnify_human_oral_v1.0.1.input.tsv"
tail -n +2 "${ORAL_METADATA}" | cut -f 1,15 | tr ';' '\t' \
    | awk -v root="${ORAL_ROOT}/genomes" -F '\t' \
        '{tax="1"; for(i=NF;i>1;i--){if(length($i)>3){tax=$i;break}}; print root "/" $1 ".fna.gz\t" $1 "\t" tax}' \
    > "${ORAL_INPUT}"
require_file "${ORAL_INPUT}"
run_timed mgnify_human_oral_v1_0_1 \
    "${GANON}" build-custom \
    --input-file "${ORAL_INPUT}" \
    --db-prefix "${COMPONENT_ROOT}/mgnify_human_oral_v1.0.1" \
    --taxonomy gtdb-89 \
    --level leaves \
    --threads "${THREADS}" \
    --filter-type hibf \
    --max-fp "${MAX_FP}" \
    --kmer-size "${KMER_SIZE}" \
    --window-size "${WINDOW_SIZE}" \
    --write-info-file \
    --verbose

for component in \
    host_qc \
    abfv_refseq_species1 \
    broad_euk_refseq_species1 \
    genbank_species_gap_species1 \
    mgnify_human_oral_v1.0.1; do
    require_file "${COMPONENT_ROOT}/${component}.hibf"
    require_file "${COMPONENT_ROOT}/${component}.tax"
    require_file "${COMPONENT_ROOT}/${component}.info.tsv"
    cp "${COMPONENT_ROOT}/${component}.hibf" "${RELEASE_ROOT}/${component}.hibf"
    cp "${COMPONENT_ROOT}/${component}.tax" "${RELEASE_ROOT}/${component}.tax"
    cp "${COMPONENT_ROOT}/${component}.info.tsv" "${RELEASE_ROOT}/${component}.info.tsv"
done

printf 'component\thierarchy\ttaxonomy\tlabel\tprefix\tkmer_size\twindow_size\tmax_fp\n' \
    > "${MANIFEST_ROOT}/bundle_components.tsv"
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    host_qc 1 ncbi host_qc "${BUNDLE_ID}/host_qc" "${KMER_SIZE}" "${WINDOW_SIZE}" "${MAX_FP}" \
    abfv_refseq_species1 2 ncbi primary_abfv "${BUNDLE_ID}/abfv_refseq_species1" "${KMER_SIZE}" "${WINDOW_SIZE}" "${MAX_FP}" \
    broad_euk_refseq_species1 2 ncbi primary_broad_euk "${BUNDLE_ID}/broad_euk_refseq_species1" "${KMER_SIZE}" "${WINDOW_SIZE}" "${MAX_FP}" \
    genbank_species_gap_species1 2 ncbi primary_genbank_gap "${BUNDLE_ID}/genbank_species_gap_species1" "${KMER_SIZE}" "${WINDOW_SIZE}" "${MAX_FP}" \
    mgnify_human_oral_v1.0.1 3 gtdb-89 oral_rescue "${BUNDLE_ID}/mgnify_human_oral_v1.0.1" "${KMER_SIZE}" "${WINDOW_SIZE}" "${MAX_FP}" \
    >> "${MANIFEST_ROOT}/bundle_components.tsv"

printf 'watchlist\ttaxid\tscientific_name\tcoverage_status\tcomponent\n' \
    > "${MANIFEST_ROOT}/watchlist_coverage.tsv"
for watchlist in food medical_parasite; do
    input_watchlist="${MANIFEST_ROOT}/${watchlist}_watchlist.tsv"
    tail -n +2 "${input_watchlist}" | while IFS=$'\t' read -r taxid scientific_name category; do
        component=""
        for candidate in abfv_refseq_species1 broad_euk_refseq_species1 genbank_species_gap_species1; do
            if awk -F '\t' -v wanted="${taxid}" '$1 == wanted {found=1; exit} END {exit !found}' \
                "${COMPONENT_ROOT}/${candidate}.tax"; then
                component="${candidate}"
                break
            fi
        done
        if [[ -n "${component}" ]]; then
            status="present"
        else
            status="not_present"
            component="NA"
        fi
        printf '%s\t%s\t%s\t%s\t%s\n' \
            "${watchlist}" "${taxid}" "${scientific_name}" "${status}" "${component}"
    done >> "${MANIFEST_ROOT}/watchlist_coverage.tsv"
done

END_EPOCH="$(date +%s)"
ELAPSED_SECONDS="$((END_EPOCH - START_EPOCH))"
{
    printf 'build_completed_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'elapsed_seconds\t%s\n' "${ELAPSED_SECONDS}"
} >> "${MANIFEST_ROOT}/build_context.tsv"
SOURCE_MANIFEST_ROOT="${MANIFEST_ROOT}/source_manifests"
mkdir -p "${SOURCE_MANIFEST_ROOT}"
while IFS= read -r -d '' source_manifest; do
    relative_path="${source_manifest#${COMPONENT_ROOT}/}"
    destination="${SOURCE_MANIFEST_ROOT}/components/${relative_path}"
    mkdir -p "$(dirname "${destination}")"
    cp "${source_manifest}" "${destination}"
done < <(find "${COMPONENT_ROOT}" -type f \( \
    -name assembly_summary.txt -o \
    -name '*_assembly_accession.txt' -o \
    -name '*_url_downloaded.txt' -o \
    -name '*_url_failed.txt' \
    \) -print0)
cp "${GAP_SUMMARY}" "${SOURCE_MANIFEST_ROOT}/genbank_species_gap_assembly_summary.txt"
cp "${ORAL_METADATA}" "${SOURCE_MANIFEST_ROOT}/mgnify_human_oral_v1.0.1.metadata.tsv"
find "${RELEASE_ROOT}" "${MANIFEST_ROOT}" "${LOG_ROOT}" -type f \
    -printf '%P\t%s\n' | LC_ALL=C sort \
    > "${MANIFEST_ROOT}/bundle_file_sizes.tsv"

[[ -d "${STAGING_ROOT}" ]] || fail "locked FSx staging root is missing: ${STAGING_ROOT}"
if find "${STAGING_ROOT}" -mindepth 1 -maxdepth 1 ! -name .dayoa_agent -print -quit | grep -q .; then
    fail "locked FSx staging root contains data outside .dayoa_agent: ${STAGING_ROOT}"
fi
cp -a "${RELEASE_ROOT}/." "${STAGING_ROOT}/"
cp -a "${MANIFEST_ROOT}" "${STAGING_ROOT}/manifests"
cp -a "${LOG_ROOT}" "${STAGING_ROOT}/logs"
printf 'complete\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${STAGING_ROOT}/BUILD_COMPLETE.tsv"
sync "${STAGING_ROOT}"
printf 'BUILD_COMPLETE\t%s\t%s\n' "${BUNDLE_ID}" "${STAGING_ROOT}"
