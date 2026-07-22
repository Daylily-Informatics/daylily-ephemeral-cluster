"""Shared DAY-EC headnode readiness validation."""

from __future__ import annotations

import shlex
from typing import Optional

from daylily_ec.aws.ssm import SsmCommandResult, run_shell


DEFAULT_HEADNODE_REPO_NAME = "daylily-ephemeral-cluster"
SENTIEON_LICENSE_ENDPOINT = "license.sentieon.lsmc.bio:8990"
REQUIRED_ROLE_FILES = (
    "/fsx/references/runtime_assets/cached_envs/apptainer_1.4.5_amd64.deb",
    "/fsx/references/runtime_assets/tool_specific_resources/womtool_87.jar",
)
REQUIRED_ROLE_DIRECTORIES = (
    "/fsx/references/genomic_data",
    "/fsx/references/runtime_assets/cached_envs/conda",
)
REQUIRED_WRITABLE_CACHE_DIRECTORY_TEMPLATES = (
    "/fsx/resources/environments/apptainer/cache/net",
    "/fsx/resources/environments/conda/{remote_user}/{hostname}",
    "/fsx/resources/environments/containers/{remote_user}/{hostname}",
    "/fsx/resources/environments/nextflow",
)
REQUIRED_HEADNODE_WORK_DIRECTORY_TEMPLATES = (
    "/fsx/work/{remote_user}",
    "/fsx/work/{remote_user}/containers",
    "/fsx/work/{remote_user}/nextflow",
    "/fsx/work/{remote_user}/sarek",
    "/fsx/run_dir_mounts",
)


def build_headnode_readiness_script(
    repo_name: str = DEFAULT_HEADNODE_REPO_NAME,
    *,
    remote_user: str = "ubuntu",
) -> str:
    """Return the remote script that proves the headnode is ready for workflows."""

    repo_name_q = shlex.quote(repo_name)
    remote_user_q = shlex.quote(remote_user)
    sentieon_license_endpoint_q = shlex.quote(SENTIEON_LICENSE_ENDPOINT)
    file_checks = "\n".join(f"test -s {path}" for path in REQUIRED_ROLE_FILES)
    dir_checks = "\n".join(f"test -d {path}" for path in REQUIRED_ROLE_DIRECTORIES)
    writable_cache_checks = "\n".join(
        f"test -d {template.format(hostname='$(hostname)', remote_user=remote_user)}"
        for template in REQUIRED_WRITABLE_CACHE_DIRECTORY_TEMPLATES
    )
    headnode_work_checks = "\n".join(
        f"test -d {template.format(remote_user=remote_user)}"
        for template in REQUIRED_HEADNODE_WORK_DIRECTORY_TEMPLATES
    )
    return f"""
set -euo pipefail
repo_dir="$HOME/projects"/{repo_name_q}
readiness_script="$(mktemp /tmp/daylily-headnode-readiness-XXXXXX.sh)"
trap 'rm -f "$readiness_script"' EXIT
cat >"$readiness_script" <<'DAYLILY_HEADNODE_READINESS'
set -euo pipefail
test "$(id -un)" = {remote_user_q}
test "${{DAYLILY_EC_HEADNODE_BOOTSTRAPPED:-0}}" = 1
test "${{CONDA_DEFAULT_ENV:-}}" = DAY-EC
test "${{SENTIEON_LICENSE:-}}" = {sentieon_license_endpoint_q}
command -v daylily-ec >/dev/null 2>&1
command -v day-clone >/dev/null 2>&1
stty -a 2>/dev/null | grep -Eq '(^|[[:space:];])-ixon([[:space:];]|$)'
df -P /fsx >/dev/null
{file_checks}
{dir_checks}
{writable_cache_checks}
{headnode_work_checks}
test -r /etc/profile.d/daylily-runtime-cache.sh
grep -Fq 'DAYLILY_CONTAINER_CACHE' /etc/profile.d/daylily-runtime-cache.sh
grep -Fq 'DAYLILY_APPTAINER_CACHE' /etc/profile.d/daylily-runtime-cache.sh
grep -Fq 'DAYLILY_NEXTFLOW_SEED_CACHE' /etc/profile.d/daylily-runtime-cache.sh
grep -Fq 'NXF_SINGULARITY_CACHEDIR' /etc/profile.d/daylily-runtime-cache.sh
test ! -e /fsx/runtime_assets
test -L /fsx/data
test "$(readlink -f /fsx/data)" = /fsx/references
day-clone --list >/dev/null
day-clone --check-auth --repository daylily-omics-analysis >/dev/null
echo "DAY-EC headnode readiness validated"
DAYLILY_HEADNODE_READINESS
chmod 700 "$readiness_script"
cd "$repo_dir"
script -q -c "bash -il '$readiness_script'" /dev/null
"""


def validate_headnode_readiness(
    instance_id: str,
    region: str,
    *,
    profile: Optional[str] = None,
    timeout: Optional[int] = 120,
    comment: str = "Validate DAY-EC headnode readiness",
    repo_name: str = DEFAULT_HEADNODE_REPO_NAME,
    remote_user: str = "ubuntu",
) -> SsmCommandResult:
    """Run the shared readiness validation on a headnode via SSM."""

    return run_shell(
        instance_id,
        region,
        build_headnode_readiness_script(repo_name=repo_name, remote_user=remote_user),
        profile=profile,
        as_user=remote_user,
        timeout=timeout,
        comment=comment,
    )
