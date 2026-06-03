#!/usr/bin/env python3
"""Read-only runtime cache inventory for dyec5128."""

from __future__ import annotations

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


PROFILE = "lsmc"
REGION = "us-west-2"
CLUSTER = "dyec5128"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = r"""
set +euo pipefail
echo INVENTORY_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo HOST=$(hostname)
echo SQUEUE
squeue -u ubuntu -o "%i|%P|%j|%u|%T|%M|%D|%R|%C|%m"
echo SHARED_CACHE_CONDA
find /fsx/references/runtime_assets/cached_envs/conda -mindepth 1 -maxdepth 1 -printf "%y\t%f\t%p\t%l\n" 2>/dev/null | sort
echo SHARED_CACHE_CONTAINERS
find /fsx/references/runtime_assets/cached_envs/containers -mindepth 1 -maxdepth 1 -printf "%y\t%f\t%p\t%l\n" 2>/dev/null | sort
echo LOCAL_CONDA_CANDIDATES
find /fsx/resources/environments/conda -mindepth 4 -maxdepth 4 \( -type d -o -type l \) -printf "%y\t%p\t%l\n" 2>/dev/null | sort
echo LOCAL_CONDA_YAMLS
find /fsx/resources/environments/conda -mindepth 4 -maxdepth 4 -type f -name "*.yaml" -printf "%p\n" 2>/dev/null | sort
echo LOCAL_CONTAINER_CANDIDATES
find /fsx/resources/environments/containers \( -type f -o -type l \) -printf "%y\t%s\t%p\t%l\n" 2>/dev/null | sort | sed -n "1,300p"
echo FSX_TMP_APPTAINER_EXISTS
for p in /fsx/tmp/apptainer_cache /fsx/tnmp/apptainer_cache; do
  if [ -e "$p" ]; then
    echo PRESENT $p
    du -sh "$p" 2>/dev/null || true
    find "$p" -maxdepth 6 -printf "%y\t%s\t%p\t%l\n" 2>/dev/null | sort | sed -n "1,300p"
  else
    echo ABSENT $p
  fi
done
echo APPTAINER_ENV_AND_CONFIG
bash -lc 'env | sort | grep -E "APPTAINER|SINGULARITY|DAYLILY_CONTAINER|DAYLILY_WORK|NXF" || true'
echo APPTAINER_USAGE_GREP
grep -R "/fsx/tmp/apptainer_cache\|/fsx/tnmp/apptainer_cache\|APPTAINER_CACHEDIR\|SINGULARITY_CACHEDIR\|singularity-prefix" -n \
  /home/ubuntu/.bashrc \
  /home/ubuntu/.profile \
  /etc/profile \
  /etc/profile.d \
  /fsx/analysis_results/dyec5128/*/daylily-omics-analysis/config/day_profiles \
  2>/dev/null | sed -n "1,300p"
exit 0
"""
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            script,
            profile=PROFILE,
            timeout=240,
            comment="Inventory DayOA runtime cache promotion candidates",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
    print(result.stdout)
    print(result.stderr)
    return int(getattr(result, "response_code", 0) or 0)


if __name__ == "__main__":
    raise SystemExit(main())

