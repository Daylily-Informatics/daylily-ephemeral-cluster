"""
File Registry - DynamoDB-backed file registration system with GA4GH metadata.

Manages file registration, metadata capture, and file set grouping for the
Daylily portal's file management system. Integrates with linked bucket management
for customer S3 bucket discovery and file tracking.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Tuple


def _utc_now_iso() -> str:
    """Return current UTC time in ISO format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

LOGGER = logging.getLogger("daylily.file_registry")

# File format detection patterns
FILE_FORMAT_PATTERNS = {
    "fastq": [r"\.fastq(\.gz)?$", r"\.fq(\.gz)?$"],
    "bam": [r"\.bam$"],
    "cram": [r"\.cram$"],
    "vcf": [r"\.vcf(\.gz)?$", r"\.gvcf(\.gz)?$"],
    "bed": [r"\.bed(\.gz)?$"],
    "fasta": [r"\.fa(sta)?(\.gz)?$", r"\.fna(\.gz)?$"],
}


@dataclass
class FileMetadata:
    """Technical metadata for a registered file."""
    file_id: str  # Unique identifier
    s3_uri: str  # Full S3 URI
    file_size_bytes: int
    md5_checksum: Optional[str] = None
    file_format: str = "fastq"  # fastq, bam, vcf, etc.
    created_at: str = field(default_factory=_utc_now_iso)

    @property
    def filename(self) -> str:
        """Extract filename from S3 URI."""
        return PurePosixPath(self.s3_uri).name


@dataclass
class SequencingMetadata:
    """Sequencing run and library metadata."""
    platform: str = "ILLUMINA_NOVASEQ_X"  # Sequencing platform
    vendor: str = "ILMN"  # Vendor code
    run_id: str = ""  # Sequencing run identifier
    lane: int = 0
    barcode_id: str = "S1"
    flowcell_id: Optional[str] = None
    run_date: Optional[str] = None


@dataclass
class BiosampleMetadata:
    """Biosample/specimen metadata following GA4GH standards."""
    biosample_id: str
    subject_id: str  # Individual/subject identifier
    sample_type: str = "blood"  # blood, tissue, saliva, tumor, etc.
    tissue_type: Optional[str] = None
    collection_date: Optional[str] = None
    preservation_method: Optional[str] = None  # fresh, frozen, ffpe
    tumor_fraction: Optional[float] = None


@dataclass
class FileRegistration:
    """Complete file registration with all metadata."""
    file_id: str
    customer_id: str
    file_metadata: FileMetadata
    sequencing_metadata: SequencingMetadata
    biosample_metadata: BiosampleMetadata
    
    # Pairing information
    paired_with: Optional[str] = None  # file_id of paired file (R2 if this is R1)
    read_number: int = 1  # 1 for R1, 2 for R2
    
    # QC and analysis
    quality_score: Optional[float] = None
    percent_q30: Optional[float] = None
    concordance_vcf_path: Optional[str] = None
    is_positive_control: bool = False
    is_negative_control: bool = False
    
    # User tags
    tags: List[str] = field(default_factory=list)

    # Timestamps
    registered_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)


@dataclass
class FileSet:
    """Group of files sharing common GA4GH metadata."""
    fileset_id: str
    customer_id: str
    name: str
    description: Optional[str] = None

    # Shared metadata
    biosample_metadata: Optional[BiosampleMetadata] = None
    sequencing_metadata: Optional[SequencingMetadata] = None

    # File membership
    file_ids: List[str] = field(default_factory=list)

    # Tags for organization
    tags: List[str] = field(default_factory=list)

    # Timestamps
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)


@dataclass
class FileWorksetUsage:
    """Track file usage in worksets for bidirectional relationships."""
    file_id: str
    workset_id: str
    customer_id: str
    usage_type: str = "input"  # input, output, reference
    added_at: str = field(default_factory=_utc_now_iso)
    workset_state: Optional[str] = None  # Track workset state at time of use
    notes: Optional[str] = None


