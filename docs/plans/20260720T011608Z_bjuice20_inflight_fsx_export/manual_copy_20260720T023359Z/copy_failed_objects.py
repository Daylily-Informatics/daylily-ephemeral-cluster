#!/usr/bin/env python3
"""Repair the exact 36 failed FSx exports with validated S3-side copies."""

from __future__ import annotations

import base64
import csv
import gzip
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError

from daylily_ec.aws.ssm import run_shell, write_remote_text


PROFILE = "lsmc"
REGION = "us-west-2"
INSTANCE_ID = "i-09b566e847c16233b"
BUCKET = "lsmc-dayoa-analysis-results-usw2"
DEST_KEY_ROOT = (
    "validation/inflight_pr53_recovery_20260720T011608Z/"
    "ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/"
)
SOURCE_KEY_ROOT = (
    "validation/pre_13.0.11_8_g1d44044_20260719T214703Z/"
    "ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/"
)
FAILURE_KEY = (
    DEST_KEY_ROOT
    + "_daylily_monitor/fsx-export/20260720T014320Z/export-report/"
    + "task-002d8e282dc07dff6/failures.csv"
)
RUN_ID = "manual-copy-20260720T023359Z"
RECEIPT_KEY_ROOT = DEST_KEY_ROOT + f"_daylily_monitor/fsx-export/{RUN_ID}/"
REMOTE_FAILURES = f"/home/ubuntu/{RUN_ID}-failures.csv"
REMOTE_MAPPING = f"/home/ubuntu/{RUN_ID}-hardlink-mapping.tsv"
REMOTE_SCRIPT = f"/home/ubuntu/{RUN_ID}-build-hardlink-mapping.bash"
LOCAL_MAPPING_SCRIPT = Path(__file__).with_name("build_hardlink_mapping.bash")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def missing_object(client, key: str) -> bool:
    try:
        client.head_object(Bucket=BUCKET, Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return True
        raise
    return False


def main() -> int:
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    s3 = session.client("s3")

    failure_bytes = s3.get_object(Bucket=BUCKET, Key=FAILURE_KEY)["Body"].read()
    failure_text = failure_bytes.decode("utf-8")
    failure_rows = list(csv.reader(io.StringIO(failure_text)))
    if len(failure_rows) != 36:
        raise RuntimeError(f"expected 36 failure rows, found {len(failure_rows)}")
    if len({row[0] for row in failure_rows}) != 36:
        raise RuntimeError("failure report contains duplicate paths")

    write_remote_text(
        INSTANCE_ID,
        REGION,
        REMOTE_FAILURES,
        failure_text,
        profile=PROFILE,
        as_user="ubuntu",
    )
    write_remote_text(
        INSTANCE_ID,
        REGION,
        REMOTE_SCRIPT,
        LOCAL_MAPPING_SCRIPT.read_text(encoding="utf-8"),
        profile=PROFILE,
        as_user="ubuntu",
    )
    command = "\n".join(
        [
            "set -euo pipefail",
            f"chmod 700 {REMOTE_SCRIPT}",
            f"bash {REMOTE_SCRIPT} {REMOTE_FAILURES} {REMOTE_MAPPING}",
        ]
    )
    mapping_result = run_shell(
        INSTANCE_ID,
        REGION,
        command,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=900,
    )
    marker = "MAPPING_GZIP_BASE64="
    encoded = next(
        (line[len(marker) :] for line in mapping_result.stdout.splitlines() if line.startswith(marker)),
        None,
    )
    if not encoded:
        raise RuntimeError("headnode mapping result did not contain the expected marker")
    mapping_text = gzip.decompress(base64.b64decode(encoded)).decode("utf-8")
    mappings = list(csv.DictReader(io.StringIO(mapping_text), delimiter="\t"))
    if len(mappings) != 36:
        raise RuntimeError(f"expected 36 hard-link mappings, found {len(mappings)}")

    expected_destinations = {
        row[0].split("bjuiceprevalanalysis-complete/", 1)[1] for row in failure_rows
    }
    actual_destinations = {row["destination_relative_path"] for row in mappings}
    if actual_destinations != expected_destinations:
        raise RuntimeError("hard-link mapping destinations do not match the failure report")

    preflight: list[dict[str, object]] = []
    for row in mappings:
        source_key = SOURCE_KEY_ROOT + row["source_relative_path"]
        destination_key = DEST_KEY_ROOT + row["destination_relative_path"]
        source_head = s3.head_object(
            Bucket=BUCKET,
            Key=source_key,
            ChecksumMode="ENABLED",
        )
        expected_bytes = int(row["bytes"])
        if int(source_head["ContentLength"]) != expected_bytes:
            raise RuntimeError(f"source S3 size mismatch: s3://{BUCKET}/{source_key}")
        if not missing_object(s3, destination_key):
            raise RuntimeError(f"refusing to overwrite existing destination: s3://{BUCKET}/{destination_key}")
        preflight.append(
            {
                **row,
                "source_key": source_key,
                "destination_key": destination_key,
                "source_etag": str(source_head["ETag"]),
                "source_checksum_sha256": source_head.get("ChecksumSHA256", ""),
            }
        )

    transfer_config = TransferConfig(
        multipart_threshold=64 * 1024 * 1024,
        multipart_chunksize=256 * 1024 * 1024,
        max_concurrency=10,
        use_threads=True,
    )
    receipts: list[dict[str, object]] = []
    for index, item in enumerate(preflight, start=1):
        started = utc_now()
        source_key = str(item["source_key"])
        destination_key = str(item["destination_key"])
        expected_bytes = int(item["bytes"])
        print(f"[{index}/36] s3://{BUCKET}/{source_key} -> s3://{BUCKET}/{destination_key}", flush=True)
        status = "COPY_FAILED"
        error = ""
        destination_head: dict[str, object] = {}
        try:
            s3.copy(
                {"Bucket": BUCKET, "Key": source_key},
                BUCKET,
                destination_key,
                ExtraArgs={
                    "CopySourceIfMatch": str(item["source_etag"]),
                    "ChecksumAlgorithm": "SHA256",
                },
                Config=transfer_config,
            )
            destination_head = s3.head_object(
                Bucket=BUCKET,
                Key=destination_key,
                ChecksumMode="ENABLED",
            )
            if int(destination_head["ContentLength"]) != expected_bytes:
                raise RuntimeError(
                    f"destination size {destination_head['ContentLength']} != {expected_bytes}"
                )
            if not destination_head.get("ChecksumSHA256"):
                raise RuntimeError("destination does not expose ChecksumSHA256")
            status = "COPIED_AND_VALIDATED"
        except Exception as exc:  # preserve all per-object failures in the receipt
            error = f"{type(exc).__name__}: {exc}"

        receipts.append(
            {
                "source_s3_uri": f"s3://{BUCKET}/{source_key}",
                "destination_s3_uri": f"s3://{BUCKET}/{destination_key}",
                "bytes": expected_bytes,
                "inode": item["inode"],
                "link_count": item["link_count"],
                "hsm_state": item["hsm_state"],
                "source_etag": item["source_etag"],
                "source_checksum_sha256": item["source_checksum_sha256"],
                "destination_etag": str(destination_head.get("ETag", "")).strip('"'),
                "destination_checksum_sha256": destination_head.get("ChecksumSHA256", ""),
                "started_utc": started,
                "completed_utc": utc_now(),
                "status": status,
                "error": error,
            }
        )

    fields = list(receipts[0])
    receipt_buffer = io.StringIO()
    writer = csv.DictWriter(receipt_buffer, fieldnames=fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(receipts)
    receipt_bytes = receipt_buffer.getvalue().encode("utf-8")
    summary = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "generated_at": utc_now(),
        "source_failure_report": f"s3://{BUCKET}/{FAILURE_KEY}",
        "source_export_prefix": f"s3://{BUCKET}/{SOURCE_KEY_ROOT}",
        "mapped_count": len(mappings),
        "copied_and_validated": sum(row["status"] == "COPIED_AND_VALIDATED" for row in receipts),
        "failed": sum(row["status"] != "COPIED_AND_VALIDATED" for row in receipts),
        "receipt_s3_uri": f"s3://{BUCKET}/{RECEIPT_KEY_ROOT}manual_copy_receipt.tsv",
    }
    s3.put_object(
        Bucket=BUCKET,
        Key=RECEIPT_KEY_ROOT + "hardlink_mapping.tsv",
        Body=mapping_text.encode("utf-8"),
        ChecksumAlgorithm="SHA256",
        ContentType="text/tab-separated-values",
    )
    s3.put_object(
        Bucket=BUCKET,
        Key=RECEIPT_KEY_ROOT + "manual_copy_receipt.tsv",
        Body=receipt_bytes,
        ChecksumAlgorithm="SHA256",
        ContentType="text/tab-separated-values",
    )
    s3.put_object(
        Bucket=BUCKET,
        Key=RECEIPT_KEY_ROOT + "summary.json",
        Body=(json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        ChecksumAlgorithm="SHA256",
        ContentType="application/json",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["failed"] == 0 and summary["copied_and_validated"] == 36 else 1


if __name__ == "__main__":
    raise SystemExit(main())
