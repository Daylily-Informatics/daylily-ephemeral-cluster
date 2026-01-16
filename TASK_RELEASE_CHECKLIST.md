# Task Release Checklist

**Date:** 2026-01-16  
**Status:** Ready for team review and assignment

---

## ✅ ASSESSMENT COMPLETE

- [x] Reviewed all 11 UI pages
- [x] Assessed all 36 features
- [x] Identified 3 critical issues
- [x] Calculated effort estimates (115 hours)
- [x] Created 4 assessment documents
- [x] Organized 39 tasks into 4 phases
- [x] Created task list with full hierarchy
- [x] Generated summary documents

---

## 📚 DELIVERABLES CHECKLIST

### Assessment Documents
- [x] UI_ASSESSMENT_INDEX.md - Navigation guide
- [x] UI_ASSESSMENT_EXECUTIVE_SUMMARY.md - Executive overview
- [x] UI_IMPLEMENTATION_PRIORITIES.md - Detailed priorities
- [x] UI_DETAILED_BREAKDOWN.md - Line-by-line analysis
- [x] UI_FEATURE_ASSESSMENT_REPORT.md - Quick reference

### Task Management
- [x] Task list created with 39 tasks
- [x] Tasks organized in 4 phases
- [x] Testing tasks created (12 total)
- [x] Full task hierarchy established
- [x] TASK_LIST_SUMMARY.md - Task overview
- [x] READY_FOR_RELEASE.md - Release summary

---

## 🎯 PHASE 1 TASKS (Ready to Assign)

### Critical Fixes - Week 1 (40 hours)

**Task 1.1: Fix S3 URI Uniqueness Bug**
- [ ] Assign to developer
- [ ] Review FileRegistry code
- [ ] Update to use s3_uri as primary key
- [ ] Write unit tests
- [ ] Test with same filename in different directories
- [ ] Mark COMPLETE

**Task 1.2: Implement Missing Backend Endpoints**
- [ ] Assign to developer
- [ ] Implement POST /portal/files/register
- [ ] Implement GET /api/files/{id}/download
- [ ] Implement POST /api/files/{id}/add-to-fileset
- [ ] Implement POST /api/filesets/create
- [ ] Implement POST /api/filesets/{id}/add-files
- [ ] Implement POST /api/files/{id}/manifest
- [ ] Implement PATCH /api/files/{id}
- [ ] Implement POST /api/files/discover
- [ ] Write tests for all endpoints
- [ ] Mark COMPLETE

**Task 1.3: Implement Biospecimen Data Model**
- [ ] Assign to developer
- [ ] Design Biospecimen entity
- [ ] Add Biospecimen table to DynamoDB
- [ ] Update schemas
- [ ] Add all required fields
- [ ] Update hierarchy: Subject → Biospecimen → Biosample → Library
- [ ] Write migration script
- [ ] Test end-to-end
- [ ] Mark COMPLETE

---

## 🎯 PHASE 2 TASKS (Ready to Assign)

### High Priority Features - Week 2 (30 hours)

**Task 2.1: Account Security Features**
- [ ] Assign to developer
- [ ] Implement password change modal
- [ ] Implement API token generation
- [ ] Implement API token management
- [ ] Write tests
- [ ] Mark COMPLETE

**Task 2.2: Dashboard Enhancements**
- [ ] Assign to developer
- [ ] Add Files tile
- [ ] Add Experiments tile
- [ ] Add Costs tile with 30-day breakdown
- [ ] Add processing activity graph
- [ ] Write tests
- [ ] Mark COMPLETE

**Task 2.3: Fix Discover Files Button Redirect**
- [ ] Assign to developer
- [ ] Update templates/files/buckets.html line 69-71
- [ ] Change discoverFiles() to redirect
- [ ] Test redirect works
- [ ] Mark COMPLETE

**Task 2.4: Rename Manifest Generator**
- [ ] Assign to developer
- [ ] Update templates/manifest_generator.html
- [ ] Update templates/base.html
- [ ] Update all code references
- [ ] Test navigation works
- [ ] Mark COMPLETE

---

## 🎯 PHASE 3 TASKS (Ready to Assign)

### Medium Priority Features - Week 3 (25 hours)

