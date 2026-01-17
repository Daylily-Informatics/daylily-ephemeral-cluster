"""DynamoDB-backed storage for re-usable stage_samples.tsv manifests.

Manifests are customer-scoped and store the TSV payload (gzip+base64) alongside
lightweight metadata for listing and selection.

Design goals:
- Efficient list by customer_id (partition key)
- Stable lookup by (customer_id, manifest_id)
- Store TSV content in DynamoDB (subject to 400KB item limit)
"""

from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import gzip
import hashlib
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key


LOGGER = logging.getLogger("daylily.manifest_registry")


class ManifestTooLargeError(ValueError):
    """Raised when the TSV content cannot fit into a DynamoDB item."""


@dataclass(frozen=True)
class SavedManifest:
    manifest_id: str
    customer_id: str
    name: Optional[str]
    description: Optional[str]
    created_at: str
    sample_count: int
    tsv_sha256: str
    tsv_gzip_b64: str

    def to_metadata_dict(self) -> Dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "customer_id": self.customer_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "sample_count": self.sample_count,
            "tsv_sha256": self.tsv_sha256,
        }


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _generate_manifest_id(now: Optional[dt.datetime] = None) -> str:
    """Generate a lexicographically time-sortable manifest id."""
    now = now or dt.datetime.now(dt.timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%S%fZ")
    return f"m-{ts}-{uuid.uuid4().hex[:10]}"


def _gzip_b64_encode(text: str) -> str:
    raw = text.encode("utf-8")
    gz = gzip.compress(raw)
    return base64.b64encode(gz).decode("ascii")


def _gzip_b64_decode(b64: str) -> str:
    gz = base64.b64decode(b64.encode("ascii"))
    raw = gzip.decompress(gz)
    return raw.decode("utf-8")


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _estimate_sample_count(tsv_content: str) -> int:
    """Count TSV rows excluding the header (best-effort)."""
    lines = [ln for ln in tsv_content.splitlines() if ln.strip()]
    if not lines:
        return 0
    # If the first line looks like a header row containing SAMPLE_ID, skip it.
    header = lines[0]
    if "SAMPLE_ID" in header and "RUN_ID" in header:
        return max(0, len(lines) - 1)
    return len(lines)


def parse_tsv_to_samples(tsv_content: str) -> List[Dict[str, Any]]:
    """Parse stage_samples.tsv content into a list of sample dicts.

    Expected columns include: RUN_ID, SAMPLE_ID, R1_FQ, R2_FQ (at minimum).
    Returns normalized sample dicts suitable for workset metadata['samples'].
    """
    lines = [ln for ln in tsv_content.splitlines() if ln.strip()]
    if not lines:
        return []

    # Parse header
    header_line = lines[0]
    headers = [h.strip() for h in header_line.split("\t")]

    # Build column index map (case-insensitive)
    col_idx = {}
    for i, h in enumerate(headers):
        col_idx[h.upper()] = i

    samples = []
    for line in lines[1:]:  # Skip header
        cols = line.split("\t")
        if len(cols) < 2:
            continue  # Skip malformed lines

        # Extract sample data using known column names
        sample = {
            "sample_id": cols[col_idx.get("SAMPLE_ID", -1)] if col_idx.get("SAMPLE_ID", -1) >= 0 and col_idx.get("SAMPLE_ID", -1) < len(cols) else "",
            "r1_file": cols[col_idx.get("R1_FQ", -1)] if col_idx.get("R1_FQ", -1) >= 0 and col_idx.get("R1_FQ", -1) < len(cols) else "",
            "r2_file": cols[col_idx.get("R2_FQ", -1)] if col_idx.get("R2_FQ", -1) >= 0 and col_idx.get("R2_FQ", -1) < len(cols) else "",
            "run_id": cols[col_idx.get("RUN_ID", -1)] if col_idx.get("RUN_ID", -1) >= 0 and col_idx.get("RUN_ID", -1) < len(cols) else "",
            "status": "pending",
        }

        # Add optional fields if present
        for field, tsv_col in [
            ("sample_type", "SAMPLE_TYPE"),
            ("lib_prep", "LIB_PREP"),
            ("external_sample_id", "EXTERNAL_SAMPLE_ID"),
        ]:
            idx = col_idx.get(tsv_col, -1)
            if idx >= 0 and idx < len(cols):
                sample[field] = cols[idx]

        # Only add if we have at least sample_id
        if sample["sample_id"]:
            samples.append(sample)

    return samples


class ManifestRegistry:
    """DynamoDB-backed manifest registry."""

    def __init__(
        self,
        table_name: str = "daylily-manifests",
        region: str = "us-west-2",
        profile: Optional[str] = None,
    ):
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile
        session = boto3.Session(**session_kwargs)
        self.dynamodb = session.resource("dynamodb")
        self.table_name = table_name
        self.table = self.dynamodb.Table(table_name)

        LOGGER.info("ManifestRegistry bound to table: %s", self.table.table_name)
        assert hasattr(self.table, "table_name")

    def create_table_if_not_exists(self) -> None:
        try:
            self.table.load()
            LOGGER.info("Manifest table %s already exists", self.table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        LOGGER.info("Creating manifest table %s", self.table_name)
        table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "manifest_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "manifest_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        LOGGER.info("Manifest table %s created successfully", self.table_name)

    def save_manifest(
        self,
        *,
        customer_id: str,
        tsv_content: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> SavedManifest:
        if not customer_id or not customer_id.strip():
            raise ValueError("customer_id is required")
        if not tsv_content or not tsv_content.strip():
            raise ValueError("tsv_content is required")

        created_at = _utc_now_iso()
        manifest_id = _generate_manifest_id()
        sample_count = _estimate_sample_count(tsv_content)

        tsv_sha256 = _sha256_hex(tsv_content)
        tsv_gzip_b64 = _gzip_b64_encode(tsv_content)

        # DynamoDB hard limit is 400KB per item; keep a conservative ceiling.
        if len(tsv_gzip_b64.encode("utf-8")) > 350_000:
            raise ManifestTooLargeError(
                "Manifest TSV is too large to store in DynamoDB. "
                "Consider splitting into multiple manifests."
            )

        item = {
            "customer_id": customer_id,
            "manifest_id": manifest_id,
            "created_at": created_at,
            "name": name or "",
            "description": description or "",
            "sample_count": int(sample_count),
            "tsv_sha256": tsv_sha256,
            "tsv_gzip_b64": tsv_gzip_b64,
            "schema_version": 1,
        }

        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(customer_id) AND attribute_not_exists(manifest_id)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Extremely unlikely given UUID randomness; surface as conflict.
                raise ValueError("Manifest id collision; please retry") from e
            raise

        LOGGER.info(
            "Saved manifest %s for customer %s (samples=%d)",
            manifest_id,
            customer_id,
            sample_count,
        )

        return SavedManifest(
            manifest_id=manifest_id,
            customer_id=customer_id,
            name=name,
            description=description,
            created_at=created_at,
            sample_count=sample_count,
            tsv_sha256=tsv_sha256,
            tsv_gzip_b64=tsv_gzip_b64,
        )

    def list_customer_manifests(self, customer_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        """List manifests (metadata only) for a customer."""
        if not customer_id or not customer_id.strip():
            raise ValueError("customer_id is required")

        try:
            resp = self.table.query(
                KeyConditionExpression=Key("customer_id").eq(customer_id),
                Limit=limit,
                ScanIndexForward=False,  # newest-first due to time-sortable manifest_id
            )
        except ClientError as e:
            LOGGER.error("Failed to list manifests for customer %s: %s", customer_id, str(e))
            raise

        items = resp.get("Items", [])
        result = []
        for it in items:
            result.append(
                {
                    "manifest_id": it.get("manifest_id"),
                    "customer_id": it.get("customer_id"),
                    "name": it.get("name") or None,
                    "description": it.get("description") or None,
                    "created_at": it.get("created_at"),
                    "sample_count": int(it.get("sample_count") or 0),
                }
            )
        return result

    def get_manifest(self, *, customer_id: str, manifest_id: str) -> Optional[SavedManifest]:
        if not customer_id or not customer_id.strip():
            raise ValueError("customer_id is required")
        if not manifest_id or not manifest_id.strip():
            raise ValueError("manifest_id is required")

        try:
            resp = self.table.get_item(
                Key={"customer_id": customer_id, "manifest_id": manifest_id}
            )
        except ClientError as e:
            LOGGER.error(
                "Failed to get manifest %s for customer %s: %s",
                manifest_id,
                customer_id,
                str(e),
            )
            raise

        item = resp.get("Item")
        if not item:
            return None

        return SavedManifest(
            manifest_id=item["manifest_id"],
            customer_id=item["customer_id"],
            name=item.get("name") or None,
            description=item.get("description") or None,
            created_at=item.get("created_at") or "",
            sample_count=int(item.get("sample_count") or 0),
            tsv_sha256=item.get("tsv_sha256") or "",
            tsv_gzip_b64=item.get("tsv_gzip_b64") or "",
        )

    def get_manifest_tsv(self, *, customer_id: str, manifest_id: str) -> Optional[str]:
        m = self.get_manifest(customer_id=customer_id, manifest_id=manifest_id)
        if not m:
            return None
        return _gzip_b64_decode(m.tsv_gzip_b64)
