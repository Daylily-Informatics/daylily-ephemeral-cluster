#!/usr/bin/env bash
set -euo pipefail

JOBS=(17351 16939 18791 18676 18677 18334)
REPO="/fsx/analysis_results/hyb-only/hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z/daylily-omics-analysis"

cd "${REPO}"

echo "__SQUEUE__"
squeue -j "$(IFS=,; echo "${JOBS[*]}")" -o "%.18i %.12P %.80j %.10T %.12M %.6D %R"

echo "__JOB_DETAILS__"
for job in "${JOBS[@]}"; do
    echo "===JOB:${job}==="
    detail="/tmp/dayoa_job_${job}.txt"
    scontrol show job -dd "${job}" > "${detail}" || true
    tr ' ' '\n' < "${detail}" | grep -E '^(JobId=|JobName=|JobState=|RunTime=|TimeLimit=|SubmitTime=|StartTime=|BatchHost=|NodeList=|NumNodes=|NumCPUs=|ReqMem=|TRES=|WorkDir=|StdOut=|StdErr=|Command=|Reason=)' || true
    stdout="$(tr ' ' '\n' < "${detail}" | awk -F= '$1=="StdOut"{print $2; exit}')"
    stderr="$(tr ' ' '\n' < "${detail}" | awk -F= '$1=="StdErr"{print $2; exit}')"
    for path in "${stdout}" "${stderr}"; do
        if [[ -n "${path}" && "${path}" != "(null)" ]]; then
            echo "---PATH:${path}---"
            if [[ -e "${path}" ]]; then
                stat -c 'mtime=%y size=%s path=%n' "${path}" || true
                tail -40 "${path}" || true
            else
                echo "missing"
            fi
        fi
    done
done

echo "__LATEST_SNAKEMAKE_LOG__"
latest_log="$(find .snakemake/log -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1{print $2}')"
echo "${latest_log:-NONE}"
if [[ -n "${latest_log:-}" && -e "${latest_log}" ]]; then
    stat -c 'mtime=%y size=%s path=%n' "${latest_log}" || true
    tail -80 "${latest_log}" || true
fi

echo "__RECENT_SENTDHIOMR_FILES_30MIN__"
find results/day/hg38_broad -type f -path '*sentdhiomr*' -mmin -30 -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -120 || true

echo "__RECENT_BENCHMARK_FILES_30MIN__"
find results/day/hg38_broad -type f -name '*.bench.tsv' -mmin -30 -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -80 || true

echo "__NODE_DETAILS__"
for node in i192bigmem-dy-all-7 i192bigmem-dy-all-12 i192mem-dy-all-4 i192mem-dy-all-5 i192mem-dy-all-7 i192mem-dy-all-3; do
    echo "===NODE:${node}==="
    scontrol show node -o "${node}" || true
done