**Task 3.1: Files Page Search & Filters**
- [ ] Assign to developer
- [ ] Add filter UI
- [ ] Implement search logic
- [ ] Add format filter
- [ ] Add subject filter
- [ ] Add biosample filter
- [ ] Add date range filter
- [ ] Write tests
- [ ] Mark COMPLETE

**Task 3.2: File Detail Page Features**
- [ ] Assign to developer
- [ ] Implement view subject files
- [ ] Implement find similar files
- [ ] Implement add tag functionality
- [ ] Write tests
- [ ] Mark COMPLETE

**Task 3.3: Test Bulk Import Feature**
- [ ] Assign to QA
- [ ] Test CSV import
- [ ] Test TSV import
- [ ] Test preview functionality
- [ ] Test submission
- [ ] Document results
- [ ] Mark COMPLETE

**Task 3.4: Test Auto-Discover Feature**
- [ ] Assign to QA
- [ ] Test file discovery
- [ ] Test file selection
- [ ] Test registration
- [ ] Document results
- [ ] Mark COMPLETE

---

## 🎯 PHASE 4 TASKS (Ready to Assign)

### Polish & Documentation - Week 4 (20 hours)

**Task 4.1: Write UI Documentation**
- [ ] Assign to writer
- [ ] Write user guide
- [ ] Add support email link
- [ ] Add feature documentation
- [ ] Review and approve
- [ ] Mark COMPLETE

**Task 4.2: Implement Cost Calculation Formula**
- [ ] Assign to developer
- [ ] Implement formula: (total_size / (total_size - (total_size * 0.98)))
- [ ] Update Dashboard
- [ ] Update usage page
- [ ] Write tests
- [ ] Mark COMPLETE

**Task 4.3: Add Column Mapping Help**
- [ ] Assign to developer
- [ ] Create help modal
- [ ] Add column descriptions
- [ ] Test modal displays
- [ ] Mark COMPLETE

**Task 4.4: Test Reset Button**
- [ ] Assign to QA
- [ ] Test resetForm() function
- [ ] Verify all fields reset
- [ ] Document results
- [ ] Mark COMPLETE

---

## 🧪 TESTING TASKS (Parallel)

- [ ] Test S3 URI Uniqueness
- [ ] Test All Backend Endpoints
- [ ] Test Biospecimen Hierarchy
- [ ] Test Account Security
- [ ] Test Dashboard Tiles
- [ ] Test File Search & Filters
- [ ] Test Bulk Import
- [ ] Test Auto-Discover
- [ ] Test File Detail Buttons
- [ ] Test Fileset Operations
- [ ] Test Manifest Generation
- [ ] Test Cost Calculation

---

## 📋 TEAM ASSIGNMENT TEMPLATE

```
PHASE 1 (Week 1):
- Developer A: Task 1.1 (S3 URI Uniqueness)
- Developer B: Task 1.2 (Backend Endpoints)
- Developer C: Task 1.3 (Biospecimen Model)
- QA Team: Testing tasks

PHASE 2 (Week 2):
- Developer A: Task 2.1 (Account Security)
- Developer B: Task 2.2 (Dashboard)
- Developer C: Task 2.3 & 2.4 (Quick fixes)
- QA Team: Testing tasks

PHASE 3 (Week 3):
- Developer A: Task 3.1 (Search & Filters)
- Developer B: Task 3.2 (File Detail)
- QA Team: Task 3.3 & 3.4 (Testing)

PHASE 4 (Week 4):
- Writer: Task 4.1 (Documentation)
- Developer A: Task 4.2 (Cost Calculation)
- Developer B: Task 4.3 (Help Modal)
- QA Team: Task 4.4 (Testing)
```

---

## 🚀 RELEASE APPROVAL

- [x] Assessment complete
- [x] Tasks created and organized
- [x] Effort estimates provided
- [x] Critical issues identified
- [x] Testing plan included
- [x] Documentation provided
- [ ] Team review completed
- [ ] Tasks assigned to developers
- [ ] Phase 1 started
- [ ] Weekly check-ins scheduled

---

**Status:** ✅ READY FOR TEAM ASSIGNMENT  
**Next Action:** Assign Phase 1 tasks to developers  
**Timeline:** 4 weeks to completion  
**Total Effort:** 115 hours


