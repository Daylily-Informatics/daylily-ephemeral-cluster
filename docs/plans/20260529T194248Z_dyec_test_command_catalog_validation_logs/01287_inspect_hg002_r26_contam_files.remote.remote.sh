#!/usr/bin/env bash
set -euo pipefail

session="ccv20260529r26_illumina_hg002_kitchensink_multiqc"
repo="/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis"
sample="JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ"
base="$repo/results/day/hg38/$sample/align/sent/dmd/snv/sentd/contam_identity"

echo "## read_haps files"
find "$base/read_haps" -type f -printf '%s %p\n' 2>/dev/null | sort || true
echo "## read_haps output"
cat "$base/read_haps/$sample.sent.dmd.sentd.read_haps.txt" 2>/dev/null | head -n 80 || true
echo "## read_haps log"
cat "$base/read_haps/logs/$sample.sent.dmd.sentd.read_haps.log" 2>/dev/null | head -n 80 || true

echo "## haplocheck files"
find "$base/haplocheck" -type f -printf '%s %p\n' 2>/dev/null | sort || true
echo "## haplocheck log"
cat "$base/haplocheck/vcf/logs/$sample.sent.dmd.sentd.haplocheck.vcf.log" 2>/dev/null | head -n 120 || true
