#!/usr/bin/env python3
from daylily_ec.aws.ssm import run_shell


COMMAND = r"""
id -un
ls -1 "$HOME/miniconda3/envs" 2>/dev/null | sed -n '1,80p'
. "$HOME/miniconda3/etc/profile.d/conda.sh"
conda env list
find "$HOME/miniconda3/envs" -path '*/bin/samtools' -type f 2>/dev/null | sed -n '1,40p'
find /fsx/analysis_results -path '*/bin/samtools' -type f 2>/dev/null | sed -n '1,40p'
"""


result = run_shell(
    "i-07ec9d66e9a88e538",
    "us-west-2",
    COMMAND,
    profile="lsmc",
    timeout=180,
    comment="Find samtools environment for ONT CRAM validation",
)
print(result.stdout)
print(result.stderr)
