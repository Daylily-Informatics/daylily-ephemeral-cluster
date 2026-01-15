# Daylily File Management System - Architecture

## System Overview

The file management system consists of 5 integrated layers:

```
┌─────────────────────────────────────────────────────────────┐
│                    REST API Layer                           │
│  POST /register  GET /list  POST /filesets  POST /bulk-import
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Data Models Layer                         │
│  FileMetadata  BiosampleMetadata  SequencingMetadata        │
│  FileRegistration  FileSet                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  File Registry Layer                        │
│  register_file()  get_file()  list_customer_files()         │
│  create_fileset()  get_fileset()                            │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                 DynamoDB Storage Layer                      │
│  Files Table  FileSets Table  Customer GSI                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer Details

### 1. REST API Layer (`daylib/file_api.py`)

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/files/register` | Register single file with metadata |
| GET | `/api/files/list` | List files for customer |
| POST | `/api/files/filesets` | Create file set grouping |
| POST | `/api/files/bulk-import` | Bulk import multiple files |

**Request/Response Models:**
- FileMetadataRequest/Response
- BiosampleMetadataRequest
- SequencingMetadataRequest
- FileRegistrationRequest/Response
- FileSetRequest/Response
- BulkImportRequest/Response

---

### 2. Data Models Layer (`daylib/file_metadata.py` + `daylib/file_registry.py`)

**GA4GH-Aligned Models:**

```
Subject
  ├─ subject_id: str
  └─ species: str

Biosample
  ├─ biosample_id: str
  ├─ subject_id: str
  ├─ sample_type: str
  ├─ tissue_type: str
  ├─ collection_date: str
  └─ preservation_method: str

SequencingLibrary
  ├─ library_id: str
  ├─ library_prep_kit: str
  └─ target_coverage: float

SequencingRun
  ├─ run_id: str
  ├─ platform: str
  ├─ flowcell_id: str
  └─ run_date: str

FASTQFile
  ├─ file_id: str
  ├─ s3_uri: str
  ├─ file_size_bytes: int
  ├─ md5_checksum: str
  ├─ read_number: int (1 or 2)
  └─ paired_with: str (optional)

AnalysisInput
  ├─ subject: Subject
  ├─ biosample: Biosample
  ├─ sequencing_library: SequencingLibrary
  ├─ sequencing_run: SequencingRun
  ├─ fastq_files: List[FASTQFile]
  └─ quality_metrics: Dict
```

---

### 3. File Registry Layer (`daylib/file_registry.py`)

**Core Operations:**

```python
# Register a file
registration = FileRegistration(...)
success = file_registry.register_file(registration)

# Retrieve a file
file_reg = file_registry.get_file(file_id, customer_id)

# List customer files
files = file_registry.list_customer_files(customer_id, limit=100)

# Create file set
fileset = FileSet(...)
success = file_registry.create_fileset(fileset)

# Retrieve file set
fileset = file_registry.get_fileset(fileset_id, customer_id)

# List customer filesets
filesets = file_registry.list_customer_filesets(customer_id)
```

---

### 4. DynamoDB Storage Layer

**Tables:**

1. **Files Table**
   - Partition Key: `file_id`
   - Sort Key: `customer_id`
   - GSI: `customer_id` (for customer queries)
   - Attributes: file_metadata, biosample_metadata, sequencing_metadata, etc.

2. **FileSets Table**
   - Partition Key: `fileset_id`
   - Sort Key: `customer_id`
   - GSI: `customer_id` (for customer queries)
   - Attributes: name, description, file_ids, metadata

---

### 5. File Metadata Module (`daylib/file_metadata.py`)

**Utilities:**

```python
# Parse FASTQ filename
metadata = parse_fastq_filename("sample_R1.fastq.gz")
# Returns: FASTQFile with read_number=1

# Pair R1/R2 files
pairs = pair_fastq_files([
    "sample_R1.fastq.gz",
    "sample_R2.fastq.gz"
])
# Returns: List of paired FASTQFile objects

# Generate TSV for pipeline
tsv_content = generate_stage_samples_tsv(
    analysis_inputs=[...],
    include_header=True
)
# Returns: 20-column stage_samples.tsv format
```

