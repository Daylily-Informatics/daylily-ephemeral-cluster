#!/usr/bin/env python3
import json
import shlex
import subprocess
import time


PROFILE = "lsmc"
REGION = "us-west-2"
INSTANCE_ID = "i-05374380b57fad901"
SESSION = "hybonly_ilmn_kitchensink_mounted_20260606T053415Z"


REMOTE_CODE = r'''
import json
import pathlib
import re
import subprocess

session = "hybonly_ilmn_kitchensink_mounted_20260606T053415Z"
repo = pathlib.Path(f"/fsx/analysis_results/ubuntu/{session}/daylily-omics-analysis")
logs = sorted((repo / ".snakemake" / "log").glob("*.log"), key=lambda p: p.stat().st_mtime)
payload = {"session": session, "repo": str(repo), "logs_found": len(logs)}
if logs:
    latest = logs[-1]
    lines = latest.read_text(errors="replace").splitlines()
    progress = []
    finished = 0
    submitted = 0
    errors = []
    for line_no, line in enumerate(lines, start=1):
        if "Finished job" in line:
            finished += 1
        if "Submitted job" in line:
            submitted += 1
        if (
            "Error in rule" in line
            or "Failed jobs" in line
            or "Exiting because" in line
            or "WorkflowError" in line
        ):
            errors.append({"line": line_no, "text": line[:500]})
        match = re.search(r"(\d+) of (\d+) steps \(([^)]+)\) done", line)
        if match:
            progress.append(
                {
                    "line": line_no,
                    "done": int(match.group(1)),
                    "total": int(match.group(2)),
                    "pct": match.group(3),
                    "text": line,
                }
            )
    payload.update(
        {
            "latest_log": str(latest),
            "latest_log_mtime": latest.stat().st_mtime,
            "line_count": len(lines),
            "finished_lines": finished,
            "submitted_lines": submitted,
            "latest_progress": progress[-1] if progress else None,
            "max_progress": max(progress, key=lambda row: row["done"]) if progress else None,
            "progress_tail": progress[-10:],
            "error_marker_count": len(errors),
            "error_markers_tail": errors[-10:],
        }
    )

queue = subprocess.run(
    ["bash", "-lc", "squeue -h -o '%A\t%T\t%M\t%j'"],
    text=True,
    capture_output=True,
)
jobs = []
for line in queue.stdout.splitlines():
    if "ILMN-NOVASEQ" not in line:
        continue
    parts = line.split("\t", 3)
    if len(parts) == 4:
        jobs.append({"job_id": parts[0], "state": parts[1], "time": parts[2], "name": parts[3]})
payload["active_ilmn_jobs"] = jobs
payload["active_ilmn_job_count"] = len(jobs)
payload["squeue_returncode"] = queue.returncode
payload["squeue_stderr"] = queue.stderr.strip()
print(json.dumps(payload, indent=2, sort_keys=True))
'''


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=True)


def main() -> int:
    command = "runuser -u ubuntu -- python3 -c " + shlex.quote(REMOTE_CODE)
    send = run(
        [
            "aws",
            "ssm",
            "send-command",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--instance-ids",
            INSTANCE_ID,
            "--document-name",
            "AWS-RunShellScript",
            "--parameters",
            json.dumps({"commands": [command]}),
            "--query",
            "Command.CommandId",
            "--output",
            "text",
        ]
    )
    command_id = send.stdout.strip()
    print(f"COMMAND_ID={command_id}")
    deadline = time.time() + 180
    while time.time() < deadline:
        invocation = run(
            [
                "aws",
                "ssm",
                "get-command-invocation",
                "--profile",
                PROFILE,
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
        payload = json.loads(invocation.stdout)
        if payload["Status"] in {"Success", "Failed", "Cancelled", "TimedOut"}:
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if payload["Status"] == "Success" else 1
        time.sleep(3)
    raise SystemExit(f"Timed out waiting for SSM command {command_id}")


if __name__ == "__main__":
    raise SystemExit(main())
