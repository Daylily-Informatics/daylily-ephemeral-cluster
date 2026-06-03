from __future__ import annotations

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


CLUSTER = "dyec5128"
REGION = "us-west-2"
PROFILE = "lsmc"


REMOTE_SCRIPT = r"""
set -euo pipefail

printf 'CLEANUP_START\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'FSX_BEFORE\n'
df -h /fsx

printf 'REMOVE_YAML_WITHOUT_ENV\n'
find /fsx/resources/environments/conda -mindepth 3 -maxdepth 3 -type f -name '*_.yaml' 2>/dev/null \
  | sort \
  | while read -r yaml; do
      env_dir="${yaml%.yaml}"
      if [ ! -d "${env_dir}" ]; then
        printf 'DELETE\t%s\t%s\n' "$(stat -c %s "${yaml}")" "${yaml}"
        rm -f -- "${yaml}"
      fi
    done

printf 'REMOVE_INCOMPLETE_CONDA_DIRS\n'
find /fsx/resources/environments/conda -mindepth 3 -maxdepth 3 -type d -name '*_' 2>/dev/null \
  | sort \
  | while read -r env_dir; do
      if [ ! -f "${env_dir}/conda-meta/history" ]; then
        du -sh "${env_dir}"
        rm -rf -- "${env_dir}"
      fi
    done

printf 'REMOVE_BROKEN_CONTAINER_LINKS\n'
find /fsx/resources/environments/containers -xtype l -print -delete 2>/dev/null || true

printf 'REMOVE_TINY_REAL_CONTAINER_FILES\n'
find /fsx/resources/environments/containers -type f \( -name '*.simg' -o -name '*.sif' \) -size -1M \
  -printf 'DELETE\t%s\t%p\n' \
  -delete 2>/dev/null || true

printf 'REMAINING_INCOMPLETE\n'
find /fsx/resources/environments/conda -mindepth 3 -maxdepth 3 -type d -name '*_' 2>/dev/null \
  | while read -r env_dir; do
      [ -f "${env_dir}/conda-meta/history" ] || echo "${env_dir}"
    done
find /fsx/resources/environments/conda -mindepth 3 -maxdepth 3 -type f -name '*_.yaml' 2>/dev/null \
  | while read -r yaml; do
      [ -d "${yaml%.yaml}" ] || echo "${yaml}"
    done

printf 'FSX_AFTER\n'
df -h /fsx
printf 'CLEANUP_DONE\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
"""


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            REMOTE_SCRIPT,
            profile=PROFILE,
            timeout=600,
            comment="clean incomplete runtime env artifacts before catalog relaunch",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return getattr(result, "returncode", getattr(result, "rc", 0))


if __name__ == "__main__":
    raise SystemExit(main())
