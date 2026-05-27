#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from daylily_ec.aws.ssm import (
    SsmCommandFailedError,
    run_shell,
    wait_for_ssm_online,
)

KAHLO_URL = "https://kahlo.day.lsmc.bio/login?next=/"

COMPUTE_PROBE = r'''#!/usr/bin/env bash
set -u
url="${KAHLO_URL:?}"
node="${1:-$(hostname -s)}"
tmp="$(mktemp)"
err="$(mktemp)"
set +e
metrics="$(curl -sS -L -o "$tmp" --connect-timeout 10 --max-time 25 -w 'http_code=%{http_code} url_effective=%{url_effective} remote_ip=%{remote_ip} time_total=%{time_total} ssl_verify_result=%{ssl_verify_result}' "$url" 2>"$err")"
rc="$?"
set -e
bytes="$(wc -c < "$tmp" | tr -d ' ')"
stderr_text="$(tr '\n' ' ' < "$err" | sed 's/[|]/_/g')"
rm -f "$tmp" "$err"
printf 'PROBE|compute|%s|host=%s|rc=%s|bytes=%s|%s|stderr=%s\n' "$node" "$(hostname -s)" "$rc" "$bytes" "$metrics" "$stderr_text"
exit "$rc"
'''


def aws_env(profile: str, region: str) -> dict[str, str]:
    env = dict(os.environ)
    env["AWS_PROFILE"] = profile
    env["AWS_REGION"] = region
    env["AWS_DEFAULT_REGION"] = region
    return env


def pcluster_json(command: list[str], *, profile: str, region: str) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=aws_env(profile, region),
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown pcluster error"
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    payload = json.loads(proc.stdout or "{}")
    if not isinstance(payload, dict):
        raise RuntimeError(f"{' '.join(command)} returned non-object JSON")
    return payload


def list_cluster_inventory(profile: str, region: str) -> list[dict[str, Any]]:
    payload = pcluster_json(["pcluster", "list-clusters", "--region", region], profile=profile, region=region)
    rows: list[dict[str, Any]] = []
    for item in payload.get("clusters", []) or []:
        name = str(item.get("clusterName") or "")
        if not name:
            continue
        detail = pcluster_json(
            ["pcluster", "describe-cluster", "--cluster-name", name, "--region", region],
            profile=profile,
            region=region,
        )
        head = detail.get("headNode") or {}
        rows.append(
            {
                "cluster": name,
                "region": region,
                "cluster_status": detail.get("clusterStatus"),
                "compute_fleet_status": detail.get("computeFleetStatus"),
                "cloudformation_stack_status": detail.get("cloudFormationStackStatus"),
                "version": detail.get("version"),
                "created_at": detail.get("creationTime"),
                "updated_at": detail.get("lastUpdatedTime"),
                "headnode_instance_id": head.get("instanceId"),
                "headnode_state": head.get("state"),
                "headnode_private_ip": head.get("privateIpAddress"),
                "headnode_public_ip": head.get("publicIpAddress"),
                "headnode_instance_type": head.get("instanceType"),
            }
        )
    return rows


def list_compute_instances(cluster: str, *, profile: str, region: str) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    token: str | None = None
    while True:
        command = [
            "pcluster",
            "describe-cluster-instances",
            "--cluster-name",
            cluster,
            "--region",
            region,
            "--node-type",
            "ComputeNode",
        ]
        if token:
            command.extend(["--next-token", token])
        payload = pcluster_json(command, profile=profile, region=region)
        for item in payload.get("instances", []) or []:
            if not isinstance(item, dict):
                continue
            instances.append(
                {
                    "instance_id": item.get("instanceId"),
                    "private_ip": item.get("privateIpAddress"),
                    "instance_type": item.get("instanceType"),
                    "launch_time": item.get("launchTime"),
                    "node_type": item.get("nodeType"),
                    "queue_name": item.get("queueName"),
                    "state": item.get("state"),
                }
            )
        token = payload.get("nextToken")
        if not token:
            return instances


def build_remote_script(*, include_compute: bool) -> str:
    compute_b64 = base64.b64encode(COMPUTE_PROBE.encode("utf-8")).decode("ascii")
    url = shlex.quote(KAHLO_URL)
    compute_b64_q = shlex.quote(compute_b64)
    script = f"""set -euo pipefail
export KAHLO_URL={url}
export COMPUTE_B64={compute_b64_q}
COMPUTE_SCRIPT="$(mktemp /tmp/kahlo-compute-XXXXXX.sh)"
export COMPUTE_SCRIPT
python3 -c 'import base64, os, pathlib; pathlib.Path(os.environ["COMPUTE_SCRIPT"]).write_text(base64.b64decode(os.environ["COMPUTE_B64"]).decode("utf-8"), encoding="utf-8")'
chmod 700 "$COMPUTE_SCRIPT"

probe_headnode() {{
  tmp="$(mktemp)"
  err="$(mktemp)"
  set +e
  metrics="$(curl -sS -L -o "$tmp" --connect-timeout 10 --max-time 25 -w 'http_code=%{{http_code}} url_effective=%{{url_effective}} remote_ip=%{{remote_ip}} time_total=%{{time_total}} ssl_verify_result=%{{ssl_verify_result}}' "$KAHLO_URL" 2>"$err")"
  rc="$?"
  set -e
  bytes="$(wc -c < "$tmp" | tr -d ' ')"
  stderr_text="$(tr '\\n' ' ' < "$err" | sed 's/[|]/_/g')"
  rm -f "$tmp" "$err"
  printf 'PROBE|headnode|%s|host=%s|rc=%s|bytes=%s|%s|stderr=%s\\n' "$(hostname -s)" "$(hostname -s)" "$rc" "$bytes" "$metrics" "$stderr_text"
}}

probe_headnode
"""
    if not include_compute:
        return script + 'rm -f "$COMPUTE_SCRIPT"\n'
    return script + """
echo "SINFO_BEGIN"
if command -v sinfo >/dev/null 2>&1; then
  sinfo -Nh -o '%N|%t|%T|%C' || true
else
  echo "SINFO_MISSING"
fi
echo "SINFO_END"

echo "COMPUTE_PROBES_BEGIN"
if command -v sinfo >/dev/null 2>&1 && command -v scontrol >/dev/null 2>&1 && command -v srun >/dev/null 2>&1; then
  mapfile -t specs < <(sinfo -Nh -o '%N|%t' | awk -F'|' '$2 !~ /down|drain|fail|maint|unk/ {print $1}' | sort -u)
  if [ "${#specs[@]}" -eq 0 ]; then
    echo "COMPUTE_NO_SINFO_NODES"
  fi
  for spec in "${specs[@]}"; do
    while IFS= read -r node; do
      [ -n "$node" ] || continue
      echo "COMPUTE_BEGIN|$node"
      set +e
      srun --nodes=1 --ntasks=1 --nodelist="$node" --cpus-per-task=1 --time=00:01:00 --immediate=30 "$COMPUTE_SCRIPT" "$node" 2>&1
      srun_rc="$?"
      set -e
      echo "COMPUTE_END|$node|srun_rc=$srun_rc"
    done < <(scontrol show hostnames "$spec")
  done
else
  echo "COMPUTE_SLURM_TOOLS_MISSING"
fi
echo "COMPUTE_PROBES_END"
rm -f "$COMPUTE_SCRIPT"
"""


