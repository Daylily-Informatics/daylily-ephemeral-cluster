from __future__ import annotations

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


CLUSTER = "dyec5128"
REGION = "us-west-2"
PROFILE = "lsmc"


REMOTE_SCRIPT = r"""
set -euo pipefail

printf 'ENV_TOP\n'
find /fsx/resources/environments -maxdepth 4 -mindepth 1 \
  -printf '%y\t%s\t%p\t%l\n' 2>/dev/null \
  | sort \
  | sed -n '1,700p'

printf 'NON_LINKS_SUMMARY\n'
find /fsx/resources/environments -mindepth 1 ! -type l \
  -printf '%y\t%s\t%p\n' 2>/dev/null \
  | awk -F '\t' '{n[$1]++; bytes[$1]+=$2} END {for(k in n) print k, n[k], bytes[k]}' \
  | sort

printf 'FAILED_OR_INCOMPLETE_CONDA\n'
find /fsx/resources/environments/conda -mindepth 3 -maxdepth 3 -type d -name '*_' 2>/dev/null \
  | sort \
  | while read -r d; do
      if [ ! -f "${d}/conda-meta/history" ]; then
        du -sh "${d}"
      fi
    done

printf 'YAML_WITHOUT_ENV\n'
find /fsx/resources/environments/conda -mindepth 3 -maxdepth 3 -type f -name '*_.yaml' 2>/dev/null \
  | sort \
  | while read -r y; do
      d="${y%.yaml}"
      [ -d "${d}" ] || printf '%s\t%s\n' "$(stat -c %s "${y}")" "${y}"
    done

printf 'NEXTFLOW_TREE\n'
if [ -d /fsx/resources/environments/nextflow ]; then
  find /fsx/resources/environments/nextflow -maxdepth 5 \
    -printf '%y\t%s\t%p\t%l\n' \
    | sort \
    | sed -n '1,700p'
else
  echo ABSENT
fi

printf 'DOT_AND_CONFIG_CACHE_REFERENCES\n'
for root in \
  /fsx/analysis_results/dyec5128/init/daylily-omics-analysis \
  /fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_02_illumina_snv_alignstats/daylily-omics-analysis \
  /fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_03_illumina_snv_alignstats_relatedness_vep_multiqc/daylily-omics-analysis \
  /fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_04_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis \
  /fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_05_ultima_snv_alignstats/daylily-omics-analysis; do
  [ -d "${root}" ] || continue
  echo "ROOT=${root}"
  find "${root}" -maxdepth 4 \( -name '.*' -o -name '*config*' -o -name '*activate*' -o -name 'dyoainit' \) -type f 2>/dev/null \
    | sort \
    | xargs -r grep -nE '/fsx/(resources/environments|tmp/apptainer_cache|work/.*/containers|work/.*/nextflow)|APPTAINER_CACHEDIR|SINGULARITY_CACHEDIR|NXF_|conda-prefix|singularity-prefix' \
    | sed -n '1,240p' \
    || true
done

printf 'FSX_DF\n'
df -h /fsx
"""


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            REMOTE_SCRIPT,
            profile=PROFILE,
            timeout=900,
            comment="inventory nonlink runtime env cache and dot config references",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return getattr(result, "returncode", getattr(result, "rc", 0))


if __name__ == "__main__":
    raise SystemExit(main())
