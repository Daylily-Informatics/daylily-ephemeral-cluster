#!/usr/bin/env bash
set -euo pipefail

session="ccv20260529r26_illumina_hg002_kitchensink_multiqc"
repo="/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis"
main_log="$repo/.snakemake/log/2026-05-30T065050.641034.snakemake.log"
sample="JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ"

echo "## goleft range"
sed -n '1372,1400p' "$main_log" | cut -c1-500
echo "## goleft log"
tail -n 40 "$repo/results/day/hg38/$sample/align/sent/na/alignqc/goleft/logs/goleft.log" 2>/dev/null | cut -c1-500 || true
tail -n 40 "$repo/results/day/hg38/$sample/align/sent/dmd/alignqc/goleft/logs/goleft.log" 2>/dev/null | cut -c1-500 || true

echo "## fastqc seqfu logs"
tail -n 30 "$repo/results/day/hg38/$sample/logs/fastqc/$sample.fastqc.log" 2>/dev/null | cut -c1-500 || true
tail -n 30 "$repo/results/day/hg38/$sample/seqqc/seqfu/$sample.seqfu.log" 2>/dev/null | cut -c1-500 || true

echo "## contam ranges"
sed -n '3648,3674p' "$main_log" | cut -c1-500
sed -n '3734,3770p' "$main_log" | cut -c1-500
echo "## contam logs"
tail -n 40 "$repo/results/day/hg38/$sample/align/sent/dmd/snv/sentd/contam_identity/read_haps/logs/$sample.sent.dmd.sentd.read_haps.log" 2>/dev/null | cut -c1-500 || true
tail -n 40 "$repo/results/day/hg38/$sample/align/sent/dmd/snv/sentd/contam_identity/haplocheck/logs/$sample.sent.dmd.sentd.haplocheck.log" 2>/dev/null | cut -c1-500 || true

echo "## vep ranges"
sed -n '4864,4894p' "$main_log" | cut -c1-500
sed -n '4918,4948p' "$main_log" | cut -c1-500
echo "## vep logs"
find "$repo/results/day/hg38" -path '*vep*' -type f \( -name '*.log' -o -name '*.err' -o -name '*.out' \) -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 8 | awk '{print $2}' | while read -r log; do
  echo "--- $log"
  tail -n 25 "$log" | cut -c1-500
done
