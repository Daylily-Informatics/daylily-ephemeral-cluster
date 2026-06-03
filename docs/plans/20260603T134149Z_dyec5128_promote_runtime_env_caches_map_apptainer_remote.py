from __future__ import annotations

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


CLUSTER = "dyec5128"
REGION = "us-west-2"
PROFILE = "lsmc"


REMOTE_SCRIPT = r"""
set -euo pipefail
export PATH=/usr/local/bin:/usr/bin:/bin:$PATH

printf 'HOST=%s\n' "$(hostname)"

printf 'SNAKEMAKE_SINGULARITY_PREFIX_CONTENTS\n'
find /fsx/analysis_results/dyec5128 -path '*/.snakemake/singularity/*' \( -type f -o -type l \) \
  -printf '%y\t%s\t%p\t%l\n' 2>/dev/null \
  | sort \
  | sed -n '1,400p'

printf 'WORKFLOW_CONTAINER_STRING_SEARCH\n'
grep -RIl \
  -e 'quay.io/biocontainers/fastqc' \
  -e 'quay.io/bioconda/base-glibc-busybox-bash' \
  -e 'mambaorg/micromamba' \
  -e 'fastqc:0.12.1' \
  /fsx/analysis_results/dyec5128/*/daylily-omics-analysis 2>/dev/null \
  | sed -n '1,200p' \
  | while read -r file; do
      echo "FILE=${file}"
      grep -n \
        -e 'quay.io/biocontainers/fastqc' \
        -e 'quay.io/bioconda/base-glibc-busybox-bash' \
        -e 'mambaorg/micromamba' \
        -e 'fastqc:0.12.1' \
        "${file}" \
        | sed -n '1,80p'
    done

printf 'LOG_CONTAINER_STRING_SEARCH\n'
grep -RIn \
  -e 'quay.io/biocontainers/fastqc' \
  -e 'quay.io/bioconda/base-glibc-busybox-bash' \
  -e 'mambaorg/micromamba' \
  -e 'Pulling singularity image' \
  -e 'Activating singularity image' \
  -e 'Creating singularity image' \
  /fsx/analysis_results/dyec5128/*/daylily-omics-analysis/.snakemake/log \
  /fsx/analysis_results/dyec5128/*/daylily-omics-analysis/logs \
  2>/dev/null \
  | sed -n '1,400p'

printf 'SINGULARITY_PREFIX_INSPECT\n'
find /fsx/analysis_results/dyec5128 -path '*/.snakemake/singularity/*' -type f -print 2>/dev/null \
  | sort \
  | sed -n '1,100p' \
  | while read -r image; do
      echo "IMAGE=${image}"
      stat -c 'size_bytes=%s' "${image}" || true
      apptainer inspect --json "${image}" 2>/dev/null | python3 -c 'import sys; txt=sys.stdin.read(); print(txt[:1200] if txt else "NO_INSPECT_JSON")' || true
    done

printf 'NET_LABEL_SUMMARY\n'
for f in /fsx/tmp/apptainer_cache/cache/net/*; do
  [ -f "${f}" ] || continue
  echo "NET_FILE=${f}"
  apptainer inspect --json "${f}" 2>/dev/null \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); labels=d.get("data",{}).get("attributes",{}).get("labels",{}); print(labels.get("org.label-schema.usage.singularity.deffile.from","<missing>")); print(labels.get("org.opencontainers.image.source","<missing>")); print(labels.get("org.opencontainers.image.title","<missing>"))' \
    || true
done
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
            comment="map apptainer net cache objects to workflow metadata",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return getattr(result, "returncode", getattr(result, "rc", 0))


if __name__ == "__main__":
    raise SystemExit(main())
