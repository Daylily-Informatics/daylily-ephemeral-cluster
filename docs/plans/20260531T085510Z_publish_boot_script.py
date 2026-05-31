#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "config/day_cluster/post_install_ubuntu_combined.sh"
LOG_DIR = ROOT / "docs/plans/20260531T085510Z_boot_script_reference_publish_logs"
KEY = "runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh"
BACKUP_KEY = (
    "runtime_assets/cluster_boot_config/backups/"
    "post_install_ubuntu_combined.sh.pre-80pct-shm-20260531T085510Z"
)


@dataclass(frozen=True)
class Target:
    profile: str
    region: str
    bucket: str


TARGETS = [
    Target("lsmc", "us-west-2", "lsmc-dayoa-references-usw2"),
    Target("daylily", "us-west-2", "daylily-dayoa-references-usw2"),
    Target("lsmc", "ap-south-1", "lsmc-dayoa-omics-analysis-ap-south-1"),
    Target("lsmc", "eu-central-1", "lsmc-dayoa-omics-analysis-eu-central-1"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(argv: list[str], *, label: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, text=True, capture_output=True, check=False)
    (LOG_DIR / f"{label}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (LOG_DIR / f"{label}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    record = {
        "label": label,
        "argv": argv,
        "returncode": result.returncode,
        "stdout_path": str(LOG_DIR / f"{label}.stdout.txt"),
        "stderr_path": str(LOG_DIR / f"{label}.stderr.txt"),
    }
    with (LOG_DIR / "commands.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return result


def aws(target: Target, args: list[str], *, label: str) -> subprocess.CompletedProcess[str]:
    return run(
        ["aws", *args, "--profile", target.profile, "--region", target.region],
        label=label,
    )


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    local_hash = sha256(SOURCE)
    results: list[dict[str, str | int | bool]] = []

    bash_check = run(["bash", "-n", str(SOURCE)], label="000_bash_n")
    if bash_check.returncode != 0:
        print(f"bash -n failed for {SOURCE}", file=sys.stderr)
        return bash_check.returncode

    for index, target in enumerate(TARGETS, start=1):
        prefix = f"{index:03d}_{target.bucket}"
        item: dict[str, str | int | bool] = {
            "bucket": target.bucket,
            "profile": target.profile,
            "region": target.region,
            "key": KEY,
            "backup_key": BACKUP_KEY,
            "local_sha256": local_hash,
        }

        head = aws(
            target,
            ["s3api", "head-object", "--bucket", target.bucket, "--key", KEY],
            label=f"{prefix}_head_before",
        )
        item["head_before_rc"] = head.returncode

        if head.returncode == 0:
            backup = aws(
                target,
                [
                    "s3api",
                    "copy-object",
                    "--bucket",
                    target.bucket,
                    "--key",
                    BACKUP_KEY,
                    "--copy-source",
                    f"{target.bucket}/{KEY}",
                ],
                label=f"{prefix}_backup",
            )
            item["backup_rc"] = backup.returncode
            if backup.returncode != 0:
                item["status"] = "BACKUP_FAILED"
                results.append(item)
                continue
        else:
            item["backup_rc"] = -1
            item["backup_note"] = "source object missing; upload attempted without backup"

        upload = aws(
            target,
            [
                "s3",
                "cp",
                str(SOURCE),
                f"s3://{target.bucket}/{KEY}",
                "--content-type",
                "text/x-shellscript",
            ],
            label=f"{prefix}_upload",
        )
        item["upload_rc"] = upload.returncode
        if upload.returncode != 0:
            item["status"] = "UPLOAD_FAILED"
            results.append(item)
            continue

        readback = LOG_DIR / f"{target.bucket}.post_install_ubuntu_combined.sh"
        download = aws(
            target,
            ["s3", "cp", f"s3://{target.bucket}/{KEY}", str(readback)],
            label=f"{prefix}_download",
        )
        item["download_rc"] = download.returncode
        if download.returncode != 0:
            item["status"] = "DOWNLOAD_FAILED"
            results.append(item)
            continue

        readback_hash = sha256(readback)
        item["readback_path"] = str(readback)
        item["readback_sha256"] = readback_hash
        item["hash_match"] = readback_hash == local_hash
        item["status"] = "SUCCESS" if readback_hash == local_hash else "HASH_MISMATCH"

        backup_head = aws(
            target,
            ["s3api", "head-object", "--bucket", target.bucket, "--key", BACKUP_KEY],
            label=f"{prefix}_head_backup",
        )
        item["head_backup_rc"] = backup_head.returncode
        results.append(item)

    summary_path = LOG_DIR / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0 if all(item.get("status") == "SUCCESS" for item in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
