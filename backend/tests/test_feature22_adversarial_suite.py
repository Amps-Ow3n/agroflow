"""Feature 22 - Layer 7: adversarial tests.

These tests deliberately try to violate AgroFlow's contracts: malformed input,
unauthorized actors/resources, illegal workflow operations, invalid data,
evidence-file attacks, and the commitment concurrency contract.

Where a live PostgreSQL/Neon instance is required, the test proves the
application/schema contract deterministically and documents the remaining
runtime verification boundary instead of pretending a local fake database is
PostgreSQL concurrency evidence.
"""

from io import BytesIO
from pathlib import Path
import sys
import threading

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.authorization import (  # noqa: E402
    PROCUREMENT_OFFICER,
    PERMISSION_PROCUREMENT_CREATE,
    membership_has_permission,
    user_has_permission,
)
from app.core.resource_authorization import require_resource_access  # noqa: E402
from app.schemas.commitment_schema import SupplierCommitmentCreate  # noqa: E402
from app.schemas.procurement_schema import ProcurementCreate  # noqa: E402
from app.schemas.delivery_schema import DeliveryCreate  # noqa: E402
from app.services.domain_invariants import (  # noqa: E402
    calculate_delivery_discrepancy,
    validate_commitment_quantity,
)
from app.services.evidence_document_service import (  # noqa: E402
    validate_document_type,
    validate_file,
    validate_visibility_for_document_type,
)
from app.services.procurement_service import VALID_TRANSITIONS  # noqa: E402


# ---------------------------------------------------------------------------
# Input attacks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", -1),
        ("quantity", 0),
    ],
)
def test_negative_or_zero_procurement_quantity_is_rejected(field, value):
    payload = dict(
        title="School maize",
        required_by_date="2026-10-01",
        item_name="Maize flour",
        quantity=500,
        unit="kg",
        location="Kampala",
        procurement_method="QUOTATION",
    )
    payload[field] = value
    with pytest.raises(Exception):
        ProcurementCreate.model_validate(payload)


def test_missing_required_procurement_field_is_rejected():
    payload = {
        "title": "School maize",
        "required_by_date": "2026-10-01",
        "item_name": "Maize flour",
        "quantity": 500,
        "unit": "kg",
        # location deliberately missing
        "procurement_method": "QUOTATION",
    }
    with pytest.raises(Exception):
        ProcurementCreate.model_validate(payload)


def test_null_required_quantity_is_rejected():
    payload = {
        "title": "School maize",
        "required_by_date": "2026-10-01",
        "item_name": "Maize flour",
        "quantity": None,
        "unit": "kg",
        "location": "Kampala",
        "procurement_method": "QUOTATION",
    }
    with pytest.raises(Exception):
        ProcurementCreate.model_validate(payload)


def test_wrong_type_quantity_is_rejected():
    payload = {
        "title": "School maize",
        "required_by_date": "2026-10-01",
        "item_name": "Maize flour",
        "quantity": {"unexpected": "object"},
        "unit": "kg",
        "location": "Kampala",
        "procurement_method": "QUOTATION",
    }
    with pytest.raises(Exception):
        ProcurementCreate.model_validate(payload)


def test_malformed_procurement_method_is_rejected():
    payload = {
        "title": "School maize",
        "required_by_date": "2026-10-01",
        "item_name": "Maize flour",
        "quantity": 500,
        "unit": "kg",
        "location": "Kampala",
        "procurement_method": "DROP_TABLES",
    }
    with pytest.raises(Exception):
        ProcurementCreate.model_validate(payload)


def test_unexpected_extra_field_is_rejected():
    payload = {
        "title": "School maize",
        "required_by_date": "2026-10-01",
        "item_name": "Maize flour",
        "quantity": 500,
        "unit": "kg",
        "location": "Kampala",
        "procurement_method": "QUOTATION",
        "is_admin": True,
    }
    with pytest.raises(Exception):
        ProcurementCreate.model_validate(payload)


def test_oversized_text_field_is_rejected():
    payload = {
        "title": "x" * 201,
        "required_by_date": "2026-10-01",
        "item_name": "Maize flour",
        "quantity": 500,
        "unit": "kg",
        "location": "Kampala",
        "procurement_method": "QUOTATION",
    }
    with pytest.raises(Exception):
        ProcurementCreate.model_validate(payload)


def test_commitment_cannot_use_negative_quantity_even_if_capacity_is_large():
    with pytest.raises(HTTPException) as exc:
        validate_commitment_quantity(-1, 500)
    assert exc.value.status_code == 400


