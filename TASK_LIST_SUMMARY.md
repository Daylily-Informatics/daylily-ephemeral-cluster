# UI Implementation Task List Summary

**Generated:** 2026-01-16  
**Total Tasks Created:** 27 implementation tasks + 12 testing tasks  
**Total Effort:** 115 hours over 4 weeks  
**Status:** Ready for team assignment and execution

---

## 📋 TASK STRUCTURE

```
Root: Current Task List
├── [/] Investigate/Triage/Understand (COMPLETED)
├── [ ] UI Assessment & Task Planning
├── [ ] PHASE 1: Critical Fixes (Week 1) - 40 hours
│   ├── 1.1 Fix S3 URI Uniqueness Bug
│   ├── 1.2 Implement Missing Backend Endpoints (8 endpoints)
│   └── 1.3 Implement Biospecimen Data Model
├── [ ] PHASE 2: High Priority Features (Week 2) - 30 hours
│   ├── 2.1 Account Security Features
│   ├── 2.2 Dashboard Enhancements
│   ├── 2.3 Fix Discover Files Button Redirect
│   └── 2.4 Rename Manifest Generator
├── [ ] PHASE 3: Medium Priority Features (Week 3) - 25 hours
│   ├── 3.1 Files Page Search & Filters
│   ├── 3.2 File Detail Page Features
│   ├── 3.3 Test Bulk Import Feature
│   └── 3.4 Test Auto-Discover Feature
├── [ ] PHASE 4: Polish & Documentation (Week 4) - 20 hours
│   ├── 4.1 Write UI Documentation
│   ├── 4.2 Implement Cost Calculation Formula
│   ├── 4.3 Add Column Mapping Help
│   └── 4.4 Test Reset Button
└── [ ] Testing & QA (Parallel with phases)
    ├── Test S3 URI Uniqueness
    ├── Test All Backend Endpoints
    ├── Test Biospecimen Hierarchy
    ├── Test Account Security
    ├── Test Dashboard Tiles
    ├── Test File Search & Filters
    ├── Test Bulk Import
    ├── Test Auto-Discover
    ├── Test File Detail Buttons
    ├── Test Fileset Operations
    ├── Test Manifest Generation
    └── Test Cost Calculation
```

---

## 🎯 QUICK REFERENCE BY PRIORITY

### PHASE 1: CRITICAL (Week 1) - 40 hours
**Blocks core functionality - must complete first**

1. **Fix S3 URI Uniqueness Bug** - MEDIUM effort
   - Issue: Files with same name in different directories fail silently
   - Action: Update FileRegistry to use s3_uri as primary key
   - Test: Register same filename in different directories

2. **Implement Missing Backend Endpoints** - HIGH effort
   - 8 critical endpoints needed for file operations
   - Endpoints: register, download, add-to-fileset, create-fileset, add-files, manifest, edit, discover
   - Test: Verify all endpoints return correct responses

3. **Implement Biospecimen Data Model** - HIGH effort
   - Add Biospecimen entity to hierarchy
   - Add 8+ new fields to data model
   - Update DynamoDB schema
   - Test: End-to-end hierarchy validation

---

### PHASE 2: HIGH PRIORITY (Week 2) - 30 hours
**Significantly affects user experience**

1. **Account Security Features** - MEDIUM effort
   - Password change functionality
   - API token generation/management
   - Location: templates/account.html

2. **Dashboard Enhancements** - LOW effort
   - Add Files tile (count, size)
   - Add Experiments tile
   - Add Costs tile (30-day breakdown)
   - Add processing activity graph

3. **Fix Discover Files Button** - LOW effort
   - Change redirect from modal to register page
   - Location: templates/files/buckets.html line 69-71

4. **Rename Manifest Generator** - LOW effort
   - "Analysis Manifest Generator" → "Workset Manifest Generator"
   - Update 3 locations

---

### PHASE 3: MEDIUM PRIORITY (Week 3) - 25 hours
**Nice-to-have features**

1. **Files Page Search & Filters** - MEDIUM effort
   - Advanced filter button
   - Search with filters (format, subject, biosample, date range)
   - Location: templates/files/index.html

2. **File Detail Page Features** - MEDIUM effort
   - View subject files
   - Find similar files
   - Add tag functionality
   - Location: templates/files/detail.html

3. **Test Bulk Import** - LOW effort
   - CSV/TSV import functionality
   - Location: templates/files/register.html lines 252-294

4. **Test Auto-Discover** - LOW effort
   - File discovery functionality
   - Location: templates/files/register.html lines 296-383

---

### PHASE 4: POLISH (Week 4) - 20 hours
**Final touches and documentation**

1. **Write UI Documentation** - MEDIUM effort
   - UI-specific user guide
   - Add support email link (John@dyly.bio)
   - Location: templates/docs.html

2. **Implement Cost Calculation** - LOW effort
   - Formula: (total_size / (total_size - (total_size * 0.98)))
   - Update Dashboard and usage page

3. **Add Column Mapping Help** - LOW effort
   - Help modal with descriptions
   - Location: templates/manifest_generator.html line 272-274

4. **Test Reset Button** - LOW effort
   - Verify resetForm() function
   - Location: templates/files/register.html line 244

---

## ✅ TESTING & QA (Parallel)

12 comprehensive test tasks covering:
- S3 URI uniqueness validation
- All 8 backend endpoints
- Biospecimen hierarchy end-to-end
- Account security features
- Dashboard tiles
- File search and filters
- Bulk import with various formats
- Auto-discover functionality
- File detail page buttons
- Fileset operations
- Manifest generation
- Cost calculation accuracy

---

## 📊 EFFORT BREAKDOWN

| Phase | Tasks | Effort | Timeline |
|-------|-------|--------|----------|
| Phase 1 | 3 | 40 hrs | Week 1 |
| Phase 2 | 4 | 30 hrs | Week 2 |
| Phase 3 | 4 | 25 hrs | Week 3 |
| Phase 4 | 4 | 20 hrs | Week 4 |
| Testing | 12 | Parallel | All weeks |
| **TOTAL** | **27** | **115 hrs** | **4 weeks** |

---

## 🚀 NEXT STEPS

1. **Review this task list** with your team
2. **Assign tasks** to developers based on expertise
3. **Start Phase 1** immediately (critical fixes)
4. **Set up testing framework** for QA tasks
5. **Schedule weekly check-ins** to track progress
6. **Adjust timeline** if needed based on team capacity

---

## 📚 REFERENCE DOCUMENTS

- **UI_ASSESSMENT_INDEX.md** - Overview of all assessment documents
- **UI_ASSESSMENT_EXECUTIVE_SUMMARY.md** - High-level status and risks
- **UI_IMPLEMENTATION_PRIORITIES.md** - Detailed priority breakdown
- **UI_DETAILED_BREAKDOWN.md** - Line-by-line feature analysis
- **UI_FEATURE_ASSESSMENT_REPORT.md** - Quick reference table

---

## ⚠️ CRITICAL NOTES

1. **S3 URI Bug is HIGH RISK** - Can cause data loss
2. **Backend endpoints are BLOCKING** - Many UI features depend on them
3. **Biospecimen model is COMPLEX** - Requires careful design
4. **Testing is ESSENTIAL** - Run tests after each phase
5. **Documentation is IMPORTANT** - Users need guidance

---

**Status:** ✅ Ready for team review and assignment  
**Last Updated:** 2026-01-16  
**Prepared By:** Augment Agent


