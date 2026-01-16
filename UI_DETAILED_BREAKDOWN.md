# UI Features - Detailed Breakdown

## PAGE 1: Upload (`/portal/files/upload`)

### Feature 1.1: Cancel Upload Button
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/files/upload.html` line 115-117
- **Implementation:** Button exists with `cancelUpload()` function
- **Issue:** Needs testing to verify abort functionality works correctly
- **Code:** `<button class="btn btn-outline" id="cancel-upload-btn" onclick="cancelUpload()">`

### Feature 1.2: File Upload with Progress
- **Status:** ✅ COMPLETE
- **Location:** `templates/files/upload.html` lines 55-119
- **Implementation:** Full drag-drop, queue, progress tracking
- **Code Quality:** Well-implemented with AbortController for cancellation

---

## PAGE 2: Buckets (`/portal/files/buckets`)

### Feature 2.1: AWS Logo Link to S3 Console
- **Status:** ✅ COMPLETE
- **Location:** `templates/files/buckets.html` lines 46-49
- **Implementation:** Links to AWS S3 console with bucket name
- **Code:** `<a href="https://s3.console.aws.amazon.com/s3/buckets/{{ bucket.bucket_name }}?region={{ bucket.region or 'us-east-1' }}" target="_blank">`

### Feature 2.2: Link Bucket Button Navigation
- **Status:** ✅ COMPLETE
- **Location:** `templates/files/buckets.html` line 20-22
- **Implementation:** Opens modal with form
- **Code:** `<button class="btn btn-primary" onclick="showLinkBucketModal()">`

### Feature 2.3: Edit Button Navigation
- **Status:** ✅ COMPLETE
- **Location:** `templates/files/buckets.html` line 72-74
- **Implementation:** Opens edit modal with bucket details
- **Code:** `<button class="btn btn-sm btn-outline" onclick="editBucket('{{ bucket.bucket_id }}')">`

### Feature 2.4: Discover Files Button
- **Status:** ❌ NOT STARTED (NEEDS CHANGE)
- **Location:** `templates/files/buckets.html` line 69-71
- **Current:** Opens discover modal in bucket manager
- **Required:** Should redirect to `/portal/files/register?bucket_id={id}&tab=discover`
- **Code:** Currently calls `discoverFiles()` - needs to redirect instead

### Feature 2.5: Bucket Validation & Remediation
- **Status:** ✅ COMPLETE
- **Location:** `templates/files/buckets.html` lines 94-121
- **Implementation:** Shows validation checks and remediation steps

---

## PAGE 3: Files Index (`/portal/files`)

### Feature 3.1: Advanced Button with Filters
- **Status:** ❌ NOT STARTED
- **Location:** `templates/files/index.html` (not shown in view)
- **Required:** Button should open filter panel
- **Missing:** Filter UI, filter logic

### Feature 3.2: Search with Filters
- **Status:** ❌ NOT STARTED
- **Location:** `templates/files/index.html`
- **Required:** Search input with filter options
- **Missing:** Search implementation, filter parameters

---

## PAGE 4: Register (`/portal/files/register`)

### Feature 4.1: Single File Registration
- **Status:** ✅ COMPLETE
- **Location:** `templates/files/register.html` lines 35-249
- **Implementation:** Full form with S3 URI, metadata, sequencing info
- **Code Quality:** Comprehensive with all required fields

### Feature 4.2: Paired File (R2) Support
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/files/register.html` lines 74-76
- **Implementation:** Input field exists
- **Issue:** Needs backend validation to confirm R1/R2 match

### Feature 4.3: Metadata Persistence
- **Status:** ⚠️ PARTIAL
- **Location:** Form fields exist but backend integration needed
- **Issue:** No confirmation that metadata is saved after creation

### Feature 4.4: Reset Button
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/files/register.html` line 244
- **Implementation:** Button exists with `resetForm()` function
- **Issue:** Function not shown in template - needs verification

### Feature 4.5: Bulk Import Tab
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/files/register.html` lines 252-294
- **Implementation:** CSV/TSV upload with preview
- **Issue:** Needs backend endpoint for bulk import

### Feature 4.6: Auto-Discover Tab
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/files/register.html` lines 296-383
- **Implementation:** Bucket selection, file type filters, metadata
- **Issue:** Needs backend discovery endpoint

---

## PAGE 5: Filesets (`/portal/files/filesets`)

### Feature 5.1: Create File Set Button
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/files/filesets.html` line 20-22
- **Implementation:** Button exists with `showCreateFilesetModal()`
- **Issue:** Modal implementation not shown

