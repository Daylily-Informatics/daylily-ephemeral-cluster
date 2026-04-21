"""Shared helpers for Daylily operator-side script entrypoints."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Iterable, Optional


class CommandError(RuntimeError):
    """Raised when an external command fails or required context is missing."""


def need_cmd(name: str) -> None:
    if subprocess.run(
        ["/bin/sh", "-lc", f"command -v {name} >/dev/null 2>&1"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode != 0:
        raise CommandError(f"Missing required command: {name}")


def aws_env(*, profile: Optional[str], region: Optional[str] = None) -> dict[str, str]:
    env = dict(os.environ)
    if profile:
        env["AWS_PROFILE"] = profile
    if region:
        env["AWS_REGION"] = region
        env.setdefault("AWS_DEFAULT_REGION", region)
    return env


def run_command(
    command: Iterable[str],
    *,
    capture_output: bool = False,
    env: Optional[dict[str, str]] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    cmd = list(command)
    try:
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=True,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        message = f"Command failed ({exc.returncode}): {' '.join(cmd)}"
        if stdout:
            message += f"\nSTDOUT:\n{stdout.strip()}"
        if stderr:
            message += f"\nSTDERR:\n{stderr.strip()}"
        raise CommandError(message) from exc
    except FileNotFoundError as exc:
        raise CommandError(f"Command not found: {cmd[0]}") from exc


def choose_from(prompt: str, options: list[str]) -> str:
    if not options:
        raise CommandError(f"No options available for: {prompt}")
    if len(options) == 1:
        return options[0]
    print(prompt)
    for idx, value in enumerate(options, start=1):
        print(f"  {idx}) {value}")
    while True:
        raw = input("Select an option: ").strip()
        if not raw.isdigit():
            print("Please enter a number.")
            continue
        selection = int(raw)
        if 1 <= selection <= len(options):
            return options[selection - 1]
        print("Selection out of range; try again.")


def resolve_region(profile: str, explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    env = aws_env(profile=profile)
    result = run_command(
        ["aws", "ec2", "describe-regions", "--output", "json"],
        capture_output=True,
        env=env,
    )
    data = json.loads(result.stdout or "{}")
    regions = sorted(entry["RegionName"] for entry in data.get("Regions", []))
    if not regions:
        raise CommandError("Unable to retrieve AWS regions. Check AWS credentials.")
    default_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if default_region and default_region in regions:
        return default_region
    return choose_from("Select AWS region:", regions)


def resolve_cluster(profile: str, region: str, explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    env = aws_env(profile=profile, region=region)
    result = run_command(
        ["pcluster", "list-clusters", "--region", region, "--output", "json"],
        capture_output=True,
        env=env,
    )
    data = json.loads(result.stdout or "{}")
    clusters = [entry.get("clusterName") for entry in data.get("clusters", [])]
    names = sorted(name for name in clusters if name)
    if not names:
        raise CommandError(f"No ParallelCluster clusters found in region {region!r}.")
    return choose_from("Select cluster:", names)
