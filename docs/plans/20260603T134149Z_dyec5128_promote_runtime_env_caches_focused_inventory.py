from __future__ import annotations

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


CLUSTER = "dyec5128"
REGION = "us-west-2"
PROFILE = "lsmc"


REMOTE_SCRIPT = r"""
set -euo pipefail

printf 'COMPLETE_CONDA_TOPLEVEL\n'
find /fsx/resources/environments/conda -mindepth 3 -maxdepth 3 -type d -name '*_' 2>/dev/null \
  | sort \
  | while read -r d; do
      if [ -f "${d}/conda-meta/history" ]; then
        name="$(basename "${d}")"
        size="$(du -sb "${d}" | awk '{print $1}')"
        y="${d}.yaml"
        ys=missing
        [ -f "${y}" ] && ys="$(stat -c %s "${y}")"
        printf '%s\t%s\t%s\t%s\n' "${name}" "${size}" "${ys}" "${d}"
      fi
    done

printf 'INCOMPLETE_CONDA_TOPLEVEL\n'
find /fsx/resources/environments/conda -mindepth 3 -maxdepth 3 -type d -name '*_' 2>/dev/null \
  | sort \
  | while read -r d; do
      if [ ! -f "${d}/conda-meta/history" ]; then
        du -sb "${d}"
      fi
    done

printf 'YAML_WITHOUT_ENV\n'
find /fsx/resources/environments/conda -mindepth 3 -maxdepth 3 -type f -name '*_.yaml' 2>/dev/null \
  | sort \
  | while read -r y; do
      d="${y%.yaml}"
      [ -d "${d}" ] || printf '%s\t%s\n' "$(stat -c %s "${y}")" "${y}"
    done

printf 'REAL_CONTAINER_IMAGES\n'
find /fsx/resources/environments/containers -type f \( -name '*.simg' -o -name '*.sif' \) ! -xtype l \
  -printf '%s\t%p\n' 2>/dev/null \
  | sort

printf 'NEXTFLOW_TOPLEVEL\n'
if [ -d /fsx/resources/environments/nextflow ]; then
  find /fsx/resources/environments/nextflow -mindepth 1 -maxdepth 1 ! -type l \
    -printf '%y\t%s\t%p\n' \
    | sort
  du -sh /fsx/resources/environments/nextflow/* 2>/dev/null || true
else
  echo ABSENT
fi

printf 'DOT_CONFIG_REFS\n'
for p in \
  /home/ubuntu/.bashrc \
  /home/ubuntu/.bash_profile \
  /home/ubuntu/.profile \
  /etc/profile.d/*.sh \
  /fsx/analysis_results/dyec5128/init/daylily-omics-analysis/dyoainit \
  /fsx/analysis_results/dyec5128/init/daylily-omics-analysis/config/day_profiles/slurm/config.yaml; do
  [ -f "${p}" ] || continue
  echo "FILE=${p}"
  grep -nE '/fsx/(resources/environments|tmp/apptainer_cache|work/.*/containers|work/.*/nextflow)|APPTAINER_CACHEDIR|SINGULARITY_CACHEDIR|NXF_|conda-prefix|singularity-prefix' "${p}" || true
done

printf 'APPTAINER_TMP_DOT_REFS\n'
grep -RIn '/fsx/tmp/apptainer_cache\|APPTAINER_CACHEDIR\|SINGULARITY_CACHEDIR' \
  /home/ubuntu \
  /fsx/analysis_results/dyec5128/init/daylily-omics-analysis \
  2>/dev/null \
  | sed -n '1,240p' \
  || true

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
            comment="focused runtime cache inventory",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return getattr(result, "returncode", getattr(result, "rc", 0))


if __name__ == "__main__":
    raise SystemExit(main())
