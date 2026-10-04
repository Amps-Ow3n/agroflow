# AgroFlow Feature 22 — Layer 4 Authorization Test Suite

## Purpose

Layer 4 tests who is allowed to do what, and whether authorization remains scoped to the organization/resource involved.

## Implemented

Added:

- `backend/tests/test_feature22_authorization_suite.py`

The suite derives its role/permission expectations from the existing Feature 21 central authorization map rather than inventing a new role model.

## Coverage

### Role authorization

Tests the actual responsibility -> permission map for:

- SUPPLIER_USER
- SUPPLIER_ADMIN
- PROCUREMENT_OFFICER
- PROCUREMENT_REVIEWER
- RECEIVING_OFFICER
- ORGANIZATION_ADMIN

Examples covered:

- supplier user can create commitments
- supplier user cannot inspect deliveries
- procurement officer can create procurements
- procurement reviewer can evaluate but cannot create procurements
- receiving officer can inspect/accept/reject deliveries
- organization admin has the broad organization-level permissions defined in Feature 21

### Membership/organization conditions

Tests:

- inactive membership denied
- inactive organization denied
- role lookup kept separate from organization-state policy

### Organization isolation

Tests:

- permission in Organization A does not authorize Organization B
- one user can have different responsibilities in different organizations without cross-organization privilege leakage
- supplier A cannot modify supplier B's resource

### Resource ownership resolution

Tests the existing resource-organization mapping for:

- procurement
- purchase order
- commitment
- delivery
- inspection
- supplier

Purchase orders, commitments, deliveries and inspections are verified as multi-organization resources where the procurement/school organization and supplier organization are both relevant.

### Resource-level authorization

Tests the existing `require_resource_access()` path for:

- authorized school access
- wrong-organization denial
- supplier-side commitment authorization
- school receiving officer inspection authorization
- supplier denial of school-only inspection
- missing resource -> 404 rather than authorization success

## Test result

Layer 4 authorization suite:

`36 passed`

Full backend suite after Layer 4:

`117 passed, 0 failed`

## Execution limitation

The execution environment did not have the backend's declared `python-jose`, `passlib`, and `psycopg2` dependencies installed, and network installation was unavailable. Therefore the Layer 4 tests were intentionally written against the importable Feature 21 authorization and resource-authorization layers rather than pretending that the FastAPI dependency wrappers were executed against a live database.

The production `require_permission()` dependency remains the Feature 21 path for API-level resource authorization and contains additional active/verified organization checks and the supplier-performance special visibility rule. Those API dependency tests should be run in the normal AgroFlow environment with the declared backend dependencies installed.

No production authorization behavior was changed merely to make tests pass. The implementation adds evidence around the existing Feature 21 authorization model.
