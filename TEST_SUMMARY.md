# File Metadata Update Tests - Comprehensive Test Suite

## Overview
Added 26 comprehensive tests for the file metadata update endpoint (`PATCH /api/files/{file_id}`) in `tests/test_file_api.py`.

## Test Coverage

### File Metadata Fields (3 tests)
- `test_update_file_metadata_md5_checksum` - Update MD5 checksum
- `test_update_file_metadata_file_format` - Update file format (fastq, bam, etc.)
- `test_update_file_metadata_multiple_fields` - Update multiple file metadata fields together

### Biosample Metadata Fields (4 tests)
- `test_update_biosample_metadata_biosample_id` - Update biosample ID
- `test_update_biosample_metadata_subject_id` - Update subject/individual ID
- `test_update_biosample_metadata_sample_type` - Update sample type (blood, tissue, etc.)
- `test_update_biosample_metadata_all_fields` - Update all biosample fields (includes tissue_type, collection_date, preservation_method, tumor_fraction)

### Sequencing Metadata Fields (8 tests)
- `test_update_sequencing_metadata_platform` - Update sequencing platform
- `test_update_sequencing_metadata_vendor` - Update sequencing vendor
- `test_update_sequencing_metadata_run_id` - Update run ID
- `test_update_sequencing_metadata_lane` - Update lane number
- `test_update_sequencing_metadata_barcode_id` - Update barcode ID
- `test_update_sequencing_metadata_flowcell_id` - Update flowcell ID
- `test_update_sequencing_metadata_run_date` - Update run date
- `test_update_sequencing_metadata_all_fields` - Update all sequencing metadata fields together

### Quality & Control Fields (6 tests)
- `test_update_read_number` - Update read number (1 or 2)
- `test_update_paired_with` - Update paired file reference
- `test_update_quality_score` - Update quality score
- `test_update_percent_q30` - Update percent Q30 bases
- `test_update_is_positive_control` - Update positive control flag
- `test_update_is_negative_control` - Update negative control flag

### Tags & Combined Updates (3 tests)
- `test_update_tags` - Update file tags
- `test_update_all_fields_together` - Update all metadata fields in single request
- `test_update_empty_payload` - Handle empty payload gracefully

### Error Handling (2 tests)
- `test_update_file_not_found` - Handle non-existent file (404)
- `test_update_file_failure` - Handle update failure (500)

## Test Results
✅ All 26 tests PASSED
✅ All 53 total tests in test_file_api.py PASSED (27 new + 26 existing)

## Running the Tests
```bash
# Run only the new update tests
pytest tests/test_file_api.py::TestUpdateFileMetadataEndpoint -v

# Run all file API tests
pytest tests/test_file_api.py -v
```

