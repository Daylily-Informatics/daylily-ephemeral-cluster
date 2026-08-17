#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 <experiment-code> <analysis-root> <output-tar.gz>" >&2
    exit 2
fi

experiment_code=$1
analysis_root=$2
output_tar=$3
dayoa_root="${analysis_root}/daylily-omics-analysis"
manifest_dir="${dayoa_root}/results/day/hg38/reports/input_manifests"
identity_audit="${manifest_dir}/analysis_unit_identity_audit.tsv"

[[ "$experiment_code" == "E1" || "$experiment_code" == "E2" ]] || {
    echo "experiment code must be E1 or E2" >&2
    exit 2
}
[[ -d "$dayoa_root" ]] || { echo "missing DayOA root: $dayoa_root" >&2; exit 3; }
[[ -f "$identity_audit" ]] || { echo "missing identity audit: $identity_audit" >&2; exit 3; }
[[ ! -e "$output_tar" ]] || { echo "output already exists: $output_tar" >&2; exit 3; }

mapfile -t runtime_units < <(tail -n +2 "$identity_audit" | cut -f1)
[[ ${#runtime_units[@]} -eq 7 ]] || {
    echo "expected seven runtime analysis units; found ${#runtime_units[@]}" >&2
    exit 4
}

stage_root=$(mktemp -d "/tmp/hg002-bjuice-combined-${experiment_code}.XXXXXX")
bundle_root="${stage_root}/${experiment_code}"
dayoa_bundle="${bundle_root}/daylily-omics-analysis"
file_list="${stage_root}/dayoa-files.txt"
mkdir -p "$dayoa_bundle" "${bundle_root}/analysis-root-metadata"

find "$manifest_dir" -maxdepth 1 -type f -name '*.tsv' -printf '%P\n' \
    | sed 's#^#results/day/hg38/reports/input_manifests/#' >> "$file_list"

for report_file in benchmarks_summary.tsv dayoa_evidence_manifest.json; do
    report_path="results/day/hg38/reports/${report_file}"
    [[ -f "${dayoa_root}/${report_path}" ]] || {
        echo "missing required report: ${dayoa_root}/${report_path}" >&2
        exit 5
    }
    echo "$report_path" >> "$file_list"
done

if [[ -f "${dayoa_root}/config/hg002_bjuice_v2_multi_analysis_unit_hiomr2.yaml" ]]; then
    echo "config/hg002_bjuice_v2_multi_analysis_unit_hiomr2.yaml" >> "$file_list"
fi

for runtime_unit in "${runtime_units[@]}"; do
    unit_root="results/day/hg38/${runtime_unit}"
    [[ -d "${dayoa_root}/${unit_root}" ]] || {
        echo "missing runtime analysis-unit directory: ${dayoa_root}/${unit_root}" >&2
        exit 5
    }
    rg --files "${dayoa_root}/${unit_root}" \
        | sed "s#^${dayoa_root}/##" \
        | rg '(/align/sentdhiomr2rsr/na/alignqc/mosdepth/[^/]+\.summary\.txt$|/align/sentdhiomr2lr/na/alignqc/mosdepth/[^/]+\.summary\.txt$|/align/sentmm2ont/na/snv/sentdhiomr2/concordance/_giabHC/[^/]+_concordance\.mqc\.tsv$|/slim-consensus/truvari/[^/]+/queries/[^/]+/truvari/summary\.json$|/align/sentmm2ont/na/snv/sentdhiomr2/segdup/|/align/sentdhiomr2sr/smd/htd/smn12/[^/]+\.summary\.(tsv|json)$|/slim-consensus/prepared/smn12/[^/]+\.normalized\.json$)' \
        >> "$file_list" || true
done

sort -u -o "$file_list" "$file_list"

coverage_count=$(rg -c '/align/sentdhiomr2(rsr|lr)/na/alignqc/mosdepth/[^/]+\.summary\.txt$' "$file_list" || true)
hard_vcf_count=$(rg -c '/concordance/_giabHC/[^/]+_concordance\.mqc\.tsv$' "$file_list" || true)
truvari_count=$(rg -c '/truvari/summary\.json$' "$file_list" || true)
smn12_count=$(rg -c '/htd/smn12/[^/]+\.summary\.json$' "$file_list" || true)
segdup_count=$(rg -c '/segdup/.+\.result\.vcf\.gz$' "$file_list" || true)

[[ "$coverage_count" -eq 14 ]] || { echo "expected 14 coverage summaries; found $coverage_count" >&2; exit 6; }
[[ "$hard_vcf_count" -eq 7 ]] || { echo "expected 7 GIAB-HC hard-VCF files; found $hard_vcf_count" >&2; exit 6; }
[[ "$truvari_count" -eq 28 ]] || { echo "expected 28 raw Truvari summaries; found $truvari_count" >&2; exit 6; }
[[ "$smn12_count" -eq 7 ]] || { echo "expected 7 SMN12 JSON summaries; found $smn12_count" >&2; exit 6; }
[[ "$segdup_count" -gt 0 ]] || { echo "no SegDup result VCFs found" >&2; exit 6; }

rsync -a --files-from="$file_list" "${dayoa_root}/" "${dayoa_bundle}/"
cp -a "${analysis_root}/.dayoa_agent/owner.json" "${bundle_root}/analysis-root-metadata/owner.json"
cp -a "${analysis_root}/.dayoa_agent/visits" "${bundle_root}/analysis-root-metadata/visits"

source_inventory="${bundle_root}/source_inventory.tsv"
printf 'experiment\tanalysis_root\trelative_path\tbytes\tmtime_epoch\tsha256\n' > "$source_inventory"
while IFS= read -r relative_path; do
    original_path="${dayoa_root}/${relative_path}"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$experiment_code" \
        "$analysis_root" \
        "$relative_path" \
        "$(stat -c %s "$original_path")" \
        "$(stat -c %Y "$original_path")" \
        "$(sha256sum "$original_path" | cut -d' ' -f1)" \
        >> "$source_inventory"
done < "$file_list"

cat > "${bundle_root}/collection_receipt.tsv" <<EOF
field\tvalue
experiment\t${experiment_code}
analysis_root\t${analysis_root}
runtime_analysis_units\t${#runtime_units[@]}
coverage_summaries\t${coverage_count}
hard_vcf_giabhc_files\t${hard_vcf_count}
truvari_summaries\t${truvari_count}
smn12_json_summaries\t${smn12_count}
segdup_result_vcfs\t${segdup_count}
EOF

tar -C "$stage_root" -czf "$output_tar" "$experiment_code"
sha256sum "$output_tar"
cat "${bundle_root}/collection_receipt.tsv"
