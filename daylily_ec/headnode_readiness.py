"""Shared DAY-EC headnode readiness validation."""

from __future__ import annotations

import shlex
from typing import Optional

from daylily_ec.aws.ssm import SsmCommandResult, run_shell


DEFAULT_HEADNODE_REPO_NAME = "daylily-ephemeral-cluster"
REQUIRED_REFERENCE_FILES = (
    "/fsx/data/cached_envs/apptainer_1.4.5_amd64.deb",
    "/fsx/data/tool_specific_resources/cromwell_87.jar",
    "/fsx/data/tool_specific_resources/womtool_87.jar",
)
REQUIRED_REFERENCE_DIRECTORIES = ("/fsx/data/cached_envs/conda",)


def build_headnode_readiness_script(repo_name: str = DEFAULT_HEADNODE_REPO_NAME) -> str:
    """Return the remote script that proves the headnode is ready for workflows."""

    repo_name_q = shlex.quote(repo_name)
    file_checks = "\n".join(f"test -s {path}" for path in REQUIRED_REFERENCE_FILES)
    dir_checks = "\n".join(f"test -d {path}" for path in REQUIRED_REFERENCE_DIRECTORIES)
    return f"""
set -euo pipefail
repo_dir="$HOME/projects"/{repo_name_q}
readiness_script="$(mktemp /tmp/daylily-headnode-readiness-XXXXXX.sh)"
trap 'rm -f "$readiness_script"' EXIT
cat >"$readiness_script" <<'DAYLILY_HEADNODE_READINESS'
set -euo pipefail
test "$(id -un)" = ubuntu
test "${{DAYLILY_EC_HEADNODE_BOOTSTRAPPED:-0}}" = 1
test "${{CONDA_DEFAULT_ENV:-}}" = DAY-EC
command -v daylily-ec >/dev/null 2>&1
command -v day-clone >/dev/null 2>&1
stty -a 2>/dev/null | grep -Eq '(^|[[:space:];])-ixon([[:space:];]|$)'
df -P /fsx >/dev/null
test -d /fsx/data
{file_checks}
{dir_checks}
day-clone --list >/dev/null
echo "DAY-EC headnode readiness validated"
DAYLILY_HEADNODE_READINESS
chmod 700 "$readiness_script"
cd "$repo_dir"
script -q -c "bash -lc '$readiness_script'" /dev/null
"""


def validate_headnode_readiness(
    instance_id: str,
    region: str,
    *,
    profile: Optional[str] = None,
    timeout: Optional[int] = 120,
    comment: str = "Validate DAY-EC headnode readiness",
    repo_name: str = DEFAULT_HEADNODE_REPO_NAME,
) -> SsmCommandResult:
    """Run the shared readiness validation on a headnode via SSM as ubuntu."""

    return run_shell(
        instance_id,
        region,
        build_headnode_readiness_script(repo_name=repo_name),
        profile=profile,
        as_user="ubuntu",
        timeout=timeout,
        comment=comment,
    )
