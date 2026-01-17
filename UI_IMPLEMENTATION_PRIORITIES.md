# UI Implementation Priorities

**Assessment Date:** 2026-01-16  
**Total Features:** 36  
**Completion:** ~60% (UI exists, backend integration needed)

---

## PRIORITY 1: CRITICAL (Blocks Core Functionality)

### 1.1 Fix S3 URI Uniqueness Issue
- **Impact:** HIGH - Files silently fail to register
- **Effort:** MEDIUM
- **Location:** Backend file registration logic
- **Issue:** Using filename instead of full S3 URI as unique key
- **Action:** Update FileRegistry to use s3_uri as primary key
- **Tests Needed:** Test registering same filename in different directories

### 1.2 Implement Missing Backend Endpoints
- **Impact:** HIGH - Many UI buttons non-functional
- **Effort:** HIGH
- **Endpoints Needed:**
  - `POST /portal/files/register` - Bulk file registration
  - `GET /api/files/{id}/download` - File download
  - `POST /api/files/{id}/add-to-fileset` - Add to fileset
  - `POST /api/filesets/create` - Create fileset
  - `POST /api/filesets/{id}/add-files` - Add files to fileset
  - `POST /api/files/{id}/manifest` - Use in manifest
  - `PATCH /api/files/{id}` - Edit metadata
  - `POST /api/files/discover` - Auto-discover files

### 1.3 Implement Biospecimen Data Model
- **Impact:** HIGH - Required for proper data hierarchy
- **Effort:** HIGH
- **Current:** Subject → Biosample → Library
- **Required:** Subject → Biospecimen → Biosample → Library
- **Missing Fields:**
  - Biospecimen ID, Type, Collection, Preservation
  - Tissue Type, Tumor Fraction
  - BioSample Type, Produced Date
- **Action:** Add Biospecimen table to DynamoDB, update schemas

---

## PRIORITY 2: HIGH (Affects User Experience)

### 2.1 Account Security Features
- **Impact:** MEDIUM - Users can't manage accounts
- **Effort:** MEDIUM
- **Features:**
  - Change password functionality
  - API token generation and management
- **Location:** `templates/account.html`
- **Action:** Implement password change modal, token management UI

### 2.2 Dashboard Enhancements
- **Impact:** MEDIUM - Dashboard incomplete
- **Effort:** LOW
- **Missing:**
  - Files tile (registered count, total size)
  - Experiments tile (if applicable)
  - Costs tile with 30-day breakdown
  - Processing activity graph with 2 additional metrics
- **Action:** Add tiles and update dashboard template

### 2.3 Discover Files Button Redirect
- **Impact:** MEDIUM - User flow broken
- **Effort:** LOW
- **Location:** `templates/files/buckets.html` line 69-71
- **Current:** Opens modal in bucket manager
- **Required:** Redirect to `/portal/files/register?bucket_id={id}&tab=discover`
- **Action:** Change `discoverFiles()` to redirect

### 2.4 Rename Manifest Generator
- **Impact:** LOW - Naming clarity
- **Effort:** LOW
- **Change:** "Analysis Manifest Generator" → "Workset Manifest Generator" ✅ COMPLETE
- **Locations:**
  - `templates/manifest_generator.html` line 4, 10
  - `templates/base.html` navigation
  - Any references in code

---

## PRIORITY 3: MEDIUM (Nice to Have)

### 3.1 Files Page Search & Filters
- **Impact:** MEDIUM - Users can't filter files
- **Effort:** MEDIUM
- **Features:**
  - Advanced filter button
  - Search with filter options
  - Filter by: format, subject, biosample, date range
- **Location:** `templates/files/index.html`
- **Action:** Add filter UI and search logic

### 3.2 File Detail Page Features
- **Impact:** MEDIUM - Limited file management
- **Effort:** MEDIUM
- **Missing:**
  - View subject files
  - Find similar files
  - Add tag functionality
- **Location:** `templates/files/detail.html`
- **Action:** Implement these features with backend support

### 3.3 Bulk Import Testing
- **Impact:** MEDIUM - Feature exists but untested
- **Effort:** LOW
- **Location:** `templates/files/register.html` lines 252-294
- **Action:** Test CSV/TSV import, verify preview, test submission

### 3.4 Auto-Discover Testing
- **Impact:** MEDIUM - Feature exists but untested
- **Effort:** LOW
- **Location:** `templates/files/register.html` lines 296-383
- **Action:** Test discovery, file selection, registration

---

## PRIORITY 4: LOW (Polish)

### 4.1 Documentation
- **Impact:** LOW - Users need help
- **Effort:** MEDIUM
- **Missing:**
  - UI-specific documentation
  - Contact support email link (John@dyly.bio)
- **Location:** `templates/docs.html`
- **Action:** Write user guide, add support link

### 4.2 Cost Calculation Formula
- **Impact:** LOW - Cost display incomplete
- **Effort:** LOW
- **Formula:** `(total_size / (total_size - (total_size * 0.98)))`
- **Location:** Dashboard, usage page
- **Action:** Implement cost calculation

### 4.3 Column Mapping Help
- **Impact:** LOW - Users need guidance
- **Effort:** LOW
- **Location:** `templates/manifest_generator.html` line 272-274
- **Action:** Add help modal with column descriptions

### 4.4 Reset Button Testing
- **Impact:** LOW - Form reset
- **Effort:** LOW
- **Location:** `templates/files/register.html` line 244
- **Action:** Verify `resetForm()` function works

---

## IMPLEMENTATION ROADMAP

### Phase 1 (Week 1): Critical Fixes
1. Fix S3 URI uniqueness issue
2. Implement core backend endpoints
3. Add Biospecimen data model

### Phase 2 (Week 2): High Priority
1. Account security features
2. Dashboard enhancements
3. Discover button redirect
4. Manifest generator rename

### Phase 3 (Week 3): Medium Priority
1. Files search & filters
2. File detail features
3. Bulk import & auto-discover testing

### Phase 4 (Week 4): Polish
1. Documentation
2. Cost calculation
3. Help content
4. Testing & QA

---

## TESTING CHECKLIST

- [ ] S3 URI uniqueness with same filename in different directories
- [ ] All backend endpoints return correct responses
- [ ] Biospecimen hierarchy works end-to-end
- [ ] Password change functionality
- [ ] API token generation and revocation
- [ ] Dashboard tiles update correctly
- [ ] File search and filters work
- [ ] Bulk import with CSV/TSV
- [ ] Auto-discover file detection
- [ ] File detail page all buttons functional
- [ ] Fileset creation and file selection
- [ ] Manifest generation with all fields
- [ ] Cost calculation accuracy


