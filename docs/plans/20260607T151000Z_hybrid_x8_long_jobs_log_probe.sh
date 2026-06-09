#!/usr/bin/env bash
set -euo pipefail

JOBS=(17351 16939 18791 18676 18677 18334)
REPO="/fsx/analysis_results/hyb-only/hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z/daylily-omics-analysis"
OUT="/tmp/hybrid_x8_long_jobs_log_probe_$(date -u +%Y%m%dT%H%M%SZ).txt"
S3_OUT="s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/config_snapshots/20260607T124257Z/hybrid_x8_fullvars_5017/$(basename "${OUT}")"

exec > >(tee "${OUT}") 2>&1

cd "${REPO}"

echo "__SQUEUE__"
squeue -j "$(IFS=,; echo "${JOBS[*]}")" -o "%.18i %.12P %.120j %.10T %.12M %.6D %R"

echo "__RUNNING_JOBS_DETAIL_AND_LOGS__"
for job in "${JOBS[@]}"; do
    echo "===JOB:${job}==="
    detail="/tmp/dayoa_job_${job}.txt"
    scontrol show job -dd "${job}" > "${detail}" || true
    cat "${detail}"
    command_path="$(tr ' ' '\n' < "${detail}" | awk -F= '$1=="Command"{print $2; exit}')"
    if [[ -n "${command_path}" && -e "${command_path}" ]]; then
        echo "---SNAKEJOB:${command_path}---"
        stat -c 'mtime=%y size=%s path=%n' "${command_path}" || true
        echo "---RULE_LOG_PATHS---"
        grep -Eo 'results/day/[^ ]+sentdhiomr/log/[^ ;]+' "${command_path}" | sort -u || true
        echo "---RULE_LOG_TAILS---"
        while IFS= read -r log_path; do
            [[ -z "${log_path}" ]] && continue
            echo "+++LOG:${log_path}+++"
            if [[ -e "${log_path}" ]]; then
                stat -c 'mtime=%y size=%s path=%n' "${log_path}" || true
                tail -80 "${log_path}" || true
            else
                echo "missing"
            fi
        done < <(grep -Eo 'results/day/[^ ]+sentdhiomr/log/[^ ;]+' "${command_path}" | sort -u || true)
        echo "---OUTPUT_PATHS_STAT---"
        while IFS= read -r out_path; do
            [[ -z "${out_path}" ]] && continue
            out_path="${out_path%;}"
            echo "+++OUT:${out_path}+++"
            if [[ -e "${out_path}" ]]; then
                stat -c 'mtime=%y size=%s path=%n' "${out_path}" || true
            else
                parent="$(dirname "${out_path}")"
                echo "missing; parent=${parent}"
                [[ -d "${parent}" ]] && find "${parent}" -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' | sort | tail -30 || true
            fi
        done < <(grep -Eo 'results/day/[^ ]+sentdhiomr/[^ >;|]+' "${command_path}" | grep -E '/vcfs/|/tmp/' | sort -u || true)
    else
        echo "snakejob command script missing: ${command_path}"
    fi
done

echo "__NA03986_SENTDHIOMR_LOGS_MTIME__"
find results/day/hg38_broad -type f -path '*NA03986*sentdhiomr/log/*' -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -120 || true

echo "__NA03986_SENTDHIOMR_TMP_MTIME__"
find results/day/hg38_broad -type f -path '*NA03986*sentdhiomr/vcfs/*/tmp/*' -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -160 || true

aws s3 cp "${OUT}" "${S3_OUT}"
echo "__S3_OUT__ ${S3_OUT}"