def parse_probe(line: str) -> dict[str, str]:
    parts = line.split("|")
    record: dict[str, str] = {"role": parts[1], "node": parts[2], "raw": line}
    for field in parts[3:]:
        if field.startswith("stderr="):
            record["stderr"] = field[len("stderr=") :]
            continue
        for token in field.split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            record[key] = value
    return record


def probe_cluster(
    cluster_row: dict[str, Any],
    *,
    profile: str,
    region: str,
    include_compute: bool,
) -> dict[str, Any]:
    cluster = str(cluster_row["cluster"])
    instance_id = str(cluster_row["headnode_instance_id"])
    result: dict[str, Any] = {
        "cluster": cluster,
        "region": region,
        "headnode_instance_id": instance_id,
        "compute_instances": list_compute_instances(cluster, profile=profile, region=region),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        wait_for_ssm_online(instance_id, region, profile=profile, timeout=120, poll_interval=5)
        command = run_shell(
            instance_id,
            region,
            build_remote_script(include_compute=include_compute),
            profile=profile,
            timeout=240,
            poll_interval=3,
            comment=f"Kahlo reachability probe for {cluster}",
        )
        stdout = command.stdout
        stderr = command.stderr
        result["ssm_command_id"] = command.command_id
        result["ssm_status"] = command.status
        result["ssm_response_code"] = command.response_code
    except SsmCommandFailedError as exc:
        stdout = exc.result.stdout
        stderr = exc.result.stderr
        result["ssm_command_id"] = exc.result.command_id
        result["ssm_status"] = exc.result.status
        result["ssm_response_code"] = exc.result.response_code
        result["ssm_error"] = str(exc)
    except Exception as exc:
        result["error"] = str(exc)
        result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return result

    result["stdout"] = stdout
    result["stderr"] = stderr
    result["probes"] = [parse_probe(line) for line in stdout.splitlines() if line.startswith("PROBE|")]
    result["sinfo"] = []
    in_sinfo = False
    for line in stdout.splitlines():
        if line == "SINFO_BEGIN":
            in_sinfo = True
            continue
        if line == "SINFO_END":
            in_sinfo = False
            continue
        if in_sinfo:
            result["sinfo"].append(line)
    result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return result


def is_running_cluster(row: dict[str, Any]) -> bool:
    return (
        row.get("cluster_status") == "CREATE_COMPLETE"
        and row.get("compute_fleet_status") == "RUNNING"
        and row.get("headnode_state") == "running"
        and bool(row.get("headnode_instance_id"))
    )


def summarize_probe(probe: dict[str, str]) -> str:
    return (
        f"{probe.get('role')} {probe.get('node')} rc={probe.get('rc')} "
        f"http={probe.get('http_code')} bytes={probe.get('bytes')} "
        f"ip={probe.get('remote_ip')}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--headnode-only", action="store_true")
    args = parser.parse_args()

    inventory = list_cluster_inventory(args.profile, args.region)
    running = [row for row in inventory if is_running_cluster(row)]
    output_path = Path(args.output)
    results: dict[str, Any] = {
        "url": KAHLO_URL,
        "profile": args.profile,
        "region": args.region,
        "inventory": inventory,
        "running_clusters": [row["cluster"] for row in running],
        "excluded_clusters": [
            row for row in inventory if not is_running_cluster(row)
        ],
        "cluster_results": [],
    }

    with ThreadPoolExecutor(max_workers=min(4, max(1, len(running)))) as pool:
        futures = [
            pool.submit(
                probe_cluster,
                row,
                profile=args.profile,
                region=args.region,
                include_compute=not args.headnode_only,
            )
            for row in running
        ]
        for future in as_completed(futures):
            cluster_result = future.result()
            results["cluster_results"].append(cluster_result)
            print(f"cluster={cluster_result['cluster']}")
            if "error" in cluster_result:
                print(f"  error={cluster_result['error']}")
            for probe in cluster_result.get("probes", []):
                print(f"  {summarize_probe(probe)}")
            sys.stdout.flush()

    results["cluster_results"].sort(key=lambda item: item["cluster"])
    output_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