class FileRegistry:
    """DynamoDB-backed file registry for GA4GH-compliant metadata storage."""

    def __init__(
        self,
        files_table_name: str = "daylily-files",
        filesets_table_name: str = "daylily-filesets",
        file_workset_usage_table_name: str = "daylily-file-workset-usage",
        region: str = "us-west-2",
        profile: Optional[str] = None,
    ):
        """Initialize file registry.

        Args:
            files_table_name: DynamoDB table for file registrations
            filesets_table_name: DynamoDB table for file sets
            file_workset_usage_table_name: DynamoDB table for file-workset relationships
            region: AWS region
            profile: AWS profile name
        """
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self.dynamodb = session.resource("dynamodb")
        self.files_table_name = files_table_name
        self.filesets_table_name = filesets_table_name
        self.file_workset_usage_table_name = file_workset_usage_table_name
        self.files_table = self.dynamodb.Table(files_table_name)
        self.filesets_table = self.dynamodb.Table(filesets_table_name)
        self.file_workset_usage_table = self.dynamodb.Table(file_workset_usage_table_name)

        # Sanity logging/guards so mis-bound DynamoDB resources surface immediately
        LOGGER.info(
            "FileRegistry bound to tables: files=%s, filesets=%s, file_workset_usage=%s",
            self.files_table.table_name,
            self.filesets_table.table_name,
            self.file_workset_usage_table.table_name,
        )
        assert hasattr(self.files_table, "table_name")
        assert hasattr(self.filesets_table, "table_name")
        assert hasattr(self.file_workset_usage_table, "table_name")

    def create_tables_if_not_exist(self) -> None:
        """Create DynamoDB tables for file registry."""
        self._create_files_table()
        self._create_filesets_table()
        self._create_file_workset_usage_table()
    
    def _create_files_table(self) -> None:
        """Create files registration table."""
        try:
            self.files_table.load()
            LOGGER.info("Files table %s already exists", self.files_table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        
        LOGGER.info("Creating files table %s", self.files_table_name)
        table = self.dynamodb.create_table(
            TableName=self.files_table_name,
            KeySchema=[
                {"AttributeName": "file_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "file_id", "AttributeType": "S"},
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "registered_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "customer-id-index",
                    "KeySchema": [
                        {"AttributeName": "customer_id", "KeyType": "HASH"},
                        {"AttributeName": "registered_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        LOGGER.info("Files table created successfully")
    
    def _create_filesets_table(self) -> None:
        """Create file sets table."""
        try:
            self.filesets_table.load()
            LOGGER.info("FileSet table %s already exists", self.filesets_table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        
        LOGGER.info("Creating filesets table %s", self.filesets_table_name)
        table = self.dynamodb.create_table(
            TableName=self.filesets_table_name,
            KeySchema=[
                {"AttributeName": "fileset_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "fileset_id", "AttributeType": "S"},
                {"AttributeName": "customer_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "customer-id-index",
                    "KeySchema": [
                        {"AttributeName": "customer_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        LOGGER.info("FileSet table created successfully")

    def _create_file_workset_usage_table(self) -> None:
        """Create file-workset usage tracking table."""
        try:
            self.file_workset_usage_table.load()
            LOGGER.info("File-workset usage table %s already exists", self.file_workset_usage_table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        LOGGER.info("Creating file-workset usage table %s", self.file_workset_usage_table_name)
        table = self.dynamodb.create_table(
            TableName=self.file_workset_usage_table_name,
            KeySchema=[
                {"AttributeName": "file_id", "KeyType": "HASH"},
                {"AttributeName": "workset_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "file_id", "AttributeType": "S"},
                {"AttributeName": "workset_id", "AttributeType": "S"},
                {"AttributeName": "customer_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "workset-id-index",
                    "KeySchema": [
                        {"AttributeName": "workset_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "customer-id-index",
                    "KeySchema": [
                        {"AttributeName": "customer_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        LOGGER.info("File-workset usage table created successfully")

    def register_file(self, registration: FileRegistration) -> bool:
        """Register a file with metadata.
        
        Args:
            registration: FileRegistration object
            
        Returns:
            True if registered, False if already exists
        """
        item = {
            "file_id": registration.file_id,
            "customer_id": registration.customer_id,
            "file_metadata": json.dumps(asdict(registration.file_metadata)),
            "sequencing_metadata": json.dumps(asdict(registration.sequencing_metadata)),
            "biosample_metadata": json.dumps(asdict(registration.biosample_metadata)),
            "paired_with": registration.paired_with or "",
            "read_number": registration.read_number,
            "registered_at": registration.registered_at,
            "updated_at": registration.updated_at,
            "tags": registration.tags,
        }
        
        if registration.quality_score is not None:
            item["quality_score"] = registration.quality_score
        if registration.percent_q30 is not None:
            item["percent_q30"] = registration.percent_q30
        if registration.concordance_vcf_path:
            item["concordance_vcf_path"] = registration.concordance_vcf_path
        
        item["is_positive_control"] = registration.is_positive_control
        item["is_negative_control"] = registration.is_negative_control
        
        try:
            self.files_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(file_id)",
            )
            LOGGER.info("Registered file %s for customer %s", registration.file_id, registration.customer_id)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.warning("File %s already registered", registration.file_id)
                return False
            raise
    
    def get_file(self, file_id: str) -> Optional[FileRegistration]:
        """Retrieve a file registration by ID."""
        LOGGER.debug(f"get_file: Attempting to get file_id={file_id}")
        LOGGER.debug(f"get_file: files_table={self.files_table_name}")

        try:
            response = self.files_table.get_item(Key={"file_id": file_id})
            LOGGER.debug(f"get_file: DynamoDB response received, has Item: {'Item' in response}")

            if "Item" not in response:
                LOGGER.debug(f"get_file: File {file_id} not found in registry")
                return None

            item = response["Item"]
            LOGGER.debug(f"get_file: Converting item to FileRegistration")
            result = self._item_to_registration(item)
            LOGGER.debug(f"get_file: Successfully converted item to FileRegistration")
            return result
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "ResourceNotFoundException":
                LOGGER.warning(f"get_file: Table {self.files_table_name} does not exist")
                return None
            # Don't use exc_info=True as it causes deepcopy issues with boto3 objects
            LOGGER.error("Failed to get file %s: %s", file_id, str(e))
            return None
        except Exception as e:
            # Don't use exc_info=True as it causes deepcopy issues with boto3 objects
            LOGGER.error("Unexpected error in get_file(%s): %s", file_id, str(e))
            return None
    
    def list_customer_files(self, customer_id: str, limit: int = 100) -> List[FileRegistration]:
        """List all files for a customer."""
        try:
            response = self.files_table.query(
                IndexName="customer-id-index",
                KeyConditionExpression=Key("customer_id").eq(customer_id),
                Limit=limit,
            )

            # Fail-fast: if any item cannot be converted, surface the error
            return [
                self._item_to_registration(item)
                for item in response.get("Items", [])
            ]
        except ClientError as e:
            LOGGER.error("Failed to list files for customer %s: %s", customer_id, str(e))
            raise

    def find_file_by_s3_uri(self, customer_id: str, s3_uri: str) -> Optional[FileRegistration]:
        """Find a file registration for a customer by exact S3 URI.

        This is used to enforce uniqueness of S3 URIs across registrations and to
        support idempotent behavior when a user attempts to register the same S3
        object multiple times.
        """
        LOGGER.debug("find_file_by_s3_uri: customer_id=%s, s3_uri=%s", customer_id, s3_uri)

        try:
            exclusive_start_key: Optional[Dict[str, Any]] = None

            while True:
                query_kwargs: Dict[str, Any] = {
                    "IndexName": "customer-id-index",
                    "KeyConditionExpression": Key("customer_id").eq(customer_id),
                }
                if exclusive_start_key is not None:
                    query_kwargs["ExclusiveStartKey"] = exclusive_start_key

                response = self.files_table.query(**query_kwargs)
                items = response.get("Items", [])

                for item in items:
                    try:
                        meta_raw = item.get("file_metadata")
                        if not meta_raw:
                            continue
                        meta = json.loads(meta_raw)
                        if meta.get("s3_uri") == s3_uri:
                            LOGGER.debug(
                                "find_file_by_s3_uri: Found existing registration for %s",
                                s3_uri,
                            )
                            return self._item_to_registration(item)
                    except Exception as inner_e:  # pragma: no cover - defensive logging
                        LOGGER.error(
                            "find_file_by_s3_uri: Failed to inspect item for %s: %s",
                            s3_uri,
                            str(inner_e),
                        )

                exclusive_start_key = response.get("LastEvaluatedKey")
                if not exclusive_start_key:
                    break

            LOGGER.debug(
                "find_file_by_s3_uri: No existing registration found for customer_id=%s, s3_uri=%s",
                customer_id,
                s3_uri,
            )
            return None
        except ClientError as e:
            LOGGER.error(
                "Failed to find file by s3_uri %s for customer %s: %s",
                s3_uri,
                customer_id,
                str(e),
            )
            raise
    
    def _item_to_registration(self, item: Dict[str, Any]) -> FileRegistration:
        """Convert DynamoDB item to FileRegistration."""
        LOGGER.debug(
            f"_item_to_registration: Starting conversion for file_id={item.get('file_id')}"
        )

        LOGGER.debug("_item_to_registration: Parsing file_metadata")
        file_meta = json.loads(item.get("file_metadata", "{}"))

        LOGGER.debug("_item_to_registration: Parsing sequencing_metadata")
        seq_meta = json.loads(item.get("sequencing_metadata", "{}"))

        LOGGER.debug("_item_to_registration: Parsing biosample_metadata")
        bio_meta = json.loads(item.get("biosample_metadata", "{}"))

        LOGGER.debug("_item_to_registration: Creating FileMetadata")
        file_metadata_obj = FileMetadata(**file_meta)

        LOGGER.debug("_item_to_registration: Creating SequencingMetadata")
        seq_metadata_obj = SequencingMetadata(**seq_meta)

        LOGGER.debug("_item_to_registration: Creating BiosampleMetadata")
        bio_metadata_obj = BiosampleMetadata(**bio_meta)

        LOGGER.debug("_item_to_registration: Creating FileRegistration object")
        result = FileRegistration(
            file_id=item["file_id"],
            customer_id=item["customer_id"],
            file_metadata=file_metadata_obj,
            sequencing_metadata=seq_metadata_obj,
            biosample_metadata=bio_metadata_obj,
            paired_with=item.get("paired_with") or None,
            read_number=item.get("read_number", 1),
            quality_score=item.get("quality_score"),
            percent_q30=item.get("percent_q30"),
            concordance_vcf_path=item.get("concordance_vcf_path"),
            is_positive_control=item.get("is_positive_control", False),
            is_negative_control=item.get("is_negative_control", False),
            tags=item.get("tags", []),
            registered_at=item.get("registered_at", ""),
            updated_at=item.get("updated_at", ""),
        )
        LOGGER.debug("_item_to_registration: Successfully created FileRegistration")
        return result
    
    def create_fileset(self, fileset: FileSet) -> bool:
        """Create a file set grouping files with shared metadata."""
        item = {
            "fileset_id": fileset.fileset_id,
            "customer_id": fileset.customer_id,
            "name": fileset.name,
            "description": fileset.description or "",
            "file_ids": fileset.file_ids,
            "created_at": fileset.created_at,
            "updated_at": fileset.updated_at,
        }
        
        if fileset.biosample_metadata:
            item["biosample_metadata"] = json.dumps(asdict(fileset.biosample_metadata))
        if fileset.sequencing_metadata:
            item["sequencing_metadata"] = json.dumps(asdict(fileset.sequencing_metadata))
        
        try:
            self.filesets_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(fileset_id)",
            )
            LOGGER.info("Created fileset %s for customer %s", fileset.fileset_id, fileset.customer_id)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.warning("FileSet %s already exists", fileset.fileset_id)
                return False
            raise
    
    def get_fileset(self, fileset_id: str) -> Optional[FileSet]:
        """Retrieve a file set by ID."""
        try:
            response = self.filesets_table.get_item(Key={"fileset_id": fileset_id})
            if "Item" not in response:
                return None
            
            item = response["Item"]
            bio_meta = None
            seq_meta = None
            
            if "biosample_metadata" in item:
                bio_meta = BiosampleMetadata(**json.loads(item["biosample_metadata"]))
            if "sequencing_metadata" in item:
                seq_meta = SequencingMetadata(**json.loads(item["sequencing_metadata"]))
            
            return FileSet(
                fileset_id=item["fileset_id"],
                customer_id=item["customer_id"],
                name=item["name"],
                description=item.get("description"),
                biosample_metadata=bio_meta,
                sequencing_metadata=seq_meta,
                file_ids=item.get("file_ids", []),
                created_at=item.get("created_at", ""),
                updated_at=item.get("updated_at", ""),
            )
        except ClientError as e:
            LOGGER.error("Failed to get fileset %s: %s", fileset_id, str(e))
            return None
    
    def list_customer_filesets(self, customer_id: str) -> List[FileSet]:
        """List all file sets for a customer."""
        try:
            response = self.filesets_table.query(
                IndexName="customer-id-index",
                KeyConditionExpression=Key("customer_id").eq(customer_id),
            )
            
            filesets = []
            for item in response.get("Items", []):
                bio_meta = None
                seq_meta = None
                
                if "biosample_metadata" in item:
                    bio_meta = BiosampleMetadata(**json.loads(item["biosample_metadata"]))
                if "sequencing_metadata" in item:
                    seq_meta = SequencingMetadata(**json.loads(item["sequencing_metadata"]))
                
                filesets.append(FileSet(
                    fileset_id=item["fileset_id"],
                    customer_id=item["customer_id"],
                    name=item["name"],
                    description=item.get("description"),
                    biosample_metadata=bio_meta,
                    sequencing_metadata=seq_meta,
                    file_ids=item.get("file_ids", []),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                ))
            return filesets
        except ClientError as e:
            LOGGER.error("Failed to list filesets for customer %s: %s", customer_id, str(e))
            return []

    def add_files_to_fileset(self, fileset_id: str, file_ids: List[str]) -> bool:
        """Add files to an existing file set."""
        try:
            self.filesets_table.update_item(
                Key={"fileset_id": fileset_id},
                UpdateExpression="SET file_ids = list_append(if_not_exists(file_ids, :empty), :fids), updated_at = :ts",
                ExpressionAttributeValues={
                    ":fids": file_ids,
                    ":empty": [],
                    ":ts": _utc_now_iso(),
                },
            )
            LOGGER.info("Added %d files to fileset %s", len(file_ids), fileset_id)
            return True
        except ClientError as e:
            LOGGER.error("Failed to add files to fileset %s: %s", fileset_id, str(e))
            return False

    def remove_files_from_fileset(self, fileset_id: str, file_ids: List[str]) -> bool:
        """Remove files from a file set."""
        try:
            fileset = self.get_fileset(fileset_id)
            if not fileset:
                return False

            # Remove specified files
            updated_file_ids = [fid for fid in fileset.file_ids if fid not in file_ids]

            self.filesets_table.update_item(
                Key={"fileset_id": fileset_id},
                UpdateExpression="SET file_ids = :fids, updated_at = :ts",
                ExpressionAttributeValues={
                    ":fids": updated_file_ids,
                    ":ts": _utc_now_iso(),
                },
            )
            LOGGER.info("Removed %d files from fileset %s", len(file_ids), fileset_id)
            return True
        except ClientError as e:
            LOGGER.error("Failed to remove files from fileset %s: %s", fileset_id, str(e))
            return False

    def update_fileset_metadata(
        self,
        fileset_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        biosample_metadata: Optional[BiosampleMetadata] = None,
        sequencing_metadata: Optional[SequencingMetadata] = None,
    ) -> bool:
        """Update file set metadata."""
        try:
            update_expr_parts: List[str] = ["updated_at = :ts"]
            expr_values: Dict[str, Any] = {":ts": _utc_now_iso()}

            if name is not None:
                update_expr_parts.append("name = :name")
                expr_values[":name"] = name

            if description is not None:
                update_expr_parts.append("description = :desc")
                expr_values[":desc"] = description

            if biosample_metadata is not None:
                update_expr_parts.append("biosample_metadata = :bio")
                expr_values[":bio"] = {
                    "biosample_id": biosample_metadata.biosample_id,
                    "subject_id": biosample_metadata.subject_id,
                    "sample_type": biosample_metadata.sample_type,
                    "tissue_type": biosample_metadata.tissue_type,
                    "collection_date": biosample_metadata.collection_date,
                    "preservation_method": biosample_metadata.preservation_method,
                    "tumor_fraction": biosample_metadata.tumor_fraction,
                }

            if sequencing_metadata is not None:
                update_expr_parts.append("sequencing_metadata = :seq")
                expr_values[":seq"] = {
                    "platform": sequencing_metadata.platform,
                    "vendor": sequencing_metadata.vendor,
                    "run_id": sequencing_metadata.run_id,
                    "lane": sequencing_metadata.lane,
                    "barcode_id": sequencing_metadata.barcode_id,
                    "flowcell_id": sequencing_metadata.flowcell_id,
                    "run_date": sequencing_metadata.run_date,
                }

            self.filesets_table.update_item(
                Key={"fileset_id": fileset_id},
                UpdateExpression="SET " + ", ".join(update_expr_parts),
                ExpressionAttributeValues=expr_values,
            )
            LOGGER.info("Updated metadata for fileset %s", fileset_id)
            return True
        except ClientError as e:
            LOGGER.error("Failed to update fileset %s: %s", fileset_id, str(e))
            return False

    def delete_fileset(self, fileset_id: str) -> bool:
        """Delete a file set (does not delete the files themselves)."""
        try:
            self.filesets_table.delete_item(Key={"fileset_id": fileset_id})
            LOGGER.info("Deleted fileset %s", fileset_id)
            return True
        except ClientError as e:
            LOGGER.error("Failed to delete fileset %s: %s", fileset_id, str(e))
            return False

    def clone_fileset(self, fileset_id: str, new_name: str, new_fileset_id: Optional[str] = None) -> Optional[FileSet]:
        """Clone a file set with a new name."""
        try:
            original = self.get_fileset(fileset_id)
            if not original:
                return None

            new_id = new_fileset_id or str(uuid.uuid4())
            cloned = FileSet(
                fileset_id=new_id,
                customer_id=original.customer_id,
                name=new_name,
                description=f"Cloned from {original.name}",
                biosample_metadata=original.biosample_metadata,
                sequencing_metadata=original.sequencing_metadata,
                file_ids=original.file_ids.copy(),
                tags=original.tags.copy(),
            )

            if self.create_fileset(cloned):
                return cloned
            return None
        except Exception as e:
            LOGGER.error("Failed to clone fileset %s: %s", fileset_id, str(e))
            return None

    def get_fileset_files(self, fileset_id: str) -> List[FileRegistration]:
        """Get all files in a file set."""
        fileset = self.get_fileset(fileset_id)
        if not fileset:
            return []

        files = []
        for file_id in fileset.file_ids:
            f = self.get_file(file_id)
            if f:
                files.append(f)
        return files

    def update_file_tags(self, file_id: str, tags: List[str]) -> bool:
        """Update tags for a file."""
        try:
            self.files_table.update_item(
                Key={"file_id": file_id},
                UpdateExpression="SET tags = :tags, updated_at = :ts",
                ExpressionAttributeValues={
                    ":tags": tags,
                    ":ts": _utc_now_iso(),
                },
            )
            return True
        except ClientError as e:
            LOGGER.error("Failed to update tags for file %s: %s", file_id, str(e))
            return False

    def update_file(
        self,
        file_id: str,
        file_metadata: Optional[Dict[str, Any]] = None,
        biosample_metadata: Optional[Dict[str, Any]] = None,
        sequencing_metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        read_number: Optional[int] = None,
        paired_with: Optional[str] = None,
        quality_score: Optional[float] = None,
        percent_q30: Optional[float] = None,
        is_positive_control: Optional[bool] = None,
        is_negative_control: Optional[bool] = None,
    ) -> bool:
        """Update file registration metadata.

        Args:
            file_id: File identifier
            file_metadata: Dict with file metadata fields (md5_checksum, file_format, etc.)
            biosample_metadata: Dict with biosample fields (biosample_id, subject_id, etc.)
            sequencing_metadata: Dict with sequencing fields (platform, run_id, etc.)
            tags: List of tags
            read_number: Read number (1 or 2)
            paired_with: File ID of paired file
            quality_score: Quality score
            percent_q30: Percentage of Q30 bases
            is_positive_control: Flag for positive control
            is_negative_control: Flag for negative control

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            update_parts = ["updated_at = :ts"]
            expr_values: Dict[str, Any] = {":ts": _utc_now_iso()}

            # File metadata fields
            if file_metadata:
                if "md5_checksum" in file_metadata:
                    update_parts.append("md5_checksum = :md5")
                    expr_values[":md5"] = file_metadata["md5_checksum"]
                if "file_format" in file_metadata:
                    update_parts.append("file_format = :fmt")
                    expr_values[":fmt"] = file_metadata["file_format"]

            # Biosample metadata (nested object)
            if biosample_metadata:
                update_parts.append("biosample_id = :bio_id")
                update_parts.append("subject_id = :subj_id")
                update_parts.append("sample_type = :stype")
                expr_values[":bio_id"] = biosample_metadata.get("biosample_id", "")
                expr_values[":subj_id"] = biosample_metadata.get("subject_id", "")
                expr_values[":stype"] = biosample_metadata.get("sample_type", "blood")

                if "tissue_type" in biosample_metadata:
                    update_parts.append("tissue_type = :ttype")
                    expr_values[":ttype"] = biosample_metadata["tissue_type"]
                if "collection_date" in biosample_metadata:
                    update_parts.append("collection_date = :cdate")
                    expr_values[":cdate"] = biosample_metadata["collection_date"]
                if "preservation_method" in biosample_metadata:
                    update_parts.append("preservation_method = :pmethod")
                    expr_values[":pmethod"] = biosample_metadata["preservation_method"]
                if "tumor_fraction" in biosample_metadata:
                    update_parts.append("tumor_fraction = :tfrac")
                    expr_values[":tfrac"] = biosample_metadata["tumor_fraction"]

            # Sequencing metadata (nested object)
            if sequencing_metadata:
                update_parts.append("platform = :plat")
                update_parts.append("vendor = :vend")
                expr_values[":plat"] = sequencing_metadata.get("platform", "ILLUMINA_NOVASEQ_X")
                expr_values[":vend"] = sequencing_metadata.get("vendor", "ILMN")

                if "run_id" in sequencing_metadata:
                    update_parts.append("run_id = :runid")
                    expr_values[":runid"] = sequencing_metadata["run_id"]
                if "lane" in sequencing_metadata:
                    update_parts.append("lane = :lane")
                    expr_values[":lane"] = sequencing_metadata["lane"]
                if "barcode_id" in sequencing_metadata:
                    update_parts.append("barcode_id = :bcode")
                    expr_values[":bcode"] = sequencing_metadata["barcode_id"]
                if "flowcell_id" in sequencing_metadata:
                    update_parts.append("flowcell_id = :fcid")
                    expr_values[":fcid"] = sequencing_metadata["flowcell_id"]
                if "run_date" in sequencing_metadata:
                    update_parts.append("run_date = :rdate")
                    expr_values[":rdate"] = sequencing_metadata["run_date"]

            # Other fields
            if tags is not None:
                update_parts.append("tags = :tags")
                expr_values[":tags"] = tags
            if read_number is not None:
                update_parts.append("read_number = :rnum")
                expr_values[":rnum"] = read_number
            if paired_with is not None:
                update_parts.append("paired_with = :paired")
                expr_values[":paired"] = paired_with
            if quality_score is not None:
                update_parts.append("quality_score = :qscore")
                expr_values[":qscore"] = quality_score
            if percent_q30 is not None:
                update_parts.append("percent_q30 = :pq30")
                expr_values[":pq30"] = percent_q30
            if is_positive_control is not None:
                update_parts.append("is_positive_control = :posctrl")
                expr_values[":posctrl"] = is_positive_control
            if is_negative_control is not None:
                update_parts.append("is_negative_control = :negctrl")
                expr_values[":negctrl"] = is_negative_control

            self.files_table.update_item(
                Key={"file_id": file_id},
                UpdateExpression="SET " + ", ".join(update_parts),
                ExpressionAttributeValues=expr_values,
                ConditionExpression="attribute_exists(file_id)",
            )
            LOGGER.info("Updated file %s", file_id)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.warning("File %s not found for update", file_id)
                return False
            LOGGER.error("Failed to update file %s: %s", file_id, str(e))
            return False

    def search_files_by_tag(self, customer_id: str, tag: str) -> List[FileRegistration]:
        """Search files by tag within a customer's files."""
        # Note: This is a scan operation - for production, consider a GSI on tags
        files = self.list_customer_files(customer_id, limit=1000)
        return [f for f in files if tag in f.tags]

    def search_files_by_biosample(self, customer_id: str, biosample_id: str) -> List[FileRegistration]:
        """Search files by biosample ID."""
        files = self.list_customer_files(customer_id, limit=1000)
        return [f for f in files if f.biosample_metadata.biosample_id == biosample_id]

    # ========== File-Workset Usage Tracking ==========

    def record_file_workset_usage(
        self,
        file_id: str,
        workset_id: str,
        customer_id: str,
        usage_type: str = "input",
        workset_state: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Record that a file is used in a workset.

        Args:
            file_id: File identifier
            workset_id: Workset identifier
            customer_id: Customer identifier
            usage_type: Type of usage (input, output, reference)
            workset_state: Current state of the workset
            notes: Optional notes about the usage

        Returns:
            True if recorded successfully
        """
        try:
            item = {
                "file_id": file_id,
                "workset_id": workset_id,
                "customer_id": customer_id,
                "usage_type": usage_type,
                "added_at": _utc_now_iso(),
            }
            if workset_state:
                item["workset_state"] = workset_state
            if notes:
                item["notes"] = notes

            self.file_workset_usage_table.put_item(Item=item)
            LOGGER.info("Recorded file %s usage in workset %s", file_id, workset_id)
            return True
        except ClientError as e:
            LOGGER.error("Failed to record file-workset usage: %s", str(e))
            return False

    def get_file_workset_history(self, file_id: str) -> List[FileWorksetUsage]:
        """Get all worksets that have used a file.

        Args:
            file_id: File identifier

        Returns:
            List of FileWorksetUsage records
        """
        try:
            response = self.file_workset_usage_table.query(
                KeyConditionExpression="file_id = :fid",
                ExpressionAttributeValues={":fid": file_id},
            )

            usages = []
            for item in response.get("Items", []):
                usages.append(FileWorksetUsage(
                    file_id=item["file_id"],
                    workset_id=item["workset_id"],
                    customer_id=item["customer_id"],
                    usage_type=item.get("usage_type", "input"),
                    added_at=item.get("added_at", ""),
                    workset_state=item.get("workset_state"),
                    notes=item.get("notes"),
                ))
            return usages
        except ClientError as e:
            LOGGER.error("Failed to get file workset history: %s", str(e))
            return []

    def get_workset_files(self, workset_id: str) -> List[FileWorksetUsage]:
        """Get all files used in a workset.

        Args:
            workset_id: Workset identifier

        Returns:
            List of FileWorksetUsage records
        """
        try:
            response = self.file_workset_usage_table.query(
                IndexName="workset-id-index",
                KeyConditionExpression="workset_id = :wid",
                ExpressionAttributeValues={":wid": workset_id},
            )

            usages = []
            for item in response.get("Items", []):
                usages.append(FileWorksetUsage(
                    file_id=item["file_id"],
                    workset_id=item["workset_id"],
                    customer_id=item["customer_id"],
                    usage_type=item.get("usage_type", "input"),
                    added_at=item.get("added_at", ""),
                    workset_state=item.get("workset_state"),
                    notes=item.get("notes"),
                ))
            return usages
        except ClientError as e:
            LOGGER.error("Failed to get workset files: %s", str(e))
            return []

    def update_workset_usage_state(self, workset_id: str, new_state: str) -> int:
        """Update the workset state for all file usages in a workset.

        Args:
            workset_id: Workset identifier
            new_state: New workset state

        Returns:
            Number of records updated
        """
        usages = self.get_workset_files(workset_id)
        updated = 0

        for usage in usages:
            try:
                self.file_workset_usage_table.update_item(
                    Key={"file_id": usage.file_id, "workset_id": workset_id},
                    UpdateExpression="SET workset_state = :state",
                    ExpressionAttributeValues={":state": new_state},
                )
                updated += 1
            except ClientError as e:
                LOGGER.error("Failed to update usage state: %s", str(e))

        return updated

    def get_files_for_workset_recreation(self, workset_id: str) -> List[FileRegistration]:
        """Get all input files needed to recreate a workset.

        Args:
            workset_id: Workset identifier

        Returns:
            List of FileRegistration objects for input files
        """
        usages = self.get_workset_files(workset_id)
        input_usages = [u for u in usages if u.usage_type == "input"]

        files = []
        for usage in input_usages:
            f = self.get_file(usage.file_id)
            if f:
                files.append(f)
        return files


def detect_file_format(filename: str) -> str:
    """Detect file format from filename."""
    filename_lower = filename.lower()
    for format_name, patterns in FILE_FORMAT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, filename_lower):
                return format_name
    return "unknown"


def generate_file_id(s3_uri: str, customer_id: str) -> str:
    """Generate a unique file ID from S3 URI and customer ID."""
    hash_input = f"{customer_id}:{s3_uri}"
    return f"file-{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"


@dataclass
class DiscoveredFile:
    """A file discovered from S3 bucket scanning."""
    s3_uri: str
    bucket_name: str
    key: str
    file_size_bytes: int
    last_modified: str
    etag: str
    detected_format: str
    is_registered: bool = False
    file_id: Optional[str] = None


class BucketFileDiscovery:
    """Discover and scan files in linked S3 buckets."""

    def __init__(
        self,
        region: str = "us-west-2",
        profile: Optional[str] = None,
    ):
        """Initialize bucket file discovery.

        Args:
            region: AWS region
            profile: AWS profile name
        """
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self.s3 = session.client("s3")
        self.region = region

    def discover_files(
        self,
        bucket_name: str,
        prefix: str = "",
        file_formats: Optional[List[str]] = None,
        max_files: int = 1000,
    ) -> List[DiscoveredFile]:
        """Discover files in an S3 bucket.

        Args:
            bucket_name: S3 bucket name
            prefix: Optional prefix to filter files
            file_formats: Optional list of formats to filter (e.g., ["fastq", "bam"])
            max_files: Maximum number of files to return

        Returns:
            List of discovered files
        """
        LOGGER.debug(f"discover_files: Starting discovery in bucket={bucket_name}, prefix={prefix}, formats={file_formats}, max_files={max_files}")
        discovered = []
        paginator = self.s3.get_paginator("list_objects_v2")

        try:
            for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]

                    # Skip directories
                    if key.endswith("/"):
                        continue

                    detected_format = detect_file_format(key)
                    LOGGER.debug(f"discover_files: Found file {key}, detected_format={detected_format}")

                    # Filter by format if specified
                    if file_formats and detected_format not in file_formats:
                        LOGGER.debug(f"discover_files: Skipping {key} (format {detected_format} not in {file_formats})")
                        continue

                    s3_uri = f"s3://{bucket_name}/{key}"
                    discovered.append(DiscoveredFile(
                        s3_uri=s3_uri,
                        bucket_name=bucket_name,
                        key=key,
                        file_size_bytes=obj["Size"],
                        last_modified=obj["LastModified"].isoformat(),
                        etag=obj["ETag"].strip('"'),
                        detected_format=detected_format,
                    ))

                    if len(discovered) >= max_files:
                        LOGGER.info("Reached max files limit (%d)", max_files)
                        return discovered

        except ClientError as e:
            LOGGER.error("Failed to discover files in %s: %s", bucket_name, str(e))

        LOGGER.info("Discovered %d files in s3://%s/%s", len(discovered), bucket_name, prefix)
        return discovered

    def check_registration_status(
        self,
        discovered_files: List[DiscoveredFile],
        registry: FileRegistry,
        customer_id: str,
    ) -> List[DiscoveredFile]:
        """Check which discovered files are already registered.

        Args:
            discovered_files: List of discovered files
            registry: FileRegistry instance
            customer_id: Customer ID

        Returns:
            Updated list with registration status
        """
        LOGGER.debug(f"check_registration_status: Starting with {len(discovered_files)} files")
        LOGGER.debug(f"check_registration_status: customer_id={customer_id}")
        LOGGER.debug(f"check_registration_status: registry is FileRegistry instance")

        for i, df in enumerate(discovered_files):
            try:
                LOGGER.debug(f"check_registration_status: Processing file {i+1}/{len(discovered_files)}: {df.key}")
                file_id = generate_file_id(df.s3_uri, customer_id)
                LOGGER.debug(f"check_registration_status: Generated file_id={file_id}")

                LOGGER.debug(f"check_registration_status: Calling registry.get_file({file_id})")
                existing = registry.get_file(file_id)
                LOGGER.debug(f"check_registration_status: get_file returned: {existing is not None}")

                if existing:
                    df.is_registered = True
                    df.file_id = file_id
                    LOGGER.debug(f"check_registration_status: File {df.key} is registered")
            except Exception as e:
                # Log error but continue processing other files
                LOGGER.warning(f"check_registration_status: Error processing file {df.key}: {str(e)}")

        LOGGER.debug(f"check_registration_status: Completed successfully")
        return discovered_files

    def auto_register_files(
        self,
        discovered_files: List[DiscoveredFile],
        registry: FileRegistry,
        customer_id: str,
        biosample_id: str,
        subject_id: str,
        sequencing_platform: str = "ILLUMINA_NOVASEQ_X",
    ) -> Tuple[int, int, List[str]]:
        """Auto-register discovered files with default metadata.

        Args:
            discovered_files: List of discovered files
            registry: FileRegistry instance
            customer_id: Customer ID
            biosample_id: Default biosample ID
            subject_id: Default subject ID
            sequencing_platform: Sequencing platform

        Returns:
            Tuple of (registered_count, skipped_count, error_messages)
        """
        registered = 0
        skipped = 0
        errors = []

        for df in discovered_files:
            if df.is_registered:
                skipped += 1
                continue

            file_id = generate_file_id(df.s3_uri, customer_id)

            # Detect read number from filename
            read_number = 1
            if "_R2" in df.key or "_2.fastq" in df.key or "_2.fq" in df.key:
                read_number = 2

            registration = FileRegistration(
                file_id=file_id,
                customer_id=customer_id,
                file_metadata=FileMetadata(
                    file_id=file_id,
                    s3_uri=df.s3_uri,
                    file_size_bytes=df.file_size_bytes,
                    md5_checksum=df.etag,  # ETag is often MD5 for single-part uploads
                    file_format=df.detected_format,
                ),
                sequencing_metadata=SequencingMetadata(
                    platform=sequencing_platform,
                ),
                biosample_metadata=BiosampleMetadata(
                    biosample_id=biosample_id,
                    subject_id=subject_id,
                ),
                read_number=read_number,
            )

            try:
                if registry.register_file(registration):
                    registered += 1
                    df.is_registered = True
                    df.file_id = file_id
                else:
                    skipped += 1
            except Exception as e:
                errors.append(f"Failed to register {df.s3_uri}: {str(e)}")

        LOGGER.info(
            "Auto-registration complete: %d registered, %d skipped, %d errors",
            registered, skipped, len(errors)
        )
        return registered, skipped, errors
