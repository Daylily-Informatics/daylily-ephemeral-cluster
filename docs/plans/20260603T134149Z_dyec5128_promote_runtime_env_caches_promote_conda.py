from __future__ import annotations

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


CLUSTER = "dyec5128"
REGION = "us-west-2"
PROFILE = "lsmc"


REMOTE_SCRIPT = r"""
set -euo pipefail

DEST="s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/conda"
SRC_ROOT="/fsx/resources/environments/conda"
PROMOTED=0
SKIPPED=0

printf 'PROMOTE_CONDA_START %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'DEST %s\n' "${DEST}"

find "${SRC_ROOT}" -mindepth 3 -maxdepth 3 -type d -name '*_' -print \
  | sort \
  | while read -r env_dir; do
      name="$(basename "${env_dir}")"
      yaml="${env_dir}.yaml"
      if [ ! -f "${env_dir}/conda-meta/history" ]; then
        printf 'SKIP_INCOMPLETE\t%s\n' "${env_dir}"
        SKIPPED=$((SKIPPED + 1))
        continue
      fi
      size_bytes="$(du -sb "${env_dir}" | awk '{print $1}')"
      if aws s3 ls "${DEST}/${name}/" >/dev/null 2>&1; then
        printf 'SKIP_ENV_EXISTS\t%s\t%s\t%s\n' "${name}" "${size_bytes}" "${env_dir}"
      else
        printf 'SYNC_ENV\t%s\t%s\t%s\n' "${name}" "${size_bytes}" "${env_dir}"
        aws s3 sync --only-show-errors "${env_dir}/" "${DEST}/${name}/"
        PROMOTED=$((PROMOTED + 1))
      fi
      if [ -f "${yaml}" ]; then
        if aws s3 ls "${DEST}/${name}.yaml" >/dev/null 2>&1; then
          printf 'SKIP_YAML_EXISTS\t%s\t%s\n' "${name}" "${yaml}"
        else
          printf 'COPY_YAML\t%s\t%s\n' "${name}" "${yaml}"
          aws s3 cp --only-show-errors "${yaml}" "${DEST}/${name}.yaml"
        fi
      else
        printf 'MISSING_YAML\t%s\t%s\n' "${name}" "${yaml}"
      fi
    done

printf 'PROMOTE_CONDA_DONE %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'DEST_POST_LIST\n'
aws s3 ls "${DEST}/" | sed -n '1,240p'
"""


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            REMOTE_SCRIPT,
            profile=PROFILE,
            timeout=7200,
            comment="promote complete conda env caches to reference s3",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return getattr(result, "returncode", getattr(result, "rc", 0))


if __name__ == "__main__":
    raise SystemExit(main())