def test_commitment_cannot_exceed_capacity():
    with pytest.raises(HTTPException) as exc:
        validate_commitment_quantity(501, 500)
    assert exc.value.status_code == 409


def test_delivery_discrepancy_rejects_negative_received_quantity():
    with pytest.raises(ValueError):
        calculate_delivery_discrepancy(500, -1)


def test_delivery_discrepancy_rejects_zero_committed_quantity():
    with pytest.raises(ValueError):
        calculate_delivery_discrepancy(0, 0)


# ---------------------------------------------------------------------------
# Authorization attacks
# ---------------------------------------------------------------------------

def _org_membership(org_id=1, *, verified="VERIFIED", active="ACTIVE"):
    return {
        "status": active,
        "responsibilities": [{"code": PROCUREMENT_OFFICER}],
        "organization": {
            "id": org_id,
            "status": "ACTIVE",
            "verification_status": verified,
            "organization_type": "SCHOOL",
        },
    }


def _identity(*memberships):
    return {"user": {"id": 10, "status": "ACTIVE"}, "memberships": list(memberships)}


def test_wrong_organization_is_denied():
    identity = _identity(_org_membership(1))
    assert user_has_permission(identity, PERMISSION_PROCUREMENT_CREATE, organization_id=1)
    assert not user_has_permission(identity, PERMISSION_PROCUREMENT_CREATE, organization_id=2)


def test_inactive_membership_is_denied():
    identity = _identity(_org_membership(1, active="INACTIVE"))
    assert not user_has_permission(identity, PERMISSION_PROCUREMENT_CREATE, organization_id=1)


def test_unverified_organization_is_denied_by_central_authorization_boundary():
    identity = _identity(_org_membership(1, verified="PENDING"))
    assert not user_has_permission(identity, PERMISSION_PROCUREMENT_CREATE, organization_id=1)


def test_direct_resource_id_manipulation_is_denied():
    class Cursor:
        def execute(self, query, params):
            self.row = {"organization_id": 99} if params[0] == 999 else None
        def fetchone(self):
            return self.row

    identity = _identity(_org_membership(1))
    with pytest.raises(HTTPException) as exc:
        require_resource_access(Cursor(), identity, PERMISSION_PROCUREMENT_CREATE, "procurement", 999)
    assert exc.value.status_code == 403


def test_nonexistent_resource_id_is_not_authorized():
    class Cursor:
        def execute(self, query, params):
            self.row = None
        def fetchone(self):
            return None

    with pytest.raises(HTTPException) as exc:
        require_resource_access(
            Cursor(), _identity(_org_membership(1)),
            PERMISSION_PROCUREMENT_CREATE, "procurement", 999999
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Workflow attacks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "current,target",
    [
        ("DRAFT", "COMPLETED"),
        ("COMPLETED", "DRAFT"),
        ("CANCELLED", "DELIVERY"),
        ("ORDERED", "COMPLETED"),
        ("DELIVERY", "COMPLETED"),
        ("INSPECTION", "COMMITTED"),
    ],
)
def test_illegal_procurement_transitions_are_not_in_state_machine(current, target):
    assert target not in VALID_TRANSITIONS.get(current, set())


def test_completed_has_no_outgoing_transitions():
    assert VALID_TRANSITIONS.get("COMPLETED", set()) == set()


def test_cancelled_has_no_outgoing_transitions():
    assert VALID_TRANSITIONS.get("CANCELLED", set()) == set()


# ---------------------------------------------------------------------------
# Data attacks
# ---------------------------------------------------------------------------

def test_duplicate_active_commitment_is_database_constrained():
    migration = Path(__file__).resolve().parents[1] / "migrations" / "001_phase_a_baseline.sql"
    sql = migration.read_text()
    assert "uq_active_commitment_per_po_line_supplier" in sql
    assert "UNIQUE INDEX" in sql.upper()
    assert "purchase_order_line_id" in sql
    assert "supplier_id" in sql
    normalized = ''.join(sql.split()).upper()
    assert "STATUSIN('SUBMITTED','ACCEPTED')" in normalized


def test_invalid_foreign_key_relationship_is_database_constrained():
    migration = Path(__file__).resolve().parents[1] / "migrations" / "001_phase_a_baseline.sql"
    sql = migration.read_text()
    start = sql.index("CREATE TABLE supplier_commitments")
    end = sql.index("CREATE INDEX idx_commitments_purchase_order", start)
    block = sql[start:end]
    assert "REFERENCES purchase_orders(id)" in block
    assert "REFERENCES purchase_order_lines(id)" in block
    assert "REFERENCES suppliers(id)" in block