### Feature 5.2: File Selection in Form
- **Status:** ❌ NOT STARTED
- **Location:** Not implemented
- **Required:** Form to select registered files and add to fileset
- **Missing:** File selection UI, form submission

---

## PAGE 6: File Detail (`/portal/files/file-{id}`)

### Feature 6.1: Print S3 URI
- **Status:** ✅ COMPLETE
- **Location:** `templates/files/detail.html` lines 52-58
- **Implementation:** S3 URI displayed with copy button
- **Code:** `<code>{{ file.s3_uri }}</code>`

### Feature 6.2: Download Button
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/files/detail.html` line 31-33
- **Implementation:** Button exists
- **Issue:** Backend endpoint needed

### Feature 6.3: Use in Manifest
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/files/detail.html` line 37-39
- **Implementation:** Button exists
- **Issue:** Backend integration needed

### Feature 6.4: Add to File Set
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/files/detail.html` line 34-36
- **Implementation:** Button exists
- **Issue:** Backend integration needed

### Feature 6.5: Edit Metadata
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/files/detail.html` line 28-30
- **Implementation:** Button exists
- **Issue:** Backend integration needed

### Feature 6.6: View Subject Files
- **Status:** ❌ NOT STARTED
- **Location:** Not implemented
- **Required:** Show all files for a subject

---

## PAGE 7: Worksets/New (`/portal/worksets/new`)

### Feature 7.1: File Set Selection (Primary)
- **Status:** ✅ COMPLETE
- **Location:** `templates/worksets/new.html` lines 101-132
- **Implementation:** Dropdown with preview
- **Code Quality:** Well-structured with preview card

### Feature 7.2: Upload Files Tab
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/worksets/new.html` lines 134-150
- **Implementation:** Drag-drop zone exists
- **Issue:** Needs testing and backend integration

### Feature 7.3: S3 Path & Manifest Tabs
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/worksets/new.html` lines 84-98
- **Implementation:** Tabs exist
- **Issue:** Content needs refinement

---

## PAGE 8: Manifest Generator (`/portal/manifest-generator`)

### Feature 8.1: Analysis Inputs Form
- **Status:** ✅ COMPLETE
- **Location:** `templates/manifest_generator.html` lines 37-69
- **Implementation:** Add/remove inputs, preview
- **Code Quality:** Good structure

### Feature 8.2: Download Template
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/manifest_generator.html` line 61-63
- **Implementation:** Button exists
- **Issue:** Endpoint `/api/files/manifest/template` needs verification

### Feature 8.3: Column Mapping Help
- **Status:** ⚠️ PARTIAL
- **Location:** `templates/manifest_generator.html` line 272-274
- **Implementation:** Button exists
- **Issue:** No help content shown

### Feature 8.4: Rename to "Workset Manifest Generator"
- **Status:** ❌ NOT STARTED
- **Location:** `templates/manifest_generator.html` line 4, 10
- **Current:** "Analysis Manifest Generator"
- **Required:** Change title and references

---

## PAGE 9: Dashboard (`/portal`)

### Feature 9.1: Status Tiles (Worksets)
- **Status:** ✅ COMPLETE
- **Location:** `templates/dashboard.html` lines 15-64
- **Implementation:** 5 tiles with clickable links
- **Tiles:** In Progress, Ready, Completed, Errors, Cost

### Feature 9.2: Files Tile
- **Status:** ⚠️ PARTIAL
- **Location:** Not shown in current dashboard
- **Required:** Registered files count, total size
- **Missing:** Implementation

---

## PAGE 10: Account (`/portal/account`)

### Feature 10.1: Change Password
- **Status:** ❌ NOT STARTED
- **Location:** `templates/account.html` line 94-96
- **Implementation:** Button exists but no functionality
- **Issue:** No modal or form implementation

### Feature 10.2: API Token Generation
- **Status:** ❌ NOT STARTED
- **Location:** `templates/account.html` line 99-100
- **Implementation:** Section exists but no functionality
- **Issue:** No token generation UI

---

## PAGE 11: Docs (`/portal/docs`)

### Feature 11.1: UI-Specific Documentation
- **Status:** ❌ NOT STARTED
- **Location:** `templates/docs.html`
- **Required:** User guide for portal features

### Feature 11.2: Contact Support Email
- **Status:** ❌ NOT STARTED
- **Location:** Not implemented
- **Required:** Link to John@dyly.bio

---

## CRITICAL ISSUES SUMMARY

1. **S3 URI Uniqueness** - Files with same name in different directories fail silently
2. **Missing Biospecimen Entity** - Data model incomplete
3. **Backend Endpoints** - Many buttons exist but lack backend implementation
4. **Cost Calculation** - Formula not implemented
5. **Account Security** - Password change and API tokens not implemented