---

## Data Flow Examples

### Example 1: Register Single File

```
User Request
    ↓
POST /api/files/register
    ↓
FileRegistrationRequest (JSON)
    ↓
Pydantic Validation
    ↓
Create FileRegistration object
    ↓
file_registry.register_file()
    ↓
DynamoDB put_item()
    ↓
FileRegistrationResponse (JSON)
    ↓
HTTP 200 OK
```

### Example 2: Bulk Import with FileSet

```
User Request
    ↓
POST /api/files/bulk-import
    ↓
BulkImportRequest (JSON array)
    ↓
For each file:
  ├─ Create FileRegistration
  ├─ file_registry.register_file()
  └─ Collect file_ids
    ↓
Create FileSet with file_ids
    ↓
file_registry.create_fileset()
    ↓
DynamoDB put_item() (fileset)
    ↓
BulkImportResponse (stats + fileset_id)
    ↓
HTTP 200 OK
```

### Example 3: List Customer Files

```
User Request
    ↓
GET /api/files/list?customer_id=cust-001
    ↓
file_registry.list_customer_files()
    ↓
DynamoDB query() with GSI
    ↓
Return List[FileRegistration]
    ↓
Format response (file_id, s3_uri, biosample_id, etc.)
    ↓
HTTP 200 OK
```

---

## Integration with Daylily

### Workset Creation Flow

```
File Registration
    ↓
FileSet Creation
    ↓
Workset Submission
    ↓
generate_stage_samples_tsv()
    ↓
Pipeline Execution
```

### Customer Scoping

All operations are scoped to `customer_id`:
- Files are stored with customer_id
- Queries use GSI on customer_id
- Filesets are customer-specific

### S3 Integration

- Files referenced by S3 URI
- Bucket validation via existing S3BucketValidator
- File size and checksum stored in metadata

---

## Error Handling

| Scenario | HTTP Status | Response |
|----------|------------|----------|
| File already registered | 409 Conflict | Error message |
| File not found | 404 Not Found | Error message |
| Invalid request | 400 Bad Request | Validation errors |
| Server error | 500 Internal Server Error | Error message |
| Partial bulk import failure | 200 OK | Import stats with errors array |

---

## Security Considerations

- ✅ Customer scoping (all queries filtered by customer_id)
- ✅ Input validation (Pydantic models)
- ✅ Error handling (no sensitive data in errors)
- ✅ Logging (structured logging for audit trail)
- ⚠️ Authentication/Authorization (to be added in integration)

---

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Register file | O(1) | Single DynamoDB put |
| Get file | O(1) | Single DynamoDB get |
| List files | O(n) | Query with GSI, paginated |
| Create fileset | O(1) | Single DynamoDB put |
| Bulk import | O(n) | n put operations |

---

## Future Enhancements

1. **Metadata Search**
   - Add GSI on biosample_id, subject_id
   - Enable filtering by metadata fields

2. **GA4GH Schema Validation**
   - Validate against official GA4GH schemas
   - Phenopackets support

3. **Export Functionality**
   - Export files as GA4GH JSON
   - Generate metadata reports

4. **UI Components**
   - File registration form
   - Metadata capture interface
   - Bulk import CSV uploader

---

## Testing

All layers have comprehensive test coverage:

- **API Layer**: 8 tests (endpoints, error handling)
- **Data Models**: 25 tests (parsing, pairing, TSV generation)
- **Registry Layer**: 11 tests (CRUD operations)
- **Total**: 44 tests, 100% passing ✅

---

## Deployment

1. Create DynamoDB tables (automatic via `create_tables_if_not_exist()`)
2. Configure AWS credentials
3. Integrate API router into FastAPI app
4. Add authentication/authorization middleware
5. Deploy to production

See `COMPLETION_SUMMARY.md` for integration instructions.

