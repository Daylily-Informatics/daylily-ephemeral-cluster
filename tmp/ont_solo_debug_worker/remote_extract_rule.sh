set -euo pipefail
REPO=/fsx/analysis_results/johnm/hg003a_ont_snv_alignstats_1018_bigmem/daylily-omics-analysis
nl -ba "${REPO}/workflow/rules/sent_snv_ont.smk" | sed -n '70,190p'