def test_commitment_quantity_database_constraint_is_present():
    migration = Path(__file__).resolve().parents[1] / "migrations" / "001_phase_a_baseline.sql"
    sql = migration.read_text()
    assert "CONSTRAINT commitments_quantity_check" in sql
    assert "CHECK (promised_qty > 0)" in sql


def test_delivery_window_database_and_schema_contract_is_present():
    payload = {
        "purchase_order_line_id": 1,
        "promised_qty": 500,
        "delivery_start": "2026-10-10",
        "delivery_end": "2026-10-01",
    }
    with pytest.raises(Exception):
        SupplierCommitmentCreate.model_validate(payload)


# ---------------------------------------------------------------------------
# Evidence attacks
# ---------------------------------------------------------------------------

def _upload(name, content_type, data):
    return UploadFile(
        filename=name,
        file=BytesIO(data),
        headers=Headers({"content-type": content_type}),
    )


def test_evidence_rejects_invalid_extension():
    with pytest.raises(HTTPException) as exc:
        validate_file(_upload("evidence.exe", "application/pdf", b"%PDF-1.7"))
    assert exc.value.status_code == 400


def test_evidence_rejects_invalid_mime_type():
    with pytest.raises(HTTPException) as exc:
        validate_file(_upload("evidence.pdf", "application/octet-stream", b"%PDF-1.7"))
    assert exc.value.status_code == 400


def test_evidence_rejects_invalid_magic_bytes():
    with pytest.raises(HTTPException) as exc:
        validate_file(_upload("evidence.pdf", "application/pdf", b"NOT-A-PDF"))
    assert exc.value.status_code == 400


def test_evidence_rejects_incompatible_visibility():
    with pytest.raises(HTTPException) as exc:
        validate_visibility_for_document_type("RFQ", "SUPPLIER_VISIBLE")
    assert exc.value.status_code == 403


def test_evidence_accepts_matching_pdf_signature():
    validate_file(_upload("evidence.pdf", "application/pdf", b"%PDF-1.7"))


def test_evidence_rejects_path_like_filename_by_never_using_filename_as_storage_name():
    # The production storage service generates a UUID filename; this test
    # documents the invariant that a client filename is metadata, not a path.
    from app.services.evidence_document_service import save_uploaded_file
    import tempfile
    from app.core.config import settings

    with tempfile.TemporaryDirectory() as tmp:
        storage_reference, _ = save_uploaded_file(
            _upload("../../outside.pdf", "application/pdf", b"%PDF-1.7"),
            Path(tmp),
            1,
        )
        assert ".." not in Path(storage_reference).parts
        assert Path(storage_reference).name != "../../outside.pdf"


def test_evidence_oversized_payload_is_rejected_and_partial_file_removed():
    from app.services.evidence_document_service import save_uploaded_file
    from app.core.config import settings
    import tempfile

    original = settings.MAX_EVIDENCE_FILE_SIZE
    settings.MAX_EVIDENCE_FILE_SIZE = 8
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(HTTPException) as exc:
                save_uploaded_file(
                    _upload("large.pdf", "application/pdf", b"%PDF-1.7" + b"123456789"),
                    Path(tmp),
                    1,
                )
            assert exc.value.status_code == 413
            assert not list(Path(tmp).rglob("*.pdf"))
    finally:
        settings.MAX_EVIDENCE_FILE_SIZE = original


# ---------------------------------------------------------------------------
# Repeated/concurrent attack model
# ---------------------------------------------------------------------------

def test_two_simultaneous_commit_attempts_cannot_both_win_capacity_contract():
    """Deterministic race model for the application invariant.

    A real PostgreSQL execution must additionally verify row locks and the
    unique partial index under concurrent transactions. This model ensures
    our domain guard itself cannot accept both 500 kg claims against 500 kg.
    """
    available = 500
    results = []
    lock = threading.Lock()
    committed_total = 0

    def attempt():
        nonlocal committed_total
        with lock:
            try:
                validate_commitment_quantity(500, available - committed_total)
            except HTTPException:
                results.append("REJECTED")
                return
            committed_total += 500
            results.append("ACCEPTED")

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ACCEPTED") == 1
    assert results.count("REJECTED") == 1
    assert committed_total == 500


def test_concurrency_protection_contract_documents_database_locking_requirement():
    source = Path(__file__).resolve().parents[1] / "app" / "services" / "commitment_service.py"
    text = source.read_text()
    assert "FOR UPDATE" in text
    migration = Path(__file__).resolve().parents[1] / "migrations" / "001_phase_a_baseline.sql"
    sql = migration.read_text()
    assert "uq_active_commitment_per_po_line_supplier" in sql
