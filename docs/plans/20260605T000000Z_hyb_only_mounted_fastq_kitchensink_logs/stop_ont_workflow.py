#!/usr/bin/env python3
"""Stop the active ONT workflow controller and ONT-only Slurm jobs."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys


INSTANCE_ID = "i-05374380b57fad901"
REGION = "us-west-2"
ONT_SESSION = "hybonly_ont_kitchensink_mounted_20260606T053415Z_retry1"
ONT_SESSION_Q = shlex.quote(ONT_SESSION)


REMOTE_SCRIPT = rf"""#!/usr/bin/env bash
set -euo pipefail
echo "## before_status"
tmux has-session -t {ONT_SESSION_Q} 2>/dev/null && echo "tmux_session=present" || echo "tmux_session=absent"
echo "## active_ont_jobs_before"
squeue -h -o '%A\t%T\t%j' | awk -F '\t' '$3 ~ /ONT-4Coriells|sentmm2ont|sentdont|ont_/ {{print}}' || true
mapfile -t ont_jobs < <(squeue -h -o '%A\t%j' | awk -F '\t' '$2 ~ /ONT-4Coriells|sentmm2ont|sentdont|ont_/ {{print $1}}')
if tmux has-session -t {ONT_SESSION_Q} 2>/dev/null; then
  tmux kill-session -t {ONT_SESSION_Q}
  echo "killed_tmux_session={ONT_SESSION}"
else
  echo "killed_tmux_session=already_absent"
fi
if [ "${{#ont_jobs[@]}}" -gt 0 ]; then
  printf 'scancel_jobs=%s\n' "${{ont_jobs[*]}}"
  scancel "${{ont_jobs[@]}}"
else
  echo "scancel_jobs=none"
fi
sleep 3
echo "## after_status"
tmux has-session -t {ONT_SESSION_Q} 2>/dev/null && echo "tmux_session=present" || echo "tmux_session=absent"
echo "## active_ont_jobs_after"
squeue -h -o '%A\t%T\t%j' | awk -F '\t' '$3 ~ /ONT-4Coriells|sentmm2ont|sentdont|ont_/ {{print}}' || true
"""


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def main() -> int:
    remote_path = "/tmp/stop_ont_workflow.sh"
    write_script = (
        f"cat > {remote_path} <<'DAYOA_STOP_ONT_EOF'\n"
        f"{REMOTE_SCRIPT}\n"
        "DAYOA_STOP_ONT_EOF\n"
    )
    send = run(
        [
            "aws",
            "ssm",
            "send-command",
            "--region",
            REGION,
            "--instance-ids",
            INSTANCE_ID,
            "--document-name",
            "AWS-RunShellScript",
            "--parameters",
            json.dumps(
                {
                    "commands": [
                        write_script,
                        f"chmod 755 {remote_path}",
                        f"runuser -u ubuntu -- bash {remote_path}",
                    ]
                }
            ),
            "--query",
            "Command.CommandId",
            "--output",
            "text",
        ]
    )
    command_id = send.stdout.strip()
    print(f"COMMAND_ID={command_id}")
    wait = run(
        [
            "aws",
            "ssm",
            "wait",
            "command-executed",
            "--region",
            REGION,
            "--command-id",
            command_id,
            "--instance-id",
            INSTANCE_ID,
        ],
        check=False,
    )
    if wait.returncode != 0:
        print(wait.stderr, file=sys.stderr)
    invocation = run(
        [
            "aws",
            "ssm",
            "get-command-invocation",
            "--region",
            REGION,
            "--command-id",
            command_id,
            "--instance-id",
            INSTANCE_ID,
            "--query",
            "{Status:Status,Stdout:StandardOutputContent,Stderr:StandardErrorContent}",
            "--output",
            "json",
        ]
    )
    decoded = json.loads(invocation.stdout)
    print(json.dumps(decoded, indent=2))
    return 0 if decoded.get("Status") == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
