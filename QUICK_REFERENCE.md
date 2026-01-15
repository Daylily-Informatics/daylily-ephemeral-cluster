# Quick Reference: POST /portal/files/register

## Endpoint Status
- **Path**: `POST /portal/files/register`
- **Status**: ✅ Frontend Ready | ❌ Backend Pending
- **Purpose**: Register multiple files discovered from S3 buckets

---

## User Journey

```
1. User navigates to /portal/files/buckets
2. Discovers files in linked S3 bucket
3. Clicks "Register Selected" button
4. Redirected to /portal/files/register
5. Auto-Discover tab shows discovered files
6. User selects files and provides metadata
7. Clicks "Register Selected Files"
8. POST /portal/files/register is called
9. Files are registered in system
```

---

## Request Format

```json
POST /portal/files/register
Content-Type: application/json

{
  "customer_id": "cust-001",
  "subject_id": "HG002",
  "biosample_id": "SAMPLE-001",
  "files": [
    {
      "s3_uri": "s3://bucket/file.fastq.gz",
      "key": "file.fastq.gz",
      "file_size_bytes": 1024000,
      "detected_format": "fastq",
      "last_modified": "2024-01-15T00:00:00Z",
      "etag": "abc123",
      "read_number": 1
    }
  ]
}
```

---

## Response Format

```json
{
  "registered": [
    {
      "file_id": "file-abc123",
      "s3_uri": "s3://bucket/file.fastq.gz",
      "status": "registered"
    }
  ],
  "skipped": [
    {
      "s3_uri": "s3://bucket/existing.fastq.gz",
      "reason": "Already registered"
    }
  ],
  "errors": [
    {
      "s3_uri": "s3://bucket/invalid.txt",
      "error": "Unsupported file format"
    }
  ]
}
```

---

## Frontend Code

**File**: `static/js/file-registry.js` (lines 554-626)

**Function**: `registerSelectedDiscoveredFiles()`

**Trigger**: Click "Register Selected Files" button

---

## Backend Implementation Checklist

- [ ] Create request model: `RegisterSelectedFilesRequest`
- [ ] Create response model: `BulkRegistrationResponse`
- [ ] Add POST handler to portal app
- [ ] Validate customer_id, subject_id, biosample_id
- [ ] Loop through files and register each
- [ ] Collect results (registered, skipped, errors)
- [ ] Return aggregated response
- [ ] Add error handling and logging
- [ ] Write integration tests
- [ ] Test end-to-end flow

---

## Related Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/files/register` | Register single file |
| `POST /api/files/auto-register` | Auto-register with defaults |
| `POST /api/files/bulk-import` | Import from CSV/TSV |
| `POST /api/files/buckets/{id}/discover` | Discover files |
| `POST /portal/files/register` | **Register selected discovered files** |

---

## Key Files

| File | Purpose |
|------|---------|
| `templates/files/buckets.html` | Bucket discovery UI |
| `templates/files/register.html` | Registration form |
| `static/js/file-registry.js` | Frontend logic |
| `daylib/file_api.py` | API router |
| `daylib/file_registry.py` | Business logic |
| `daylib/workset_api.py` | Portal app (add handler here) |

---

## Implementation Time Estimate

- **Backend Handler**: 1-2 hours
- **Tests**: 1-2 hours
- **Integration**: 30 minutes
- **Total**: 2-4 hours

---

## Questions?

See detailed documentation:
- `ENDPOINT_VERIFICATION_REPORT.md` - Full verification
- `ENDPOINT_IMPLEMENTATION_GUIDE.md` - How to implement
- `ENDPOINT_CODE_LOCATIONS.md` - Code locations

