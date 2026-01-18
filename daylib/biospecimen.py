"""
Biospecimen Layer - DynamoDB-backed entities for the Subject → Biospecimen → Biosample → Library hierarchy.

This module implements the GA4GH-aligned data model for tracking biological specimens
and their relationship to sequencing data.

Hierarchy:
    Subject (Patient/Individual)
      └── Biospecimen (Collection/batch of biological material)
           └── Biosample (Individual sample/aliquot)
                └── Library (Sequencing library prep)
                     └── Files (FASTQ/BAM/etc)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    """Return current UTC time in ISO format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

LOGGER = logging.getLogger("daylily.biospecimen")


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Subject:
    """
    A subject/individual from whom biosamples are collected.
    Maps to GA4GH Individual concept.
    """
    subject_id: str  # Primary key
    customer_id: str  # Partition for multi-tenant

    # Demographics
    display_name: Optional[str] = None  # Human-readable name/label
    sex: Optional[str] = None  # male, female, unknown, other
    date_of_birth: Optional[str] = None  # ISO date
    species: str = "Homo sapiens"

    # Clinical/study info
    cohort: Optional[str] = None  # Study or cohort name
    external_ids: List[str] = field(default_factory=list)  # External system IDs

    # Metadata
    notes: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)


@dataclass
class Biospecimen:
    """
    A collection/batch of biological material from a Subject.
    Represents a collection event or batch of material.
    """
    biospecimen_id: str  # Primary key
    customer_id: str
    subject_id: str  # Foreign key to Subject

    # Biospecimen characteristics
    biospecimen_type: str = "tissue"  # tissue, blood, saliva, cfDNA, organoid, etc.

    # Collection info
    collection_date: Optional[str] = None  # ISO date
    collection_method: Optional[str] = None
    preservation_method: Optional[str] = None  # fresh, frozen, ffpe

    # Tissue-specific
    tissue_type: Optional[str] = None  # More specific tissue description
    anatomical_site: Optional[str] = None  # Where sample was collected

    # Tumor-specific
    tumor_fraction: Optional[float] = None
    is_tumor: bool = False

    # Production/processing
    produced_date: Optional[str] = None  # ISO date when biospecimen was produced

    # Metadata
    notes: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)


@dataclass
class Biosample:
    """
    A physical specimen/aliquot derived from a Biospecimen.
    Maps to GA4GH Biosample concept.
    """
    biosample_id: str  # Primary key
    customer_id: str
    biospecimen_id: str  # Foreign key to Biospecimen
    subject_id: str  # Denormalized for convenience (from Biospecimen)

    # Sample characteristics
    sample_type: str = "blood"  # blood, saliva, tissue, tumor, cfDNA, etc.
    tissue_type: Optional[str] = None  # More specific tissue description
    anatomical_site: Optional[str] = None  # Where sample was collected

    # Collection info
    collection_date: Optional[str] = None  # ISO date
    collection_method: Optional[str] = None
    preservation_method: Optional[str] = None  # fresh, frozen, ffpe

    # Tumor-specific
    tumor_fraction: Optional[float] = None
    tumor_grade: Optional[str] = None
    tumor_stage: Optional[str] = None
    is_tumor: bool = False
    matched_normal_id: Optional[str] = None  # Link to normal biosample for T/N pairs

    # Metadata
    notes: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)


@dataclass
class Library:
    """
    A sequencing library prepared from a Biosample.
    Represents a specific library prep that generates sequence data.
    """
    library_id: str  # Primary key
    customer_id: str
    biosample_id: str  # Foreign key to Biosample
    
    # Library prep info
    library_prep: str = "pcr_free_wgs"  # pcr_free_wgs, pcr_wgs, exome, rna_seq, etc.
    library_kit: Optional[str] = None  # e.g., "Illumina DNA Prep"
    target_insert_size: Optional[int] = None  # bp
    
    # Capture/enrichment (for targeted sequencing)
    capture_kit: Optional[str] = None
    target_regions_bed: Optional[str] = None  # S3 URI to BED file
    
    # Sequencing targets
    target_coverage: Optional[float] = None  # Target depth
    target_read_count: Optional[int] = None
    
    # Lab info
    protocol_id: Optional[str] = None
    lab_id: Optional[str] = None
    prep_date: Optional[str] = None
    
    # Metadata
    notes: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)


