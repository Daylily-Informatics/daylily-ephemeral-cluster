"""
Tests for Biospecimen module - Subject, Biosample, and Library CRUD operations.
"""

from dataclasses import asdict
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from daylib.biospecimen import (
    BiospecimenRegistry,
    Subject,
    Biospecimen,
    Biosample,
    Library,
    generate_subject_id,
    generate_biospecimen_id,
    generate_biosample_id,
    generate_library_id,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB resource for biospecimen tests."""
    with patch("daylib.biospecimen.boto3.Session") as mock_session:
        mock_resource = MagicMock()
        mock_subjects_table = MagicMock()
        mock_biospecimens_table = MagicMock()
        mock_biosamples_table = MagicMock()
        mock_libraries_table = MagicMock()

        # Create table name to mock table mapping
        def get_table(name):
            if "subjects" in name:
                return mock_subjects_table
            elif "biospecimens" in name:
                return mock_biospecimens_table
            elif "biosamples" in name:
                return mock_biosamples_table
            elif "libraries" in name:
                return mock_libraries_table
            return MagicMock()

        mock_session.return_value.resource.return_value = mock_resource
        mock_resource.Table.side_effect = get_table

        yield {
            "session": mock_session,
            "resource": mock_resource,
            "subjects_table": mock_subjects_table,
            "biospecimens_table": mock_biospecimens_table,
            "biosamples_table": mock_biosamples_table,
            "libraries_table": mock_libraries_table,
        }


@pytest.fixture
def registry(mock_dynamodb):
    """Create a BiospecimenRegistry with mocked DynamoDB tables."""
    reg = BiospecimenRegistry(
        subjects_table_name="test-subjects",
        biospecimens_table_name="test-biospecimens",
        biosamples_table_name="test-biosamples",
        libraries_table_name="test-libraries",
        region="us-west-2",
    )
    return reg


@pytest.fixture
def sample_subject():
    """Create a sample subject for testing."""
    return Subject(
        subject_id=generate_subject_id("customer-123", "patient-001"),
        customer_id="customer-123",
        display_name="John Doe",
        sex="male",
        species="Homo sapiens",
        cohort="Study A",
        external_ids=["EXT-001", "EXT-002"],
        notes="Test subject",
        tags=["test", "sample"],
    )


@pytest.fixture
def sample_biospecimen(sample_subject):
    """Create a sample biospecimen for testing."""
    return Biospecimen(
        biospecimen_id=generate_biospecimen_id("customer-123", "biospecimen-001"),
        customer_id="customer-123",
        subject_id=sample_subject.subject_id,
        biospecimen_type="tissue",
        collection_date="2024-01-15",
        collection_method="biopsy",
        preservation_method="frozen",
        tissue_type="tumor",
        anatomical_site="lung",
        tumor_fraction=0.8,
        is_tumor=True,
        produced_date="2024-01-16",
        notes="Test biospecimen",
        tags=["test"],
    )


@pytest.fixture
def sample_biosample(sample_subject, sample_biospecimen):
    """Create a sample biosample for testing."""
    return Biosample(
        biosample_id=generate_biosample_id("customer-123", "biosample-001"),
        customer_id="customer-123",
        biospecimen_id=sample_biospecimen.biospecimen_id,
        subject_id=sample_subject.subject_id,
        sample_type="blood",
        tissue_type="peripheral blood",
        anatomical_site="arm",
        collection_date="2024-01-15",
        preservation_method="fresh",
        is_tumor=False,
        tags=["test"],
    )


@pytest.fixture
def sample_library(sample_biosample):
    """Create a sample library for testing."""
    return Library(
        library_id=generate_library_id("customer-123", "library-001"),
        customer_id="customer-123",
        biosample_id=sample_biosample.biosample_id,
        library_prep="pcr_free_wgs",
        library_kit="Illumina DNA Prep",
        target_coverage=30.0,
        protocol_id="PROT-001",
        tags=["wgs"],
    )


# =============================================================================
# ID Generation Tests
# =============================================================================

class TestIDGeneration:
    """Tests for ID generation functions."""

    def test_generate_subject_id_consistent(self):
        """Same inputs produce same subject ID."""
        id1 = generate_subject_id("cust-1", "patient-1")
        id2 = generate_subject_id("cust-1", "patient-1")
        assert id1 == id2
        assert id1.startswith("subj-")

    def test_generate_subject_id_unique(self):
        """Different inputs produce different IDs."""
        id1 = generate_subject_id("cust-1", "patient-1")
        id2 = generate_subject_id("cust-1", "patient-2")
        id3 = generate_subject_id("cust-2", "patient-1")
        assert id1 != id2
        assert id1 != id3
        assert id2 != id3

    def test_generate_biosample_id_format(self):
        """Biosample IDs have correct prefix."""
        bio_id = generate_biosample_id("cust-1", "sample-1")
        assert bio_id.startswith("bio-")
        assert len(bio_id) == 20  # "bio-" + 16 hex chars

    def test_generate_library_id_format(self):
        """Library IDs have correct prefix."""
        lib_id = generate_library_id("cust-1", "lib-1")
        assert lib_id.startswith("lib-")
        assert len(lib_id) == 20  # "lib-" + 16 hex chars


# =============================================================================
# Subject CRUD Tests
# =============================================================================

class TestSubjectCRUD:
    """Tests for Subject CRUD operations."""

    def test_create_subject_success(self, registry, mock_dynamodb, sample_subject):
        """Successfully create a new subject."""
        mock_table = mock_dynamodb["subjects_table"]
        mock_table.put_item.return_value = {}

        result = registry.create_subject(sample_subject)

        assert result is True
        mock_table.put_item.assert_called_once()

    def test_create_subject_duplicate_fails(self, registry, mock_dynamodb, sample_subject):
        """Creating duplicate subject returns False."""
        mock_table = mock_dynamodb["subjects_table"]
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Item exists"}},
            "PutItem"
        )

        result = registry.create_subject(sample_subject)

        assert result is False

    def test_get_subject_exists(self, registry, mock_dynamodb, sample_subject):
        """Retrieve an existing subject."""
        mock_table = mock_dynamodb["subjects_table"]
        # Return the subject as dict (simulating DynamoDB)
        item = asdict(sample_subject)
        mock_table.get_item.return_value = {"Item": item}

        fetched = registry.get_subject(sample_subject.subject_id)

        assert fetched is not None
        assert fetched.subject_id == sample_subject.subject_id
        assert fetched.customer_id == sample_subject.customer_id
        assert fetched.display_name == sample_subject.display_name
        assert fetched.sex == sample_subject.sex

    def test_get_subject_not_found(self, registry, mock_dynamodb):
        """Get non-existent subject returns None."""
        mock_table = mock_dynamodb["subjects_table"]
        mock_table.get_item.return_value = {}  # No Item key

        fetched = registry.get_subject("subj-nonexistent")

        assert fetched is None

    def test_get_subject_preserves_list_fields(self, registry, mock_dynamodb, sample_subject):
        """Verify external_ids and tags are preserved after roundtrip."""
        mock_table = mock_dynamodb["subjects_table"]
        item = asdict(sample_subject)
        mock_table.get_item.return_value = {"Item": item}

        fetched = registry.get_subject(sample_subject.subject_id)

        assert fetched.external_ids == sample_subject.external_ids
        assert fetched.tags == sample_subject.tags
        assert isinstance(fetched.external_ids, list)
        assert isinstance(fetched.tags, list)

    def test_create_subject_empty_lists(self, registry, mock_dynamodb):
        """Create subject with empty lists for external_ids and tags."""
        mock_table = mock_dynamodb["subjects_table"]
        mock_table.put_item.return_value = {}

        subject = Subject(
            subject_id=generate_subject_id("cust-1", "empty-lists"),
            customer_id="cust-1",
            display_name="Empty Lists Subject",
        )
        result = registry.create_subject(subject)

        assert result is True
        # Verify put_item was called with lists in the item
        call_args = mock_table.put_item.call_args
        item = call_args.kwargs.get("Item") or call_args[1].get("Item")
        assert item["external_ids"] == []
        assert item["tags"] == []

    def test_update_subject_success(self, registry, mock_dynamodb, sample_subject):
        """Successfully update a subject."""
        mock_table = mock_dynamodb["subjects_table"]
        mock_table.put_item.return_value = {}

        sample_subject.display_name = "Jane Doe"
        sample_subject.sex = "female"
        sample_subject.notes = "Updated notes"

        result = registry.update_subject(sample_subject)

        assert result is True
        mock_table.put_item.assert_called_once()

    def test_list_subjects_by_customer(self, registry, mock_dynamodb):
        """List subjects filtered by customer_id."""
        mock_table = mock_dynamodb["subjects_table"]

        # Create test subjects
        subj1 = Subject(
            subject_id=generate_subject_id("cust-1", "patient-1"),
            customer_id="cust-1",
            display_name="Patient 1",
        )
        subj2 = Subject(
            subject_id=generate_subject_id("cust-1", "patient-2"),
            customer_id="cust-1",
            display_name="Patient 2",
        )

        # Mock query to return 2 subjects for cust-1
        mock_table.query.return_value = {
            "Items": [asdict(subj1), asdict(subj2)]
        }

        cust1_subjects = registry.list_subjects("cust-1")

        assert len(cust1_subjects) == 2
        mock_table.query.assert_called_once()

    def test_list_subjects_limit(self, registry, mock_dynamodb):
        """Test listing subjects with limit."""
        mock_table = mock_dynamodb["subjects_table"]

        # Create test subjects
        subjects = [
            Subject(
                subject_id=generate_subject_id("cust-1", f"patient-{i}"),
                customer_id="cust-1",
                display_name=f"Patient {i}",
            )
            for i in range(3)
        ]

        mock_table.query.return_value = {
            "Items": [asdict(s) for s in subjects]
        }

        limited = registry.list_subjects("cust-1", limit=3)

        assert len(limited) == 3
        # Verify limit was passed
        call_kwargs = mock_table.query.call_args.kwargs
        assert call_kwargs.get("Limit") == 3



# =============================================================================
# Biosample CRUD Tests
# =============================================================================

class TestBiosampleCRUD:
    """Tests for Biosample CRUD operations."""

    def test_create_biosample_success(self, registry, mock_dynamodb, sample_biosample):
        """Successfully create a new biosample."""
        mock_table = mock_dynamodb["biosamples_table"]
        mock_table.put_item.return_value = {}

        result = registry.create_biosample(sample_biosample)

        assert result is True
        mock_table.put_item.assert_called_once()

    def test_create_biosample_duplicate_fails(self, registry, mock_dynamodb, sample_biosample):
        """Creating duplicate biosample returns False."""
        mock_table = mock_dynamodb["biosamples_table"]
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Item exists"}},
            "PutItem"
        )

        result = registry.create_biosample(sample_biosample)

        assert result is False

    def test_get_biosample_exists(self, registry, mock_dynamodb, sample_biosample):
        """Retrieve an existing biosample."""
        mock_table = mock_dynamodb["biosamples_table"]
        item = asdict(sample_biosample)
        mock_table.get_item.return_value = {"Item": item}

        fetched = registry.get_biosample(sample_biosample.biosample_id)

        assert fetched is not None
        assert fetched.biosample_id == sample_biosample.biosample_id
        assert fetched.subject_id == sample_biosample.subject_id
        assert fetched.sample_type == sample_biosample.sample_type

    def test_get_biosample_not_found(self, registry, mock_dynamodb):
        """Get non-existent biosample returns None."""
        mock_table = mock_dynamodb["biosamples_table"]
        mock_table.get_item.return_value = {}

        fetched = registry.get_biosample("bio-nonexistent")

        assert fetched is None

    def test_list_biosamples_for_subject(self, registry, mock_dynamodb, sample_subject, sample_biospecimen):
        """List biosamples for a specific subject."""
        mock_table = mock_dynamodb["biosamples_table"]

        # Create test biosamples
        biosamples = [
            Biosample(
                biosample_id=generate_biosample_id("customer-123", f"bio-{i}"),
                customer_id="customer-123",
                biospecimen_id=sample_biospecimen.biospecimen_id,
                subject_id=sample_subject.subject_id,
                sample_type="blood",
            )
            for i in range(3)
        ]

        mock_table.query.return_value = {
            "Items": [asdict(b) for b in biosamples]
        }

        result = registry.list_biosamples_for_subject(sample_subject.subject_id)

        assert len(result) == 3
        for bio in result:
            assert bio.subject_id == sample_subject.subject_id

    def test_update_biosample_tumor_info(self, registry, mock_dynamodb, sample_biosample):
        """Update biosample with tumor-specific information."""
        mock_table = mock_dynamodb["biosamples_table"]
        mock_table.put_item.return_value = {}

        sample_biosample.is_tumor = True
        sample_biosample.tumor_fraction = 0.65
        sample_biosample.tumor_grade = "Grade II"

        result = registry.update_biosample(sample_biosample)

        assert result is True
        mock_table.put_item.assert_called_once()
        # Verify the item contains tumor info
        call_args = mock_table.put_item.call_args
        item = call_args.kwargs.get("Item") or call_args[1].get("Item")
        assert item["is_tumor"] is True
        assert item["tumor_fraction"] == 0.65
        assert item["tumor_grade"] == "Grade II"


# =============================================================================
# Library CRUD Tests
# =============================================================================

class TestLibraryCRUD:
    """Tests for Library CRUD operations."""

    def test_create_library_success(self, registry, mock_dynamodb, sample_library):
        """Successfully create a new library."""
        mock_table = mock_dynamodb["libraries_table"]
        mock_table.put_item.return_value = {}

        result = registry.create_library(sample_library)

        assert result is True
        mock_table.put_item.assert_called_once()

    def test_create_library_duplicate_fails(self, registry, mock_dynamodb, sample_library):
        """Creating duplicate library returns False."""
        mock_table = mock_dynamodb["libraries_table"]
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Item exists"}},
            "PutItem"
        )

        result = registry.create_library(sample_library)

        assert result is False

    def test_get_library_exists(self, registry, mock_dynamodb, sample_library):
        """Retrieve an existing library."""
        mock_table = mock_dynamodb["libraries_table"]
        item = asdict(sample_library)
        mock_table.get_item.return_value = {"Item": item}

        fetched = registry.get_library(sample_library.library_id)

        assert fetched is not None
        assert fetched.library_id == sample_library.library_id
        assert fetched.biosample_id == sample_library.biosample_id
        assert fetched.library_prep == sample_library.library_prep

    def test_list_libraries_for_biosample(self, registry, mock_dynamodb, sample_biosample):
        """List libraries for a specific biosample."""
        mock_table = mock_dynamodb["libraries_table"]

        # Create test libraries
        libraries = [
            Library(
                library_id=generate_library_id("customer-123", f"lib-{i}"),
                customer_id="customer-123",
                biosample_id=sample_biosample.biosample_id,
                library_prep="pcr_free_wgs",
            )
            for i in range(2)
        ]

        mock_table.query.return_value = {
            "Items": [asdict(lib) for lib in libraries]
        }

        result = registry.list_libraries_for_biosample(sample_biosample.biosample_id)

        assert len(result) == 2
        for lib in result:
            assert lib.biosample_id == sample_biosample.biosample_id


# =============================================================================
# Hierarchy Tests
# =============================================================================

class TestHierarchy:
    """Tests for hierarchy queries."""

    def test_get_subject_hierarchy_complete(
        self, registry, mock_dynamodb, sample_subject, sample_biospecimen, sample_biosample, sample_library
    ):
        """Get complete hierarchy for a subject."""
        subjects_table = mock_dynamodb["subjects_table"]
        biospecimens_table = mock_dynamodb.get("biospecimens_table", MagicMock())
        biosamples_table = mock_dynamodb["biosamples_table"]
        libraries_table = mock_dynamodb["libraries_table"]

        # Mock get_subject
        subjects_table.get_item.return_value = {"Item": asdict(sample_subject)}
        # Mock list_biospecimens_for_subject
        biospecimens_table.query.return_value = {"Items": [asdict(sample_biospecimen)]}
        # Mock list_biosamples_for_biospecimen
        biosamples_table.query.return_value = {"Items": [asdict(sample_biosample)]}
        # Mock list_libraries_for_biosample
        libraries_table.query.return_value = {"Items": [asdict(sample_library)]}

        hierarchy = registry.get_subject_hierarchy(sample_subject.subject_id)

        assert "subject" in hierarchy
        assert hierarchy["subject"]["subject_id"] == sample_subject.subject_id

        assert "biospecimens" in hierarchy
        assert len(hierarchy["biospecimens"]) == 1

        biospecimen_entry = hierarchy["biospecimens"][0]
        assert "biospecimen" in biospecimen_entry
        assert "biosamples" in biospecimen_entry
        assert len(biospecimen_entry["biosamples"]) == 1

        biosample_entry = biospecimen_entry["biosamples"][0]
        assert "biosample" in biosample_entry
        assert "libraries" in biosample_entry
        assert len(biosample_entry["libraries"]) == 1

    def test_get_subject_hierarchy_not_found(self, registry, mock_dynamodb):
        """Get hierarchy for non-existent subject returns empty dict."""
        subjects_table = mock_dynamodb["subjects_table"]
        subjects_table.get_item.return_value = {}  # No Item

        hierarchy = registry.get_subject_hierarchy("subj-nonexistent")

        assert hierarchy == {}

    def test_get_statistics(
        self, registry, mock_dynamodb, sample_subject, sample_biospecimen, sample_biosample, sample_library
    ):
        """Get statistics for a customer."""
        subjects_table = mock_dynamodb["subjects_table"]
        biospecimens_table = mock_dynamodb["biospecimens_table"]
        biosamples_table = mock_dynamodb["biosamples_table"]
        libraries_table = mock_dynamodb["libraries_table"]

        # Mock query responses with Items (get_statistics uses list_* methods)
        subjects_table.query.return_value = {"Items": [asdict(sample_subject)]}
        biospecimens_table.query.return_value = {"Items": [asdict(sample_biospecimen)]}
        biosamples_table.query.return_value = {"Items": [asdict(sample_biosample)]}
        libraries_table.query.return_value = {"Items": [asdict(sample_library)]}

        stats = registry.get_statistics("customer-123")

        assert stats["subjects"] == 1
        assert stats["biospecimens"] == 1
        assert stats["biosamples"] == 1
        assert stats["libraries"] == 1

