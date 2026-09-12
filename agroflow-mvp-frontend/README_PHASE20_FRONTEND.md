# AgroFlow Phase 20 Frontend Repair

This frontend is a clean Phase-A client. It is intentionally not compatible with the retired supply/demand/chain architecture.

## Backend contract
Set `REACT_APP_API_BASE_URL` to the Phase-A FastAPI backend, for example:

`REACT_APP_API_BASE_URL=http://localhost:8000`

The login endpoint uses OAuth2 form fields (`username` = email, `password`), while registration and domain writes use JSON.

## Phase-A API groups used
- `/register`, `/login`, `/identity/me`
- `/procurements`
- `/procurements/{id}/enter-evaluation`
- `/procurements/{id}/supplier-evaluation`
- `/procurements/{id}/supplier-candidates`
- `/procurements/{id}/selection`
- `/purchase-orders/procurements/{id}`
- `/purchase-orders/{id}/commitment`
- `/supplier/commitments`
- `/deliveries/`
- `/deliveries/{id}/inspection`
- `/inspections/{id}/corrective-action`
- `/procurements/{id}/timeline`
- `/procurements/{id}/audit`
- `/suppliers/...`

## Important
The uploaded `AgroFlow-Phase20-Backend-Repair(1).zip` was inspected during this repair and contains directory entries but no backend source files. Therefore this client is aligned to the Phase-A contract, but the backend archive itself must be populated before the two can actually run together.

Do not restore retired frontend API modules or pages merely to make a missing backend endpoint work.
