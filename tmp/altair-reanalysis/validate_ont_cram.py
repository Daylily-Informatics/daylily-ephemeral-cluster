#!/usr/bin/env python3
from daylily_ec.aws.ssm import run_shell


COMMAND = r"""
CRAM=/fsx/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ont/HG003_30x.cleaned.cram
REF=/fsx/data/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.fasta
SAMTOOLS=/fsx/resources/environments/conda/ubuntu/ip-10-0-0-87/20e0c533f7572779d5d259e1c29bfd69_/bin/samtools
. "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate DAYOA
id -un
command -v htsfile || true
"$SAMTOOLS" --version | sed -n '1,2p'
test -s "$CRAM"
test -s "$CRAM.crai"
test -s "$REF"
test -s "$REF.fai"
"$SAMTOOLS" quickcheck -v "$CRAM"
htsfile "$CRAM" || true
"$SAMTOOLS" view -H "$CRAM" | awk 'BEGIN{sq=0;rg=0;pg=0} /^@SQ/{sq++} /^@RG/{rg++} /^@PG/{pg++} END{print "SQ=" sq, "RG=" rg, "PG=" pg}'
diff -u <(cut -f1,2 "$REF.fai") <("$SAMTOOLS" view -H "$CRAM" | awk -F'\t' '$1=="@SQ"{sn="";ln="";for(i=2;i<=NF;i++){if($i~/^SN:/)sn=substr($i,4); if($i~/^LN:/)ln=substr($i,4)}; print sn "\t" ln}') | sed -n '1,80p'
"$SAMTOOLS" view -@ 4 -T "$REF" "$CRAM" chr1:1-1000000 >/dev/null
"$SAMTOOLS" view -@ 4 -T "$REF" "$CRAM" chr20:10000000-10100000 | awk 'NR<=1000{n++} END{print "chr20_sample_records=" n}'
"$SAMTOOLS" idxstats "$CRAM" | sed -n '1,8p'
"""


result = run_shell(
    "i-07ec9d66e9a88e538",
    "us-west-2",
    COMMAND,
    profile="lsmc",
    timeout=300,
    comment="Validate HG003 30x ONT CRAM for Altair hybrid",
)
print(result.stdout)
print(result.stderr)
