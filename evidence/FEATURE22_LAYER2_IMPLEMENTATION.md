# AgroFlow Feature 22 — Layer 2 Integration Test Suite

## What was added

`backend/tests/test_feature22_integration_suite.py`

The suite exercises real AgroFlow route/service/schema/transaction code across multiple layers instead of testing isolated functions only.

Covered flows:

1. Procurement creation
   - HTTP route
   - Pydantic request validation
   - authorization dependency override for the test actor
   - procurement service
   - database boundary
   - transaction commit
   - persistence of procurement/item
   - procurement event + audit event
   - response identifier

2. Procurement validation before persistence
   - invalid quantity is rejected at request validation
   - database remains unchanged

3. Supplier commitment
   - commitment route
   - supplier lookup
   - purchase-order-line lookup
   - capacity invariant
   - commitment persistence
   - transaction commit
   - over-capacity rejection
   - rollback/no commitment on failure

4. Delivery recording
   - delivery route
   - accepted-commitment requirement
   - organization-scoped lookup
   - delivery persistence
   - delivery-line persistence
   - procurement transition

5. Delivery inspection
   - delivery lookup
   - received quantity compared with recorded delivery quantity
   - inspection persistence
   - delivery status update

6. Transaction rollback
   - delivery row is created in the transaction
   - invalid delivery line causes failure
   - rollback removes the partial delivery write

7. Evidence document service
   - evidence file validation
   - physical file storage
   - evidence metadata persistence

## Important environment boundary

The uploaded source archive does not contain a runnable PostgreSQL/Neon database or database credentials, and the isolated execution environment does not provide PostgreSQL.

Therefore the suite uses a deterministic in-memory PostgreSQL-shaped adapter **only at the database boundary**. The actual AgroFlow route/service/schema/transaction code is exercised. The adapter is not PostgreSQL and therefore these tests do **not** prove PostgreSQL-specific SQL behavior, Neon connectivity, constraints, indexes, locking, or real database isolation.

Those real-database checks should be added/executed when a controlled PostgreSQL test database is available.

## Verification

Executed from `backend/` with `PYTHONPATH=.`:

`72 passed, 0 failed`

This total includes the existing Layer 1/unit and security/contract tests plus the new Layer 2 integration suite.
