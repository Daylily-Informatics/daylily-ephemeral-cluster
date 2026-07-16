#!/usr/bin/env python3
"""Read-only source visibility check for the dyecX4 4NA dry-run plan."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import textwrap

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


REMOTE_SCRIPT = r"""
set -u
echo SECTION identity
whoami
hostname
date -u +%Y-%m-%dT%H:%M:%SZ
echo SECTION paths
for path in \
  /fsx/analysis_results/4_nas_ds_to_20x \
  /fsx/analysis_results/ubuntu/4_nas_ds_to_20x_realcopy \
  /fsx/run_dir_mounts/ont-4coriells-chip1 \
  /fsx/run_dir_mounts/ont-4coriells-chip2 \
  /fsx/run_dir_mounts/ont-4coriells-chip3 \
  /fsx/run_dir_mounts/ont-4coriells-chip4 \
  /fsx/control_data/ssf_derived \
  /fsx/staging/staged_external_sequencing_data
do
  if [ -e "$path" ]; then
    printf 'EXISTS\t%s\t' "$path"
    find "$path" -maxdepth 1 -mindepth 1 2>/dev/null | wc -l
  else
    printf 'MISSING\t%s\t0\n' "$path"
  fi
done
echo SECTION ilmn_fastqs
find /fsx/analysis_results/4_nas_ds_to_20x /fsx/analysis_results/ubuntu/4_nas_ds_to_20x_realcopy /fsx/control_data/ssf_derived -maxdepth 8 -type f \( -name 'NA00232-*ds20x*_R1_001.fastq.gz' -o -name 'NA09677-*ds20x*_R1_001.fastq.gz' -o -name 'NA03986-*ds20x*_R1_001.fastq.gz' -o -name 'NA05164-*ds20x*_R1_001.fastq.gz' \) -print 2>/dev/null | sort
echo SECTION ont_fastqs
for chip in 1 2 3 4; do
  for barcode in 18 19 20 21; do
    dir="/fsx/run_dir_mounts/ont-4coriells-chip${chip}/fastq_pass/barcode${barcode}"
    if [ -d "$dir" ]; then
      count=$(find "$dir" -maxdepth 1 -type f -name '*.fastq.gz' 2>/dev/null | wc -l)
      printf 'chip%s\tbarcode%s\t%s\t%s\n' "$chip" "$barcode" "$count" "$dir"
    else
      printf 'chip%s\tbarcode%s\t0\tMISSING:%s\n' "$chip" "$barcode" "$dir"
    fi
  done
done
echo SECTION dra
aws fsx describe-data-repository-associations --region us-west-2 --filters Name=file-system-id,Values=fs-04960a3a07c091cf3 --query 'Associations[].{Id:AssociationId,Lifecycle:Lifecycle,Path:FileSystemPath,S3:DataRepositoryPath,Name:Tags[?Key==`Name`].Value|[0],Purpose:Tags[?Key==`lsmc:purpose`].Value|[0]}' --output json
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--cluster", default="dyecX4")
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = resolve_headnode_instance_id(
        args.cluster,
        args.region,
        profile=args.profile,
    )
    result = run_shell(
        target.instance_id,
        args.region,
        textwrap.dedent(REMOTE_SCRIPT).strip(),
        profile=args.profile,
        as_user="ubuntu",
        timeout=900,
        comment="dyecX4 read-only 4NA source visibility check",
    )
    (args.output_dir / "4na_source_check.result.json").write_text(
        json.dumps(
            {
                "cluster": args.cluster,
                "profile": args.profile,
                "region": args.region,
                "instance_id": result.instance_id,
                "command_id": result.command_id,
                "status": result.status,
                "response_code": result.response_code,
            },
            indent=2,
        )
        + "\n"
    )
    (args.output_dir / "4na_source_check.stdout.txt").write_text(result.stdout)
    (args.output_dir / "4na_source_check.stderr.txt").write_text(result.stderr)
    print(json.dumps({"status": result.status, "response_code": result.response_code}))
    return int(result.response_code or 0)


if __name__ == "__main__":
    sys.exit(main())
