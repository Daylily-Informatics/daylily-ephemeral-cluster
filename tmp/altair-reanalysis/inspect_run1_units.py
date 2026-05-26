#!/usr/bin/env python3
from daylily_ec.aws.ssm import run_shell


COMMAND = r"""
for path in \
  /fsx/data/staged_sample_data/remote_stage_20260520T072438Z/20260520T072438Z_units.tsv \
  /fsx/analysis_results/johnm/re-ana-20260512_LH01106_0006_A23K3H2LT4/daylily-omics-analysis/config/units.tsv
do
  echo "PATH=$path"
  awk -F'\t' 'NR<=5{print NR, $2, length($9), length($10), substr($9,1,60), substr($10,1,60)}' "$path"
done
"""

result = run_shell(
    "i-07ec9d66e9a88e538",
    "us-west-2",
    COMMAND,
    profile="lsmc",
    timeout=120,
    comment="Inspect failed Run1 units TSV with awk",
)
print(result.stdout)
print(result.stderr)
