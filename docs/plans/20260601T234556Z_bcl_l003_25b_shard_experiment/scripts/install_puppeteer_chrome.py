#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from daylily_ec.aws.ssm import (
    SsmCommandFailedError,
    resolve_headnode_instance_id,
    run_shell,
    wait_for_ssm_online,
)

PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
EXP_STAMP = os.environ.get("EXP_STAMP", "20260601T234556Z")
EXP_DIR = Path(os.environ.get("EXP_DIR", f"docs/plans/{EXP_STAMP}_bcl_l003_25b_shard_experiment"))
METADATA_DIR = EXP_DIR / "metadata"


def main() -> None:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    script = """
set -euo pipefail
source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda activate DAYOA
echo "whoami=$(id -un)"
echo "hostname=$(hostname)"
echo "node=$(command -v node)"
node --version
echo "npm=$(command -v npm)"
npm --version
echo "npx=$(command -v npx)"
echo "mmdc=$(command -v mmdc)"
mmdc --version
target=/home/ubuntu/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97
exe="$target/chrome-headless-shell-linux64/chrome-headless-shell"
if [[ -d "$target" && ! -x "$exe" ]]; then
  echo "removing incomplete puppeteer cache: $target"
  rm -rf "$target"
fi
npx puppeteer browsers install chrome-headless-shell@148.0.7778.97
test -x /home/ubuntu/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97/chrome-headless-shell-linux64/chrome-headless-shell
echo "__PUPPETEER_CACHE__"
find /home/ubuntu/.cache/puppeteer -maxdepth 4 -type f -o -type l | sed -n '1,80p'
"""
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            script,
            profile=PROFILE,
            timeout=1200,
            comment="Install Puppeteer chrome-headless-shell for DAYOA Mermaid rendering",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
        failed = True
    else:
        failed = False
    (METADATA_DIR / "puppeteer_chrome_install.stdout.txt").write_text(
        result.stdout, encoding="utf-8"
    )
    (METADATA_DIR / "puppeteer_chrome_install.stderr.txt").write_text(
        result.stderr, encoding="utf-8"
    )
    (METADATA_DIR / "puppeteer_chrome_install.ssm.json").write_text(
        json.dumps(
            {
                "command_id": result.command_id,
                "instance_id": result.instance_id,
                "status": result.status,
                "response_code": result.response_code,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
