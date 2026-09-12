# AgroFlow Phase 20 Backend Repair — current snapshot

This package is backend-only and is based on the newly uploaded AgroFlow snapshot.
It does not include `.env`, `agroflow.db`, frontend files, or old migration history.

## Replace
- app/main.py
- app/core/authorization.py
- app/core/dependencies.py
- app/core/transactions.py
- app/core/db_errors.py
- app/models/procurement_events.py
- app/services/procurement_service.py
- app/services/supplier_evaluation_service.py
- app/services/supplier_selection_service.py
- app/services/purchase_order_service.py
- app/services/commitment_service.py
- app/services/delivery_service.py
- app/services/inspection_service.py
- app/services/supplier_performance_service.py
- app/engines/supplier_performance_engine.py
- app/routes/auth.py
- app/routes/organizations.py
- app/routes/procurement_routes.py
- app/routes/supplier_registry_routes.py
- app/routes/supplier_evaluation_routes.py
- app/routes/supplier_selection_routes.py
- app/routes/purchase_order_routes.py
- app/routes/commitment_routes.py
- app/routes/delivery_routes.py
- app/routes/procurement_event_routes.py
- app/routes/supplier_performance.py
- app/schemas/delivery_schema.py
- app/services/identity_service.py
- app/scripts/create_admin.py
- migrations/001_phase_a_baseline.sql

## Retire/delete
- migrations/legacy/
- schema/phase_a_baseline.sql
- app/routes/admin_delivery_routes.py
- app/routes/audit_routes.py
- app/routes/dashboard_routes.py
- app/routes/discrepancy_routes.py
- app/routes/intelligence_routes.py
- app/routes/school_dashboard_routes.py
- app/routes/school_routes.py
- app/routes/system_dashboard_routes.py
- app/routes/supplier_comparison.py
- app/routes/supplier_dashboard_routes.py
- app/routes/procurement_reality_report_routes.py
- app/services/dashboard_service.py
- app/services/discrepancy_service.py
- app/services/identity_registration_service.py
- app/services/procurement_reality_report_service.py
- app/services/supplier_comparison_service.py
- app/engines/core/
- app/engines/intelligence/
- app/engines/support/
- app/engines/delivery_engine.py
- app/engines/feasibility_engine.py
- app/engines/matching_engine.py
- app/engines/risk_engine.py
- app/engines/supplier_evaluation_engine.py
- app/models/commitments.py
- app/models/deliveries.py
- app/models/users.py
- app/utils/audit.py
- app/utils/authorization.py
- app/utils/status_mapper.py
- app/logs/decision_logger.py
- app/schemas/discrepancy_schema.py
- app/schemas/procurement_reality_report_schema.py
- app/schemas/dashboard_schema.py
- app/schemas/supplier_comparison_schema.py

## Verification performed
- Python compileall: passed.
- Phase-A static/domain/Pydantic tests in this package: 25 passed.
- Full DB-backed test execution still requires the project's Python environment with psycopg2-binary installed and a PostgreSQL/Neon database for integration tests.
