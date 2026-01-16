# Endpoint Verification Report: `POST /portal/files/register`

## 1. Overview

This report documents the current verification status of the **Portal bulk file registration endpoint** `POST /portal/files/register`.

**High-level status:**
- **Frontend:** Implemented and verified as ready to call the endpoint.
- **Backend:** Endpoint handler not yet implemented; no integration tests.

This report is the detailed companion to `VERIFICATION_SUMMARY.md`.

---

## 2. Scope

This verification covers:
- UI flow in the Portal for discovering S3 files and initiating registration.
- JavaScript client behavior and request construction to `POST /portal/files/register`.
- Request/response contract definition for the endpoint.
- Identification of missing backend functionality and tests.

Out of scope:
- Low-level FileRegistry internals.
- Legacy single-file or CSV/TSV import endpoints, except as references.

---

## 3. System Context

The endpoint `POST /portal/files/register` is a **Portal-facing bulk registration endpoint** used when a user discovers candidate files in S3 via the UI and chooses to register them into the File Registry.

Related endpoints (already existing on the API side):
- `POST /api/files/register` – single-file registration.
- `POST /api/files/auto-register` – automatic registration logic.
- `POST /api/files/bulk-import` – CSV/TSV bulk import.

`/portal/files/register` is a **separate Portal entry point** that:
- Accepts multiple discovered files from the UI.
- Applies the same underlying FileRegistry behavior.
- Returns an aggregated per-file result for the UI to display.

---

## 4. Frontend Implementation Verification

**Files involved (per `VERIFICATION_SUMMARY.md`):**
- `templates/files/buckets.html`
- `templates/files/register.html`
- `static/js/file-registry.js`

### 4.1 Buckets Page (`templates/files/buckets.html`)

Verified behaviors:
- Discovery UI presents a modal listing discovered S3 objects.
- A **"Register Selected"** button is available within or associated with the discovery modal.
- Clicking **"Register Selected"** correctly navigates/redirects the user to the registration page that contains the Auto-Discover tab.

### 4.2 Registration Page (`templates/files/register.html`)

Verified behaviors (Auto-Discover tab):
- Displays a list of discovered files available for registration.
- Allows users to select which discovered files to register.
- Presents input fields for **Subject ID** and **Biosample ID**.
- Exposes a **"Register Selected Files"** button to initiate the registration.

### 4.3 JavaScript Client (`static/js/file-registry.js`)

Verified behaviors:
- A function `registerSelectedDiscoveredFiles()` exists and is bound to the **"Register Selected Files"** button.
- It gathers selected discovered files and relevant metadata from the UI.
- It constructs and sends a **`POST`** request to the endpoint **`/portal/files/register`**.
- It handles success and error responses, including:
  - Parsing result payload (registered/skipped/errors).
  - Displaying toast notifications / user feedback.

Conclusion: **Frontend is ready** and only depends on the backend endpoint to be implemented.

---

## 5. Request & Response Contract

### 5.1 Request Payload (Conceptual)

The Portal is expected to send a JSON body including at least:
- `customer_id`: Customer performing the operation.
- `subject_id`: Subject the files belong to.
- `biosample_id`: Biosample the files belong to.
- `files`: array of discovered file objects, each containing minimal metadata, e.g.:
  - `s3_uri` (or equivalent bucket/key fields)
  - `format`
  - `size`
  - other discovery metadata as needed (checksum, storage class, etc.).

### 5.2 Response Payload (Conceptual)

The endpoint should return an object summarizing outcomes **per file**:
- `registered`: list of successfully registered files (with identifiers).
- `skipped`: list of files that were already registered or not eligible.
- `errors`: list of files that failed to register, with error reasons.

This contract is designed so the UI can:
- Clearly show what was registered vs. skipped.
- Surface per-file error details.

---

## 6. Verified User Flow

End-to-end user flow (frontend):
1. User opens the Buckets page and runs S3 discovery.
2. Discovered files appear in the discovery modal.
3. User clicks **"Register Selected"**.
4. User is redirected to the registration page, Auto-Discover tab.
5. User selects which discovered files to register.
6. User enters **Subject ID** and **Biosample ID**.
7. User clicks **"Register Selected Files"**.
8. Browser issues `POST /portal/files/register` with the payload described above.
9. UI awaits response and renders success/errors via notifications.

All of these steps up to (8) are implemented; step (9) is partially implemented on the UI side but blocked by the missing backend handler.

---

## 7. Gaps & Risks

### 7.1 Missing Backend Handler

- No implementation yet for `POST /portal/files/register` on the server.
- Likely location: Portal app routing (e.g., `workset_api.py` or a dedicated Portal module).
- Required behavior:
  - Validate customer ownership and request body.
  - Invoke FileRegistry (or equivalent service) for each file.
  - Aggregate per-file outcomes into the response format described above.
  - Log at **trace-level** for request, per-file processing, and summary.

### 7.2 Missing Tests

- No integration tests for `POST /portal/files/register`.
- No end-to-end tests from S3 discovery through to registration persistence.
- No negative-path tests (invalid payloads, permission issues, partial failures).

These gaps mean the feature is **not yet production-ready** even though the UI is in place.

---

## 8. Recommendations & Next Steps

**Immediate actions:**
1. Implement backend handler for `POST /portal/files/register` in the Portal layer.
2. Define and enforce request/response models (e.g., Pydantic/Marshmallow/Dataclasses, depending on stack).
3. Add trace-level logging for:
   - Request receipt and validation.
   - Per-file registration attempts and outcomes.
   - Final aggregated response summary.
4. Implement integration tests covering:
   - Happy path (all files register successfully).
   - Mixed outcomes (some registered, some skipped, some errors).
   - Invalid/malformed requests.

**Follow-up actions:**
- Add end-to-end tests exercising the full UI → endpoint → persistence flow.
- Align `/portal/files/register` implementation with the existing single-file and bulk-import endpoints for consistent behavior and error semantics.

---

## 9. Conclusion

The **Portal frontend** and **client-side integration** with `POST /portal/files/register` are fully in place and aligned with the intended request/response contract. The **backend endpoint handler and tests are still missing**, and implementing them is the critical path to making bulk registration from discovered S3 files fully functional.

