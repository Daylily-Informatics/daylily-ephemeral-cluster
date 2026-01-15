"""
File Registry - DynamoDB-backed file registration system with GA4GH metadata.

Manages file registration, metadata capture, and file set grouping for the
Daylily portal's file management system.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

LOGGER = logging.getLogger("daylily.file_registry")


@dataclass
class FileMetadata:
    """Technical metadata for a registered file."""
    file_id: str  # Unique identifier
    s3_uri: str  # Full S3 URI
    file_size_bytes: int
    md5_checksum: Optional[str] = None
    file_format: str = "fastq"  # fastq, bam, vcf, etc.
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


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
    registered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


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
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class FileRegistry:
    """DynamoDB-backed file registry for GA4GH-compliant metadata storage."""
    
    def __init__(
        self,
        files_table_name: str = "daylily-files",
        filesets_table_name: str = "daylily-filesets",
        region: str = "us-west-2",
        profile: Optional[str] = None,
    ):
        """Initialize file registry.
        
        Args:
            files_table_name: DynamoDB table for file registrations
            filesets_table_name: DynamoDB table for file sets
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
        self.files_table = self.dynamodb.Table(files_table_name)
        self.filesets_table = self.dynamodb.Table(filesets_table_name)
    
    def create_tables_if_not_exist(self) -> None:
        """Create DynamoDB tables for file registry."""
        self._create_files_table()
        self._create_filesets_table()
    
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
        try:
            response = self.files_table.get_item(Key={"file_id": file_id})
            if "Item" not in response:
                return None
            
            item = response["Item"]
            return self._item_to_registration(item)
        except ClientError as e:
            LOGGER.error("Failed to get file %s: %s", file_id, e)
            return None
    
    def list_customer_files(self, customer_id: str, limit: int = 100) -> List[FileRegistration]:
        """List all files for a customer."""
        try:
            response = self.files_table.query(
                IndexName="customer-id-index",
                KeyConditionExpression="customer_id = :cid",
                ExpressionAttributeValues={":cid": customer_id},
                Limit=limit,
            )
            
            registrations = []
            for item in response.get("Items", []):
                registrations.append(self._item_to_registration(item))
            return registrations
        except ClientError as e:
            LOGGER.error("Failed to list files for customer %s: %s", customer_id, e)
            return []
    
    def _item_to_registration(self, item: Dict[str, Any]) -> FileRegistration:
        """Convert DynamoDB item to FileRegistration."""
        file_meta = json.loads(item.get("file_metadata", "{}"))
        seq_meta = json.loads(item.get("sequencing_metadata", "{}"))
        bio_meta = json.loads(item.get("biosample_metadata", "{}"))
        
        return FileRegistration(
            file_id=item["file_id"],
            customer_id=item["customer_id"],
            file_metadata=FileMetadata(**file_meta),
            sequencing_metadata=SequencingMetadata(**seq_meta),
            biosample_metadata=BiosampleMetadata(**bio_meta),
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
            LOGGER.error("Failed to get fileset %s: %s", fileset_id, e)
            return None
    
    def list_customer_filesets(self, customer_id: str) -> List[FileSet]:
        """List all file sets for a customer."""
        try:
            response = self.filesets_table.query(
                IndexName="customer-id-index",
                KeyConditionExpression="customer_id = :cid",
                ExpressionAttributeValues={":cid": customer_id},
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
            LOGGER.error("Failed to list filesets for customer %s: %s", customer_id, e)
            return []

