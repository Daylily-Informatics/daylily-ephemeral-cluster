#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell, wait_for_ssm_online

KAHLO_URL = "https://kahlo.day.lsmc.bio/login?next=/"


def build_probe_script() -> str:
    url = shlex.quote(KAHLO_URL)
    return f"""set -u
export KAHLO_URL={url}
tmp="$(mktemp)"
err="$(mktemp)"
set +e
metrics="$(curl -sS -L -o "$tmp" --connect-timeout 10 --max-time 25 -w 'http_code=%{{http_code}} url_effective=%{{url_effective}} remote_ip=%{{remote_ip}} time_total=%{{time_total}} ssl_verify_result=%{{ssl_verify_result}}' "$KAHLO_URL" 2>"$err")"
rc="$?"
set -e
bytes="$(wc -c < "$tmp" | tr -d ' ')"
stderr_text="$(tr '\\n' ' ' < "$err" | sed 's/[|]/_/g')"
rm -f "$tmp" "$err"
printf 'PROBE|compute|%s|host=%s|rc=%s|bytes=%s|%s|stderr=%s\\n' "$(hostname -s)" "$(hostname -s)" "$rc" "$bytes" "$metrics" "$stderr_text"
exit 0
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


def probe_instance(
    *,
    cluster: str,
    instance: dict[str, Any],
    profile: str,
    region: str,
) -> dict[str, Any]:
    instance_id = str(instance["instance_id"])
    result: dict[str, Any] = {
        "cluster": cluster,
        "region": region,
        "instance": instance,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        wait_for_ssm_online(instance_id, region, profile=profile, timeout=60, poll_interval=5)
        command = run_shell(
            instance_id,
            region,
            build_probe_script(),
            profile=profile,
            timeout=60,
            poll_interval=3,
            comment=f"Kahlo compute reachability probe for {cluster} {instance_id}",
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
    result["probes"] = [
        parse_probe(line) for line in stdout.splitlines() if line.startswith("PROBE|")
    ]
    result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return result


def summarize_probe(result: dict[str, Any]) -> str:
    ident = result["instance"]["instance_id"]
    queue = result["instance"].get("queue_name") or ""
    if "error" in result:
        return f"{result['cluster']} {queue} {ident} error={result['error']}"
    probes = result.get("probes", [])
    if not probes:
        return f"{result['cluster']} {queue} {ident} no_probe stdout={result.get('stdout', '').strip()!r}"
    probe = probes[0]
    return (
        f"{result['cluster']} {queue} {ident} rc={probe.get('rc')} "
        f"http={probe.get('http_code')} bytes={probe.get('bytes')} "
        f"ip={probe.get('remote_ip')} stderr={probe.get('stderr', '').strip()}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    tasks: list[tuple[str, dict[str, Any]]] = []
    for cluster_result in source.get("cluster_results", []):
        cluster = str(cluster_result["cluster"])
        for instance in cluster_result.get("compute_instances", []):
            if instance.get("state") == "running":
                tasks.append((cluster, instance))

    results: dict[str, Any] = {
        "url": KAHLO_URL,
        "profile": args.profile,
        "region": args.region,
        "source": args.input,
        "compute_probe_results": [],
    }
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(tasks)))) as pool:
        futures = [
            pool.submit(
                probe_instance,
                cluster=cluster,
                instance=instance,
                profile=args.profile,
                region=args.region,
            )
            for cluster, instance in tasks
        ]
        for future in as_completed(futures):
            item = future.result()
            results["compute_probe_results"].append(item)
            print(summarize_probe(item))

    results["compute_probe_results"].sort(
        key=lambda item: (
            item["cluster"],
            str(item["instance"].get("queue_name")),
            item["instance"]["instance_id"],
        )
    )
    Path(args.output).write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
