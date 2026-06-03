from __future__ import annotations

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


CLUSTER = "dyec5128"
REGION = "us-west-2"
PROFILE = "lsmc"


REMOTE_SCRIPT = r"""
set -euo pipefail
export PATH=/usr/local/bin:/usr/bin:/bin:$PATH

printf 'HOST=%s\n' "$(hostname)"

printf 'AWS_IDENTITY\n'
aws sts get-caller-identity --output json || true

printf 'DEST_CONDA_EXISTING\n'
aws s3 ls s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/conda/ | sed -n '1,120p' || true

printf 'DEST_CONTAINERS_EXISTING\n'
aws s3 ls s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/containers/ | sed -n '1,120p' || true

printf 'APPTAINER_VERSION\n'
(apptainer --version || singularity --version || true)

printf 'APPTAINER_CACHE_LIST\n'
APPTAINER_CACHEDIR=/fsx/tmp/apptainer_cache \
SINGULARITY_CACHEDIR=/fsx/tmp/apptainer_cache \
  apptainer cache list -v || true

printf 'NET_OBJECT_INSPECTION\n'
for root in /fsx/tmp/apptainer_cache /fsx/tnmp/apptainer_cache; do
  echo "ROOT=${root}"
  if [ ! -d "${root}/cache/net" ]; then
    echo "ABSENT"
    continue
  fi
  for f in "${root}"/cache/net/*; do
    [ -f "${f}" ] || continue
    echo "FILE=${f}"
    stat -c 'size_bytes=%s' "${f}"
    file -b "${f}" || true
    echo 'INSPECT_JSON_HEAD'
    if apptainer inspect --json "${f}" >/tmp/dyec_inspect.json 2>/tmp/dyec_inspect.err; then
      python3 - <<'PY'
from pathlib import Path
text = Path("/tmp/dyec_inspect.json").read_text(errors="replace")
print(text[:1800])
PY
    elif singularity inspect --json "${f}" >/tmp/dyec_inspect.json 2>/tmp/dyec_inspect.err; then
      python3 - <<'PY'
from pathlib import Path
text = Path("/tmp/dyec_inspect.json").read_text(errors="replace")
print(text[:1800])
PY
    else
      echo 'NO_INSPECT_JSON'
      cat /tmp/dyec_inspect.err || true
    fi
    echo 'STRINGS_HINTS'
    strings "${f}" \
      | grep -Eio '(docker|oras|library|quay|ghcr|depot|biocontainers|nfcore|broadinstitute|staphb|multiqc|sentieon|bclconvert|bwa|samtools|gatk|vep|ultima|ont|pacbio|roche)[^[:space:]"'"'"'<>]{0,160}' \
      | sort -u \
      | sed -n '1,120p' \
      || true
  done
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
            comment="inspect runtime cache s3 and apptainer net objects",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
