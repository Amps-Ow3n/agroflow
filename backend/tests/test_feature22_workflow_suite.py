"""Feature 22 - Layer 3 workflow tests.

These tests exercise AgroFlow's procurement state machine and the connected
delivery/inspection rejection-recovery workflow. They are built on the
deterministic Layer 2 database adapter so the workflow can be repeated without
a live Neon/PostgreSQL environment.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.procurement_service import (
    VALID_TRANSITIONS,
    cancel_procurement,
    transition_procurement,
)
from app.services.delivery_service import create_delivery
from app.services.inspection_service import create_corrective_action, inspect_delivery
from app.schemas.delivery_schema import (
    CorrectiveActionCreate,
    DeliveryCreate,
    DeliveryLineCreate,
    InspectionCreate,
)
from test_feature22_integration_suite import FakeDB


def _seed_workflow_procurement(db, status="DRAFT"):
    c = db.cursor_obj
    c.procurements[1] = {
        "id": 1, "organization_id": 1, "status": status,
        "title": "Maize procurement",
    }
    c.items[201] = {
        "id": 201, "procurement_id": 1, "item_name": "Maize flour",
        "quantity": Decimal("500"), "unit": "kg",
    }
    return c


def test_workflow_happy_path_moves_through_complete_procurement_lifecycle():
    db = FakeDB()
    c = _seed_workflow_procurement(db)
    lifecycle = [
        "SUBMITTED", "EVALUATION", "SELECTED", "ORDERED", "COMMITTED",
        "DELIVERY", "INSPECTION", "ACCEPTED", "COMPLETED",
    ]

    for target in lifecycle:
        result = transition_procurement(c, 1, 100, target)
        assert result["to_status"] == target
        assert c.procurements[1]["status"] == target

    assert c.procurements[1]["status"] == "COMPLETED"
    assert len(c.events) == len(lifecycle)
    assert len(c.audit_events) == len(lifecycle)


def test_workflow_partial_delivery_preserves_500_to_430_evidence():
    db = FakeDB()
    c = _seed_workflow_procurement(db, "DELIVERY")
    c.commitments[1001] = {
        "id": 1001, "purchase_order_id": 10, "purchase_order_line_id": 101,
        "supplier_id": 50, "promised_qty": Decimal("500"), "status": "ACCEPTED",
    }
    result = create_delivery(c, 100, DeliveryCreate(
        commitment_id=1001, delivery_date=date(2026, 9, 30), condition="Good",
        lines=[DeliveryLineCreate(procurement_item_id=201, actual_quantity=Decimal("430"))],
    ))
    shortfall = Decimal("500") - Decimal("430")
    variance = shortfall / Decimal("500") * Decimal("100")

    assert result["delivery_status"] == "AWAITING_INSPECTION"
    assert shortfall == Decimal("70")
    assert variance == Decimal("14")


def test_workflow_rejection_corrective_action_replacement_and_reinspection():
    db = FakeDB()
    c = _seed_workflow_procurement(db, "DELIVERY")
    c.commitments[1001] = {
        "id": 1001, "purchase_order_id": 10, "purchase_order_line_id": 101,
        "supplier_id": 50, "promised_qty": Decimal("500"), "status": "ACCEPTED",
    }
    first = create_delivery(c, 100, DeliveryCreate(
        commitment_id=1001, delivery_date=date(2026, 9, 30), condition="Damaged",
        lines=[DeliveryLineCreate(procurement_item_id=201, actual_quantity=Decimal("430"))],
    ))
    rejected = inspect_delivery(c, first["id"], 100, InspectionCreate(
        received_qty=Decimal("430"), result="REJECTED", quality_status="FAILED",
        delay_status="ON_TIME", rejection_reason="Damaged goods",
    ))
    assert rejected["delivery"]["delivery_status"] == "REJECTED"

    action = create_corrective_action(
        c, rejected["inspection"]["id"], 100,
        CorrectiveActionCreate(description="Replace rejected goods"),
    )
    assert action["corrective_action"]["status"] == "OPEN"

    replacement = create_delivery(c, 100, DeliveryCreate(
        commitment_id=1001, parent_delivery_id=first["id"],
        delivery_date=date(2026, 10, 2), condition="Good",
        lines=[DeliveryLineCreate(procurement_item_id=201, actual_quantity=Decimal("500"))],
    ))
    assert replacement["parent_delivery_id"] == first["id"]
    assert c.corrective_actions[action["corrective_action"]["id"]]["status"] in {"OPEN", "COMPLETED"}

    accepted = inspect_delivery(c, replacement["id"], 100, InspectionCreate(
        received_qty=Decimal("500"), result="ACCEPTED", quality_status="GOOD",
        delay_status="ON_TIME",
    ))
    assert accepted["delivery"]["delivery_status"] == "ACCEPTED"
    assert c.procurements[1]["status"] == "ACCEPTED"


def test_workflow_illegal_transitions_are_rejected():
    cases = [("DRAFT", "COMPLETED"), ("COMPLETED", "DRAFT"), ("CANCELLED", "DELIVERY")]
    for current, target in cases:
        db = FakeDB()
        c = _seed_workflow_procurement(db, current)
        with pytest.raises(Exception) as exc:
            transition_procurement(c, 1, 100, target)
        assert getattr(exc.value, "status_code", None) == 409
        assert c.procurements[1]["status"] == current
        assert c.events == []
        assert c.audit_events == []


def test_workflow_submit_twice_is_rejected_without_state_corruption():
    db = FakeDB()
    c = _seed_workflow_procurement(db, "SUBMITTED")
    with pytest.raises(Exception) as exc:
        transition_procurement(c, 1, 100, "SUBMITTED")
    assert getattr(exc.value, "status_code", None) == 409
    assert c.procurements[1]["status"] == "SUBMITTED"


def test_workflow_cancel_twice_is_rejected():
    db = FakeDB()
    c = _seed_workflow_procurement(db, "DRAFT")
    cancel_procurement(c, 1, 100, "No longer required")
    with pytest.raises(Exception) as exc:
        cancel_procurement(c, 1, 100, "Cancel again")
    assert getattr(exc.value, "status_code", None) == 409
    assert c.procurements[1]["status"] == "CANCELLED"


def test_workflow_verify_delivery_twice_is_rejected():
    db = FakeDB()
    c = _seed_workflow_procurement(db, "DELIVERY")
    c.commitments[1001] = {
        "id": 1001, "purchase_order_id": 10, "purchase_order_line_id": 101,
        "supplier_id": 50, "promised_qty": Decimal("500"), "status": "ACCEPTED",
    }
    delivery = create_delivery(c, 100, DeliveryCreate(
        commitment_id=1001, delivery_date=date(2026, 9, 30), condition="Good",
        lines=[DeliveryLineCreate(procurement_item_id=201, actual_quantity=Decimal("500"))],
    ))
    payload = InspectionCreate(
        received_qty=Decimal("500"), result="ACCEPTED",
        quality_status="GOOD", delay_status="ON_TIME",
    )
    inspect_delivery(c, delivery["id"], 100, payload)
    with pytest.raises(Exception) as exc:
        inspect_delivery(c, delivery["id"], 100, payload)
    assert getattr(exc.value, "status_code", None) == 409
    assert len(c.inspections) == 1
    assert c.deliveries[delivery["id"]]["delivery_status"] == "ACCEPTED"


def test_workflow_acceptance_is_not_repeatable_after_completion():
    db = FakeDB()
    c = _seed_workflow_procurement(db, "ACCEPTED")
    transition_procurement(c, 1, 100, "COMPLETED")
    with pytest.raises(Exception) as exc:
        transition_procurement(c, 1, 100, "COMPLETED")
    assert getattr(exc.value, "status_code", None) == 409
    assert c.procurements[1]["status"] == "COMPLETED"


def test_workflow_transition_map_has_no_outbound_path_from_terminal_states():
    assert VALID_TRANSITIONS["COMPLETED"] == set()
    assert VALID_TRANSITIONS["CANCELLED"] == set()
