#!/usr/bin/env python3
"""Install the exact five-target Take222 run harness under the analysis lock."""

from __future__ import annotations

import hashlib
import shlex
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = Path("/fsx/analysis_results/preval-hiomr2/take222")
REMOTE = ROOT / "daylily-omics-analysis/take222_run_command_13.4.2.sh"
STAGE = Path("/home/ubuntu/t222run.sh")
LOCAL = Path(
    "/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/"
    "20260803T173159Z_take222_hg003_hg004_na19235_na20775_fullcov_manifests/"
    "take222_run_command_13.4.2.sh"
)
BASE = "4968edb7bd1699f50e0e5aeea14a6b12bf56568d4d48faefe2cdd5700642fd17"


def main() -> int:
    content = LOCAL.read_text(encoding="utf-8")
    target_hash = hashlib.sha256(content.encode()).hexdigest()
    verified_line = shlex.quote("harness-verified\t" + target_hash)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    env = """export DAYOA_AGENT_ID=codex-take222-release-20260803
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION=dayoa_take222_hg003_hg004_smn12_20260803
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T234000Z_dayoa_13_4_3_dyec_release_slack_ledger.md'
"""
    written = write_remote_text(
        target.instance_id,
        REGION,
        str(STAGE),
        content,
        profile=PROFILE,
        as_user="ubuntu",
    )
    print(f"staged\t{STAGE}\t{written.command_id}")
    acquire = env + f"""set -euo pipefail
test "$(sha256sum {shlex.quote(str(REMOTE))} | awk '{{print $1}}')" = {shlex.quote(BASE)}
test "$(sha256sum {shlex.quote(str(STAGE))} | awk '{{print $1}}')" = {shlex.quote(target_hash)}
test ! -e {shlex.quote(str(ROOT / '.dayoa_agent/write.lock'))}
dyec analysis lock acquire --analysis-root {shlex.quote(str(ROOT))} --operation write --intent 'Install exact Take222 five-target release-proof harness'
"""
    result = run_shell(target.instance_id, REGION, acquire, profile=PROFILE, as_user="ubuntu", timeout=300, comment="Acquire Take222 harness lock")
    print(result.stdout, end="")
    try:
        verify = env + f"""set -euo pipefail
dyec analysis guard --analysis-root {shlex.quote(str(ROOT))} --operation write --intent 'Install exact Take222 five-target release-proof harness' -- cp {shlex.quote(str(STAGE))} {shlex.quote(str(REMOTE))}
test "$(sha256sum {shlex.quote(str(REMOTE))} | awk '{{print $1}}')" = {shlex.quote(target_hash)}
printf '%s\n' {verified_line}
"""
        checked = run_shell(target.instance_id, REGION, verify, profile=PROFILE, as_user="ubuntu", timeout=300, comment="Verify Take222 harness")
        print(checked.stdout, end="")
    finally:
        release = env + f"dyec analysis lock release --analysis-root {shlex.quote(str(ROOT))}\n"
        released = run_shell(target.instance_id, REGION, release, profile=PROFILE, as_user="ubuntu", timeout=300, comment="Release Take222 harness lock")
        print(released.stdout, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
