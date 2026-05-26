#!/usr/bin/env python3
from daylily_ec.aws.ssm import run_shell


COMMAND = r"""
CRAM=/fsx/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ont/HG003_30x.cleaned.cram
REF=/fsx/data/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.fasta
SAMTOOLS=/fsx/resources/environments/conda/ubuntu/ip-10-0-0-87/20e0c533f7572779d5d259e1c29bfd69_/bin/samtools
tmp_ref=$(mktemp)
tmp_cram=$(mktemp)
cut -f1,2 "$REF.fai" > "$tmp_ref"
"$SAMTOOLS" view -H "$CRAM" | awk -F'\t' '$1=="@SQ"{sn="";ln="";for(i=2;i<=NF;i++){if($i~/^SN:/)sn=substr($i,4); if($i~/^LN:/)ln=substr($i,4)}; print sn "\t" ln}' > "$tmp_cram"
awk 'NR==FNR{ref[$1]=$2; next} {total++; if(!($1 in ref)){missing++; print "missing_from_ref\t"$0} else if(ref[$1] != $2){mismatch++; print "length_mismatch\t"$1"\t"$2"\t"ref[$1]} else {matched++}} END{print "cram_sq_count=" total; print "matched_sq=" matched+0; print "missing_from_ref=" missing+0; print "length_mismatch=" mismatch+0}' "$tmp_ref" "$tmp_cram"
"$SAMTOOLS" view -@ 4 -T "$REF" "$CRAM" chr1:100000000-101000000 | awk 'NR<=1000{n++} END{print "chr1_100mb_sample_records=" n}'
rm -f "$tmp_ref" "$tmp_cram"
"""


result = run_shell(
    "i-07ec9d66e9a88e538",
    "us-west-2",
    COMMAND,
    profile="lsmc",
    timeout=300,
    comment="Check HG003 30x ONT CRAM SQ subset compatibility",
)
print(result.stdout)
print(result.stderr)
