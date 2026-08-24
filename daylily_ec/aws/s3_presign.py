"""Read-only presigning for one exact S3 object."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

MAX_PRESIGN_EXPIRATION_SECONDS = 7 * 24 * 60 * 60


def parse_s3_object_uri(value: str) -> tuple[str, str, str]:
    """Return ``(bucket, key, canonical_uri)`` for one exact S3 object."""

    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError("--s3-uri must be an exact s3://bucket/key object URI")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("--s3-uri must not contain params, a query string, or a fragment")
    if parsed.username or parsed.password or parsed.port is not None:
        raise ValueError("--s3-uri must contain only an S3 bucket and object key")
    key = parsed.path.lstrip("/")
    if not key or key.endswith("/"):
        raise ValueError("--s3-uri must identify one object, not a bucket or prefix")
    canonical_uri = f"s3://{parsed.netloc}/{key}"
    return parsed.netloc, key, canonical_uri


def _isoformat_utc(value: Any) -> str | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def presign_get_object(
    *,
    s3_client: Any,
    s3_uri: str,
    expires_in_seconds: int,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Verify and presign one S3 ``GetObject`` request."""

    if isinstance(expires_in_seconds, bool) or not isinstance(expires_in_seconds, int):
        raise TypeError("--expires-in-seconds must be an integer")
    if not 1 <= expires_in_seconds <= MAX_PRESIGN_EXPIRATION_SECONDS:
        raise ValueError(
            "--expires-in-seconds must be between 1 and " f"{MAX_PRESIGN_EXPIRATION_SECONDS}"
        )

    bucket, key, canonical_uri = parse_s3_object_uri(s3_uri)
    head = s3_client.head_object(Bucket=bucket, Key=key)
    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in_seconds,
        HttpMethod="GET",
    )
    if not isinstance(url, str) or not url.strip():
        raise RuntimeError("S3 client returned an empty presigned URL")

    issued_at = generated_at or datetime.now(timezone.utc)
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)
    issued_at = issued_at.astimezone(timezone.utc)
    expires_at = issued_at + timedelta(seconds=expires_in_seconds)

    return {
        "schema_version": "dyec.aws_s3_presign.v1",
        "ok": True,
        "operation": "presign_get_object",
        "s3_uri": canonical_uri,
        "bucket": bucket,
        "key": key,
        "expires_in_seconds": expires_in_seconds,
        "generated_at": issued_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "object": {
            "content_length": head.get("ContentLength"),
            "content_type": head.get("ContentType"),
            "etag": head.get("ETag"),
            "last_modified": _isoformat_utc(head.get("LastModified")),
            "version_id": head.get("VersionId"),
        },
        "url": url,
    }
