from pathlib import Path

from app.core.authorization import RESPONSIBILITY_PERMISSIONS, PERMISSION_DELIVERY_CREATE
from app.services.procurement_service import VALID_TRANSITIONS

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
BASELINE = ROOT / "migrations" / "001_phase_a_baseline.sql"

LEGACY = (
    "supply_sources",
    "procurement_chains",
    "supplier_entity_id",
    "school_id",
    "promised_date",
    "capacity_source_id",
    "procurement_status_history",
    "audit_logs",
    "procurement_documents",
    "delivery_documents",
    "actor_trust",
    "actor_risk_cache",
    "DeliveryLogCreate",
)


def test_phase_a_transition_graph_is_frozen():
    assert VALID_TRANSITIONS == {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"EVALUATION", "CANCELLED"},
        "EVALUATION": {"SELECTED"},
        "SELECTED": {"ORDERED"},
        "ORDERED": {"COMMITTED"},
        "COMMITTED": {"DELIVERY"},
        "DELIVERY": {"INSPECTION"},
        "INSPECTION": {"ACCEPTED"},
        "ACCEPTED": {"COMPLETED"},
        "COMPLETED": set(),
        "CANCELLED": set(),
    }


def test_supplier_cannot_record_school_delivery():
    supplier_permissions = RESPONSIBILITY_PERMISSIONS["SUPPLIER_USER"]
    receiving_permissions = RESPONSIBILITY_PERMISSIONS["RECEIVING_OFFICER"]
    assert PERMISSION_DELIVERY_CREATE not in supplier_permissions
    assert PERMISSION_DELIVERY_CREATE in receiving_permissions


def test_canonical_baseline_contains_phase_a_tables_and_no_legacy_tables():
    sql = BASELINE.read_text(encoding="utf-8")
    required = [
        "users", "organizations", "organization_memberships", "responsibilities",
        "membership_responsibilities", "organization_verification_records", "suppliers",
        "supplier_capabilities", "supplier_products", "supplier_contacts", "procurements",
        "procurement_items", "supplier_evaluations", "supplier_selection_decisions",
        "purchase_orders", "purchase_order_lines", "supplier_commitments", "deliveries",
        "delivery_lines", "inspections", "corrective_actions", "procurement_events",
        "audit_events", "evidence_documents", "supplier_performance_metrics",
    ]
    for table in required:
        assert f"CREATE TABLE {table}" in sql
    for legacy in LEGACY:
        assert legacy not in sql.replace("school_identifier", "")


def test_active_backend_contains_no_legacy_domain_references():
    offenders = []
    import re
    patterns = {
        "supply_sources": r"\bsupply_sources\b",
        "procurement_chains": r"\bprocurement_chains\b",
        "supplier_entity_id": r"\bsupplier_entity_id\b",
        "school_id": r"\bschool_id\b",
        "promised_date": r"\bpromised_date\b",
        "capacity_source_id": r"\bcapacity_source_id\b",
        "procurement_status_history": r"\bprocurement_status_history\b",
        "audit_logs": r"\baudit_logs\b",
        "procurement_documents": r"\bprocurement_documents\b",
        "delivery_documents": r"\bdelivery_documents\b",
        "actor_trust": r"\bactor_trust\b",
        "actor_risk_cache": r"\bactor_risk_cache\b",
        "DeliveryLogCreate": r"\bDeliveryLogCreate\b",
    }
    for path in APP.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for legacy, pattern in patterns.items():
            if re.search(pattern, text):
                offenders.append((str(path.relative_to(ROOT)), legacy))
    assert offenders == []
