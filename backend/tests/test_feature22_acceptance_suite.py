"""Feature 22 - Layer 6 acceptance tests.

Acceptance tests step back from individual implementation details and ask whether
AgroFlow can produce a useful, evidence-backed account of a procurement outcome.
They use the deterministic Layer 2 database adapter so the business scenario is
repeatable without pretending to be a live Neon/PostgreSQL environment.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.procurement_service import transition_procurement
from app.services.delivery_service import create_delivery
from app.services.inspection_service import inspect_delivery, create_corrective_action
from app.schemas.delivery_schema import DeliveryCreate, DeliveryLineCreate, InspectionCreate, CorrectiveActionCreate
from test_feature22_integration_suite import FakeDB


def _seed_acceptance_case(db):
    c = db.cursor_obj
    c.procurements[1] = {
        "id": 1, "organization_id": 1, "status": "DRAFT",
        "title": "School maize procurement", "required_by_date": date(2026, 10, 1),
    }
    c.items[201] = {
        "id": 201, "procurement_id": 1, "item_name": "Maize flour",
        "quantity": Decimal("500"), "unit": "kg",
    }
    # Evidence and selection are represented as the persisted facts the
    # acceptance question cares about; lower layers already test their own
    # creation paths.
    c.selection_decisions = [{
        "procurement_id": 1, "supplier_id": 50,
        "decision_reason": "Verified supplier with sufficient capacity.",
        "decided_by": 100,
    }]
    c.evidence_documents = [{
        "id": 700, "procurement_id": 1, "document_type": "EVALUATION",
        "original_filename": "supplier-evaluation.pdf", "uploaded_by": 100,
        "visibility": "INTERNAL",
    }]
    c.events.extend([
        {"id": 1, "type": "REQUIREMENT_CREATED", "actor_id": 100},
        {"id": 2, "type": "SUPPLIER_SELECTED", "actor_id": 100},
    ])
    return c


def _move_to_delivery(c):
    for status in ["SUBMITTED", "EVALUATION", "SELECTED", "ORDERED", "COMMITTED", "DELIVERY"]:
        transition_procurement(c, 1, 100, status)
    c.commitments[1001] = {
        "id": 1001, "purchase_order_id": 10, "purchase_order_line_id": 101,
        "supplier_id": 50, "promised_qty": Decimal("500"), "status": "ACCEPTED",
    }


def _account(c):
    return {
        "requirement": {
            "item": c.items[201]["item_name"],
            "quantity": c.items[201]["quantity"],
            "unit": c.items[201]["unit"],
            "required_by": c.procurements[1]["required_by_date"],
        },
        "supplier_decision": c.selection_decisions[0],
        "commitment": c.commitments.get(1001),
        "deliveries": list(c.deliveries.values()),
        "inspections": list(c.inspections.values()),
        "corrective_actions": list(c.corrective_actions.values()),
        "evidence": c.evidence_documents,
        "events": c.events,
        "audit_events": c.audit_events,
    }


def test_acceptance_happy_path_can_answer_what_was_required_and_what_happened():
    db = FakeDB()
    c = _seed_acceptance_case(db)
    _move_to_delivery(c)

    delivery = create_delivery(c, 100, DeliveryCreate(
        commitment_id=1001, delivery_date=date(2026, 9, 30), condition="Good",
        lines=[DeliveryLineCreate(procurement_item_id=201, actual_quantity=Decimal("500"))],
    ))
    inspection = inspect_delivery(c, delivery["id"], 100, InspectionCreate(
        received_qty=Decimal("500"), result="ACCEPTED", quality_status="GOOD",
        delay_status="ON_TIME",
    ))
    transition_procurement(c, 1, 100, "COMPLETED")

    account = _account(c)
    assert account["requirement"] == {
        "item": "Maize flour", "quantity": Decimal("500"), "unit": "kg",
        "required_by": date(2026, 10, 1),
    }
    assert account["supplier_decision"]["supplier_id"] == 50
    assert account["commitment"]["promised_qty"] == Decimal("500")
    assert c.delivery_lines[0]["actual_quantity"] == Decimal("500")
    assert account["inspections"][0]["result"] == "ACCEPTED"
    assert inspection["delivery"]["delivery_status"] == "ACCEPTED"
    assert c.procurements[1]["status"] == "COMPLETED"
    assert account["evidence"]
    assert account["events"]
    assert account["audit_events"]


def test_acceptance_partial_delivery_can_explain_quantity_failure():
    db = FakeDB()
    c = _seed_acceptance_case(db)
    _move_to_delivery(c)

    delivery = create_delivery(c, 100, DeliveryCreate(
        commitment_id=1001, delivery_date=date(2026, 9, 30), condition="Good",
        lines=[DeliveryLineCreate(procurement_item_id=201, actual_quantity=Decimal("430"))],
    ))
    inspection = inspect_delivery(c, delivery["id"], 100, InspectionCreate(
        received_qty=Decimal("430"), result="ACCEPTED", quality_status="GOOD",
        delay_status="ON_TIME",
    ))

    committed = Decimal("500")
    received = Decimal("430")
    shortfall = committed - received
    variance = shortfall / committed * Decimal("100")

    assert shortfall == Decimal("70")
    assert variance == Decimal("14")
    assert inspection["delivery"]["delivery_status"] == "ACCEPTED"
    transition_procurement(c, 1, 100, "ACCEPTED")
    assert c.procurements[1]["status"] == "ACCEPTED"


def test_acceptance_rejection_case_preserves_failure_and_recovery_history():
    db = FakeDB()
    c = _seed_acceptance_case(db)
    _move_to_delivery(c)

    first = create_delivery(c, 100, DeliveryCreate(
        commitment_id=1001, delivery_date=date(2026, 9, 30), condition="Damaged",
        lines=[DeliveryLineCreate(procurement_item_id=201, actual_quantity=Decimal("430"))],
    ))
    rejected = inspect_delivery(c, first["id"], 100, InspectionCreate(
        received_qty=Decimal("430"), result="REJECTED", quality_status="FAILED",
        delay_status="ON_TIME", rejection_reason="Damaged goods",
    ))
    action = create_corrective_action(
        c, rejected["inspection"]["id"], 100,
        CorrectiveActionCreate(description="Replace rejected goods"),
    )
    replacement = create_delivery(c, 100, DeliveryCreate(
        commitment_id=1001, parent_delivery_id=first["id"],
        delivery_date=date(2026, 10, 2), condition="Good",
        lines=[DeliveryLineCreate(procurement_item_id=201, actual_quantity=Decimal("500"))],
    ))
    accepted = inspect_delivery(c, replacement["id"], 100, InspectionCreate(
        received_qty=Decimal("500"), result="ACCEPTED", quality_status="GOOD",
        delay_status="ON_TIME",
    ))

    account = _account(c)
    assert account["inspections"][0]["result"] == "REJECTED"
    assert account["corrective_actions"][0]["description"] == "Replace rejected goods"
    assert replacement["parent_delivery_id"] == first["id"]
    assert accepted["inspection"]["result"] == "ACCEPTED"
    assert len(account["deliveries"]) == 2
    assert len(account["inspections"]) == 2


def test_acceptance_evidence_answers_who_and_when_without_replacing_the_history():
    db = FakeDB()
    c = _seed_acceptance_case(db)
    _move_to_delivery(c)
    c.events.append({"id": 99, "type": "INSPECTION_COMPLETED", "actor_id": 100, "occurred_at": "2026-09-30T12:00:00"})
    c.evidence_documents.append({
        "id": 701, "procurement_id": 1, "document_type": "INSPECTION_RECORD",
        "original_filename": "inspection-record.pdf", "uploaded_by": 100,
        "uploaded_at": "2026-09-30T12:05:00", "visibility": "INTERNAL",
    })

    account = _account(c)
    evidence = account["evidence"][-1]
    event = account["events"][-1]

    assert evidence["original_filename"] == "inspection-record.pdf"
    assert evidence["uploaded_by"] == 100
    assert evidence["uploaded_at"] == "2026-09-30T12:05:00"
    assert event["actor_id"] == 100
    assert event["occurred_at"] == "2026-09-30T12:00:00"


def test_acceptance_account_can_expose_failure_reason_and_corrective_action():
    db = FakeDB()
    c = _seed_acceptance_case(db)
    _move_to_delivery(c)
    first = create_delivery(c, 100, DeliveryCreate(
        commitment_id=1001, delivery_date=date(2026, 9, 30), condition="Damaged",
        lines=[DeliveryLineCreate(procurement_item_id=201, actual_quantity=Decimal("430"))],
    ))
    rejected = inspect_delivery(c, first["id"], 100, InspectionCreate(
        received_qty=Decimal("430"), result="REJECTED", quality_status="FAILED",
        delay_status="ON_TIME", rejection_reason="Damaged goods",
    ))
    create_corrective_action(c, rejected["inspection"]["id"], 100, CorrectiveActionCreate(description="Replace rejected goods"))

    account = _account(c)
    inspection = account["inspections"][0]
    action = account["corrective_actions"][0]
    assert inspection["rejection_reason"] == "Damaged goods"
    assert action["description"] == "Replace rejected goods"
    assert action["status"] == "OPEN"
