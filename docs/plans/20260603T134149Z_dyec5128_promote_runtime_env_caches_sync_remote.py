from __future__ import annotations

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


CLUSTER = "dyec5128"
REGION = "us-west-2"
PROFILE = "lsmc"


REMOTE_SCRIPT = r"""
set -euo pipefail

DEST_ROOT="s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs"

printf 'SYNC_START\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'DEST_ROOT\t%s\n' "${DEST_ROOT}"

printf 'SYNC_CONDA_ENVS\n'
find /fsx/resources/environments/conda -mindepth 3 -maxdepth 3 -type d -name '*_' 2>/dev/null \
  | sort \
  | while read -r env_dir; do
      name="$(basename "${env_dir}")"
      yaml="${env_dir}.yaml"
      if [ ! -f "${env_dir}/conda-meta/history" ]; then
        printf 'SKIP_INCOMPLETE_ENV\t%s\n' "${env_dir}"
        continue
      fi
      size_bytes="$(du -sb "${env_dir}" | awk '{print $1}')"
      printf 'SYNC_ENV\t%s\t%s\t%s\n' "${name}" "${size_bytes}" "${env_dir}"
      aws s3 sync --only-show-errors "${env_dir}/" "${DEST_ROOT}/conda/${name}/"
      if [ -f "${yaml}" ]; then
        printf 'COPY_YAML\t%s\t%s\n' "${name}" "${yaml}"
        aws s3 cp --only-show-errors "${yaml}" "${DEST_ROOT}/conda/${name}.yaml"
      else
        printf 'MISSING_YAML\t%s\t%s\n' "${name}" "${yaml}"
      fi
    done

printf 'SYNC_REAL_CONTAINER_IMAGES\n'
find /fsx/resources/environments/containers -type f \( -name '*.simg' -o -name '*.sif' \) ! -xtype l -print 2>/dev/null \
  | sort \
  | while read -r image; do
      name="$(basename "${image}")"
      size_bytes="$(stat -c %s "${image}")"
      printf 'COPY_CONTAINER\t%s\t%s\t%s\n' "${name}" "${size_bytes}" "${image}"
      aws s3 cp --only-show-errors "${image}" "${DEST_ROOT}/containers/${name}"
    done

printf 'SYNC_NEXTFLOW\n'
if [ -d /fsx/resources/environments/nextflow ]; then
  du -sh /fsx/resources/environments/nextflow
  aws s3 sync --only-show-errors /fsx/resources/environments/nextflow/ "${DEST_ROOT}/nextflow/"
else
  printf 'NEXTFLOW_ABSENT\n'
fi

printf 'SYNC_APPTAINER_NET_CACHE\n'
for root in /fsx/tmp/apptainer_cache /fsx/tnmp/apptainer_cache; do
  if [ ! -d "${root}/cache/net" ]; then
    printf 'NET_CACHE_ABSENT\t%s\n' "${root}"
    continue
  fi
  find "${root}/cache/net" -type f -printf '%s\t%p\n' | sort
  aws s3 sync --only-show-errors "${root}/cache/net/" "${DEST_ROOT}/apptainer_cache/cache/net/"
done

printf 'S3_VERIFY_COUNTS\n'
for prefix in conda containers nextflow apptainer_cache/cache/net; do
  count="$(aws s3 ls --recursive "${DEST_ROOT}/${prefix}/" | wc -l | tr -d ' ')"
  bytes="$(aws s3 ls --recursive "${DEST_ROOT}/${prefix}/" | awk '{sum += $3} END {print sum+0}')"
  printf '%s\t%s\t%s\n' "${prefix}" "${count}" "${bytes}"
done

printf 'SYNC_DONE\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
"""


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            REMOTE_SCRIPT,
            profile=PROFILE,
            timeout=14400,
            comment="sync built runtime env caches from fsx to reference s3",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return getattr(result, "returncode", getattr(result, "rc", 0))


if __name__ == "__main__":
    raise SystemExit(main())
