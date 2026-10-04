# Feature 22 — Layer 7 Adversarial Test Suite

## Purpose
Layer 7 deliberately tries to break AgroFlow rather than proving only the happy path.

Coverage:
- malformed, missing, null, wrong-type, oversized and unexpected input
- role, organization, membership and direct-resource authorization attacks
- illegal and repeated workflow operations
- duplicate records, foreign-key constraints, conflicting quantities and nonexistent resources
- evidence extension/MIME/magic-byte/visibility/path-like filename/oversize attacks
- repeated/concurrent commitment attack model

## Production fix made
The central `get_authorized_membership()` security boundary now requires the organization to be `ACTIVE` **and `VERIFIED` before organization-scoped permission can authorize a user.** Previously the helper checked organization status and membership status but not verification status. This closes a defense-in-depth gap for direct resource/service authorization callers.

The evidence storage service was also hardened so an oversized upload removes the partially written file and attempts to remove the now-empty evidence directories.

## Concurrency evidence boundary
Feature 21 already protects commitment creation with:
1. `SELECT ... FOR UPDATE` on the purchase-order line, and
2. PostgreSQL partial unique index `uq_active_commitment_per_po_line_supplier` for `SUBMITTED`/`ACCEPTED` commitments.

Layer 7 tests the application invariant with a deterministic two-thread race model and verifies the source/schema locking contract. A true concurrent PostgreSQL/Neon test still requires a live PostgreSQL environment; this archive does not contain credentials or a live DB, so it does not claim that runtime database concurrency was executed here.

## Evidence result
Executed with:
`PYTHONPATH=backend pytest -q backend/tests`

Result:
**160 passed, 0 failed**

This is the complete executable backend suite in the Layer 7 archive, including Layers 1–7 and the existing backend security/contract tests.