def generate_subject_id(customer_id: str, identifier: str) -> str:
    """Generate a unique subject ID."""
    hash_input = f"{customer_id}:subject:{identifier}"
    return f"subj-{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"


def generate_biospecimen_id(customer_id: str, identifier: str) -> str:
    """Generate a unique biospecimen ID."""
    hash_input = f"{customer_id}:biospecimen:{identifier}"
    return f"bspec-{hashlib.sha256(hash_input.encode()).hexdigest()[:12]}"


def generate_biosample_id(customer_id: str, identifier: str) -> str:
    """Generate a unique biosample ID."""
    hash_input = f"{customer_id}:biosample:{identifier}"
    return f"bio-{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"


def generate_library_id(customer_id: str, identifier: str) -> str:
    """Generate a unique library ID."""
    hash_input = f"{customer_id}:library:{identifier}"
    return f"lib-{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"


# =============================================================================
# BiospecimenRegistry - DynamoDB Manager
# =============================================================================

class BiospecimenRegistry:
    """
    DynamoDB-backed registry for Subject, Biospecimen, Biosample, and Library entities.
    """

    def __init__(
        self,
        subjects_table_name: str = "daylily-subjects",
        biospecimens_table_name: str = "daylily-biospecimens",
        biosamples_table_name: str = "daylily-biosamples",
        libraries_table_name: str = "daylily-libraries",
        region: str = "us-west-2",
        profile: Optional[str] = None,
    ):
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self.dynamodb = session.resource("dynamodb")

        self.subjects_table_name = subjects_table_name
        self.biospecimens_table_name = biospecimens_table_name
        self.biosamples_table_name = biosamples_table_name
        self.libraries_table_name = libraries_table_name

        self.subjects_table = self.dynamodb.Table(subjects_table_name)
        self.biospecimens_table = self.dynamodb.Table(biospecimens_table_name)
        self.biosamples_table = self.dynamodb.Table(biosamples_table_name)
        self.libraries_table = self.dynamodb.Table(libraries_table_name)

    def create_tables_if_not_exist(self) -> None:
        """Create all biospecimen tables if they don't exist."""
        self._create_subjects_table()
        self._create_biospecimens_table()
        self._create_biosamples_table()
        self._create_libraries_table()

    def _create_subjects_table(self) -> None:
        """Create subjects table."""
        try:
            self.dynamodb.meta.client.describe_table(TableName=self.subjects_table_name)
            LOGGER.info("Subjects table %s already exists", self.subjects_table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        LOGGER.info("Creating subjects table %s", self.subjects_table_name)
        table = self.dynamodb.create_table(
            TableName=self.subjects_table_name,
            KeySchema=[
                {"AttributeName": "subject_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "subject_id", "AttributeType": "S"},
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
        LOGGER.info("Subjects table created successfully")

    def _create_biospecimens_table(self) -> None:
        """Create biospecimens table."""
        try:
            self.dynamodb.meta.client.describe_table(TableName=self.biospecimens_table_name)
            LOGGER.info("Biospecimens table %s already exists", self.biospecimens_table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        LOGGER.info("Creating biospecimens table %s", self.biospecimens_table_name)
        table = self.dynamodb.create_table(
            TableName=self.biospecimens_table_name,
            KeySchema=[
                {"AttributeName": "biospecimen_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "biospecimen_id", "AttributeType": "S"},
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "subject_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "customer-id-index",
                    "KeySchema": [
                        {"AttributeName": "customer_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "subject-id-index",
                    "KeySchema": [
                        {"AttributeName": "subject_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        LOGGER.info("Biospecimens table created successfully")

    def _create_biosamples_table(self) -> None:
        """Create biosamples table."""
        try:
            self.dynamodb.meta.client.describe_table(TableName=self.biosamples_table_name)
            LOGGER.info("Biosamples table %s already exists", self.biosamples_table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        LOGGER.info("Creating biosamples table %s", self.biosamples_table_name)
        table = self.dynamodb.create_table(
            TableName=self.biosamples_table_name,
            KeySchema=[
                {"AttributeName": "biosample_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "biosample_id", "AttributeType": "S"},
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "biospecimen_id", "AttributeType": "S"},
                {"AttributeName": "subject_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "customer-id-index",
                    "KeySchema": [
                        {"AttributeName": "customer_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "biospecimen-id-index",
                    "KeySchema": [
                        {"AttributeName": "biospecimen_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "subject-id-index",
                    "KeySchema": [
                        {"AttributeName": "subject_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        LOGGER.info("Biosamples table created successfully")

    def _create_libraries_table(self) -> None:
        """Create libraries table."""
        try:
            self.dynamodb.meta.client.describe_table(TableName=self.libraries_table_name)
            LOGGER.info("Libraries table %s already exists", self.libraries_table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        LOGGER.info("Creating libraries table %s", self.libraries_table_name)
        table = self.dynamodb.create_table(
            TableName=self.libraries_table_name,
            KeySchema=[
                {"AttributeName": "library_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "library_id", "AttributeType": "S"},
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "biosample_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "customer-id-index",
                    "KeySchema": [
                        {"AttributeName": "customer_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "biosample-id-index",
                    "KeySchema": [
                        {"AttributeName": "biosample_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        LOGGER.info("Libraries table created successfully")

    # =========================================================================
    # Subject CRUD Operations
    # =========================================================================

    def create_subject(self, subject: Subject) -> bool:
        """Create a new subject. Returns True if created, False if already exists."""
        item = asdict(subject)
        # Remove None values
        item = {k: v for k, v in item.items() if v is not None}

        try:
            self.subjects_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(subject_id)",
            )
            LOGGER.info("Created subject %s", subject.subject_id)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.warning("Subject %s already exists", subject.subject_id)
                return False
            raise

    def get_subject(self, subject_id: str) -> Optional[Subject]:
        """Retrieve a subject by ID."""
        try:
            response = self.subjects_table.get_item(Key={"subject_id": subject_id})
            if "Item" not in response:
                return None
            return Subject(**response["Item"])
        except ClientError:
            LOGGER.exception("Error getting subject %s", subject_id)
            return None

    def update_subject(self, subject: Subject) -> bool:
        """Update an existing subject."""
        subject.updated_at = _utc_now_iso()
        item = asdict(subject)
        item = {k: v for k, v in item.items() if v is not None}

        try:
            self.subjects_table.put_item(Item=item)
            LOGGER.info("Updated subject %s", subject.subject_id)
            return True
        except ClientError:
            LOGGER.exception("Error updating subject %s", subject.subject_id)
            return False

    def list_subjects(self, customer_id: str, limit: int = 100) -> List[Subject]:
        """List all subjects for a customer."""
        try:
            response = self.subjects_table.query(
                IndexName="customer-id-index",
                KeyConditionExpression=Key("customer_id").eq(customer_id),
                Limit=limit,
            )
            return [Subject(**item) for item in response.get("Items", [])]
        except ClientError:
            LOGGER.exception("Error listing subjects for customer %s", customer_id)
            return []

    # =========================================================================
    # Biospecimen CRUD Operations
    # =========================================================================

    def create_biospecimen(self, biospecimen: Biospecimen) -> bool:
        """Create a new biospecimen. Returns True if created, False if already exists."""
        item = asdict(biospecimen)
        item = {k: v for k, v in item.items() if v is not None}

        try:
            self.biospecimens_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(biospecimen_id)",
            )
            LOGGER.info("Created biospecimen %s", biospecimen.biospecimen_id)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.warning("Biospecimen %s already exists", biospecimen.biospecimen_id)
                return False
            raise

    def get_biospecimen(self, biospecimen_id: str) -> Optional[Biospecimen]:
        """Retrieve a biospecimen by ID."""
        try:
            response = self.biospecimens_table.get_item(Key={"biospecimen_id": biospecimen_id})
            if "Item" not in response:
                return None
            return Biospecimen(**response["Item"])
        except ClientError:
            LOGGER.exception("Error getting biospecimen %s", biospecimen_id)
            return None

    def update_biospecimen(self, biospecimen: Biospecimen) -> bool:
        """Update an existing biospecimen."""
        biospecimen.updated_at = _utc_now_iso()
        item = asdict(biospecimen)
        item = {k: v for k, v in item.items() if v is not None}

        try:
            self.biospecimens_table.put_item(Item=item)
            LOGGER.info("Updated biospecimen %s", biospecimen.biospecimen_id)
            return True
        except ClientError:
            LOGGER.exception("Error updating biospecimen %s", biospecimen.biospecimen_id)
            return False

    def list_biospecimens_for_subject(self, subject_id: str) -> List[Biospecimen]:
        """List all biospecimens for a subject."""
        try:
            response = self.biospecimens_table.query(
                IndexName="subject-id-index",
                KeyConditionExpression=Key("subject_id").eq(subject_id),
            )
            return [Biospecimen(**item) for item in response.get("Items", [])]
        except ClientError:
            LOGGER.exception("Error listing biospecimens for subject %s", subject_id)
            return []

    def list_biospecimens(self, customer_id: str, limit: int = 100) -> List[Biospecimen]:
        """List all biospecimens for a customer."""
        try:
            response = self.biospecimens_table.query(
                IndexName="customer-id-index",
                KeyConditionExpression=Key("customer_id").eq(customer_id),
                Limit=limit,
            )
            return [Biospecimen(**item) for item in response.get("Items", [])]
        except ClientError:
            LOGGER.exception("Error listing biospecimens for customer %s", customer_id)
            return []

    # =========================================================================
    # Biosample CRUD Operations
    # =========================================================================

    def create_biosample(self, biosample: Biosample) -> bool:
        """Create a new biosample. Returns True if created, False if already exists."""
        item = asdict(biosample)
        item = {k: v for k, v in item.items() if v is not None}

        try:
            self.biosamples_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(biosample_id)",
            )
            LOGGER.info("Created biosample %s", biosample.biosample_id)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.warning("Biosample %s already exists", biosample.biosample_id)
                return False
            raise

    def get_biosample(self, biosample_id: str) -> Optional[Biosample]:
        """Retrieve a biosample by ID."""
        try:
            response = self.biosamples_table.get_item(Key={"biosample_id": biosample_id})
            if "Item" not in response:
                return None
            return Biosample(**response["Item"])
        except ClientError:
            LOGGER.exception("Error getting biosample %s", biosample_id)
            return None

    def update_biosample(self, biosample: Biosample) -> bool:
        """Update an existing biosample."""
        biosample.updated_at = _utc_now_iso()
        item = asdict(biosample)
        item = {k: v for k, v in item.items() if v is not None}

        try:
            self.biosamples_table.put_item(Item=item)
            LOGGER.info("Updated biosample %s", biosample.biosample_id)
            return True
        except ClientError:
            LOGGER.exception("Error updating biosample %s", biosample.biosample_id)
            return False

    def list_biosamples(self, customer_id: str, limit: int = 100) -> List[Biosample]:
        """List all biosamples for a customer."""
        try:
            response = self.biosamples_table.query(
                IndexName="customer-id-index",
                KeyConditionExpression=Key("customer_id").eq(customer_id),
                Limit=limit,
            )
            return [Biosample(**item) for item in response.get("Items", [])]
        except ClientError:
            LOGGER.exception("Error listing biosamples for customer %s", customer_id)
            return []

    def list_biosamples_for_subject(self, subject_id: str) -> List[Biosample]:
        """List all biosamples for a specific subject."""
        try:
            response = self.biosamples_table.query(
                IndexName="subject-id-index",
                KeyConditionExpression=Key("subject_id").eq(subject_id),
            )
            return [Biosample(**item) for item in response.get("Items", [])]
        except ClientError:
            LOGGER.exception("Error listing biosamples for subject %s", subject_id)
            return []

    def list_biosamples_for_biospecimen(self, biospecimen_id: str) -> List[Biosample]:
        """List all biosamples for a specific biospecimen."""
        try:
            response = self.biosamples_table.query(
                IndexName="biospecimen-id-index",
                KeyConditionExpression=Key("biospecimen_id").eq(biospecimen_id),
            )
            return [Biosample(**item) for item in response.get("Items", [])]
        except ClientError:
            LOGGER.exception("Error listing biosamples for biospecimen %s", biospecimen_id)
            return []

    # =========================================================================
    # Library CRUD Operations
    # =========================================================================

    def create_library(self, library: Library) -> bool:
        """Create a new library. Returns True if created, False if already exists."""
        item = asdict(library)
        item = {k: v for k, v in item.items() if v is not None}

        try:
            self.libraries_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(library_id)",
            )
            LOGGER.info("Created library %s", library.library_id)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.warning("Library %s already exists", library.library_id)
                return False
            raise

    def get_library(self, library_id: str) -> Optional[Library]:
        """Retrieve a library by ID."""
        try:
            response = self.libraries_table.get_item(Key={"library_id": library_id})
            if "Item" not in response:
                return None
            return Library(**response["Item"])
        except ClientError:
            LOGGER.exception("Error getting library %s", library_id)
            return None

    def update_library(self, library: Library) -> bool:
        """Update an existing library."""
        library.updated_at = _utc_now_iso()
        item = asdict(library)
        item = {k: v for k, v in item.items() if v is not None}

        try:
            self.libraries_table.put_item(Item=item)
            LOGGER.info("Updated library %s", library.library_id)
            return True
        except ClientError:
            LOGGER.exception("Error updating library %s", library.library_id)
            return False

    def list_libraries(self, customer_id: str, limit: int = 100) -> List[Library]:
        """List all libraries for a customer."""
        try:
            response = self.libraries_table.query(
                IndexName="customer-id-index",
                KeyConditionExpression=Key("customer_id").eq(customer_id),
                Limit=limit,
            )
            return [Library(**item) for item in response.get("Items", [])]
        except ClientError:
            LOGGER.exception("Error listing libraries for customer %s", customer_id)
            return []

    def list_libraries_for_biosample(self, biosample_id: str) -> List[Library]:
        """List all libraries for a specific biosample."""
        try:
            response = self.libraries_table.query(
                IndexName="biosample-id-index",
                KeyConditionExpression=Key("biosample_id").eq(biosample_id),
            )
            return [Library(**item) for item in response.get("Items", [])]
        except ClientError:
            LOGGER.exception("Error listing libraries for biosample %s", biosample_id)
            return []

    # =========================================================================
    # Hierarchy Queries
    # =========================================================================

    def get_subject_hierarchy(self, subject_id: str) -> Dict[str, Any]:
        """
        Get complete hierarchy for a subject including all biospecimens, biosamples, and libraries.
        Returns a nested dictionary structure: Subject → Biospecimen → Biosample → Library
        """
        subject = self.get_subject(subject_id)
        if not subject:
            return {}

        biospecimens = self.list_biospecimens_for_subject(subject_id)

        biospecimens_list: List[Dict[str, Any]] = []
        hierarchy: Dict[str, Any] = {
            "subject": asdict(subject),
            "biospecimens": biospecimens_list
        }

        for biospecimen in biospecimens:
            biosamples = self.list_biosamples_for_biospecimen(biospecimen.biospecimen_id)
            biosamples_list: List[Dict[str, Any]] = []
            biospecimen_data: Dict[str, Any] = {
                "biospecimen": asdict(biospecimen),
                "biosamples": biosamples_list
            }

            for biosample in biosamples:
                libraries = self.list_libraries_for_biosample(biosample.biosample_id)
                biosamples_list.append({
                    "biosample": asdict(biosample),
                    "libraries": [asdict(lib) for lib in libraries]
                })

            biospecimens_list.append(biospecimen_data)

        return hierarchy

    def get_statistics(self, customer_id: str) -> Dict[str, int]:
        """Get counts of subjects, biospecimens, biosamples, and libraries for a customer."""
        subjects = self.list_subjects(customer_id, limit=1000)
        biospecimens = self.list_biospecimens(customer_id, limit=1000)
        biosamples = self.list_biosamples(customer_id, limit=1000)
        libraries = self.list_libraries(customer_id, limit=1000)

        return {
            "subjects": len(subjects),
            "biospecimens": len(biospecimens),
            "biosamples": len(biosamples),
            "libraries": len(libraries),
        }

