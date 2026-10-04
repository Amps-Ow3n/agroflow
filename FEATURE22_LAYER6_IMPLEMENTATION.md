# Feature 22 — Layer 6 Acceptance Test Suite

## Purpose

Layer 6 steps back from individual components and asks whether AgroFlow can produce a useful, evidence-backed account of what happened during a procurement.

Acceptance question:

> Can the system connect requirement → supplier decision → order/commitment → delivery → inspection → outcome, while preserving evidence of who did what, when, and why?

## Implemented

### Backend
- Added `backend/tests/test_feature22_acceptance_suite.py`.
- Tests cover:
  - complete happy-path procurement account
  - requirement quantity/unit/required-by facts
  - supplier selection evidence/reason
  - supplier commitment promise
  - delivered quantity and accepted inspection
  - partial delivery 500 kg → 430 kg with 70 kg shortfall and 14% variance
  - rejected delivery → corrective action → replacement delivery → reinspection
  - evidence metadata and event actor/time fields
  - failure reason and corrective-action explanation
- Tests use the deterministic Layer 2 database adapter; they do not claim to prove a live Neon/PostgreSQL environment.

### Evidence upload gap implemented
The Feature-21 frontend previously displayed evidence metadata but had no dedicated upload page. This gap was implemented rather than left as an acceptance hole.

Backend:
- Added `POST /evidence/{procurement_id}/upload`.
- Uses the existing `require_evidence_upload` resource authorization dependency.
- Uses the existing `create_evidence_document()` service, including document-type, visibility, MIME, extension, magic-byte, size, procurement ownership, and event ownership validation.
- Uses the existing transaction boundary.

Frontend:
- Added `src/api/evidenceApi.js`.
- Added `src/pages/procurement/EvidenceUploadPage.js`.
- Added `/school/procurements/:id/evidence/new` route.
- Added an Upload Evidence action to procurement detail.
- Added a UI test proving metadata/file selection reaches the evidence API.

## Verification

Backend:
- `PYTHONPATH=backend pytest -q backend/tests`
- Result: **122 passed, 0 failed**.

Frontend:
- The uploaded source archive does not contain `node_modules`, and this execution environment cannot install the declared React dependencies offline.
- Therefore the React/Jest suite was not claimed as executed. The source changes were inspected and the backend suite was fully executed.

## Important scope limitation

The acceptance suite uses the deterministic test database adapter inherited from Layer 2 rather than a live PostgreSQL/Neon instance. Real database behavior, real browser rendering, and real API/session execution require the normal AgroFlow development environment with declared dependencies and database configuration.
