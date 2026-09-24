from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.services.domain_invariants import (
    calculate_delivery_discrepancy,
    require_delivery_belongs_to_procurement,
    require_inspection_belongs_to_delivery,
    require_state,
    validate_commitment_quantity,
)
from app.services.procurement_service import VALID_TRANSITIONS
from app.engines.supplier_performance_engine import calculate_supplier_performance, pct
from app.schemas.commitment_schema import SupplierCommitmentCreate
from app.schemas.delivery_schema import DeliveryLineCreate
from app.schemas.procurement_schema import ProcurementCreate


def test_commitment_quantity_at_capacity_is_valid():
    assert validate_commitment_quantity(Decimal("500"), Decimal("500")) is True


def test_commitment_quantity_above_capacity_is_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_commitment_quantity(Decimal("501"), Decimal("500"))
    assert exc.value.status_code == 409


def test_commitment_quantity_negative_is_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_commitment_quantity(Decimal("-1"), Decimal("500"))
    assert exc.value.status_code == 400


def test_commitment_quantity_zero_is_valid_when_capacity_is_zero():
    assert validate_commitment_quantity(Decimal("0"), Decimal("0")) is True


def test_commitment_quantity_exceeding_zero_capacity_is_rejected():
    with pytest.raises(HTTPException):
        validate_commitment_quantity(Decimal("0.01"), Decimal("0"))


def test_canonical_delivery_discrepancy_500_to_430():
    result = calculate_delivery_discrepancy(Decimal("500"), Decimal("430"))
    assert result["shortfall"] == Decimal("70")
    assert result["overage"] == Decimal("0")
    assert result["variance_rate"] == Decimal("14.00")


def test_exact_delivery_has_zero_discrepancy():
    result = calculate_delivery_discrepancy(500, 500)
    assert result["shortfall"] == Decimal("0")
    assert result["overage"] == Decimal("0")
    assert result["variance_rate"] == Decimal("0.00")


def test_zero_received_is_full_shortfall():
    result = calculate_delivery_discrepancy(500, 0)
    assert result["shortfall"] == Decimal("500")
    assert result["overage"] == Decimal("0")
    assert result["variance_rate"] == Decimal("100.00")


def test_received_above_commitment_is_overage_not_shortfall():
    result = calculate_delivery_discrepancy(500, 550)
    assert result["shortfall"] == Decimal("0")
    assert result["overage"] == Decimal("50")
    assert result["variance_rate"] == Decimal("10.00")


def test_negative_received_quantity_is_rejected():
    with pytest.raises(ValueError):
        calculate_delivery_discrepancy(500, -1)


def test_zero_committed_quantity_is_rejected_for_variance_calculation():
    with pytest.raises(ValueError):
        calculate_delivery_discrepancy(0, 0)


def test_variance_rounding_is_two_decimal_places():
    result = calculate_delivery_discrepancy(300, 299)
    assert result["variance_rate"] == Decimal("0.33")


def test_pct_returns_none_for_zero_denominator():
    assert pct(Decimal("10"), Decimal("0")) is None


def test_procurement_quantity_schema_rejects_zero_and_negative():
    base = {
        "title": "Maize procurement",
        "required_by_date": date(2026, 10, 1),
        "item_name": "Maize flour",
        "unit": "kg",
        "location": "Kampala",
        "procurement_method": "QUOTATION",
    }
    for quantity in (Decimal("0"), Decimal("-1")):
        with pytest.raises(ValidationError):
            ProcurementCreate(**base, quantity=quantity)


def test_delivery_line_quantity_accepts_zero_but_rejects_negative():
    assert DeliveryLineCreate(procurement_item_id=1, actual_quantity=Decimal("0"))
    with pytest.raises(ValidationError):
        DeliveryLineCreate(procurement_item_id=1, actual_quantity=Decimal("-1"))


def test_commitment_delivery_window_must_be_valid():
    with pytest.raises(ValidationError):
        SupplierCommitmentCreate(
            purchase_order_line_id=1,
            promised_qty=Decimal("500"),
            delivery_start=date(2026, 10, 5),
            delivery_end=date(2026, 10, 3),
        )


def test_delivery_reference_invariant():
    assert require_delivery_belongs_to_procurement({"procurement_id": 10}, 10)
    with pytest.raises(HTTPException):
        require_delivery_belongs_to_procurement({"procurement_id": 10}, 99)


def test_inspection_reference_invariant():
    assert require_inspection_belongs_to_delivery({"delivery_id": 20}, 20)
    with pytest.raises(HTTPException):
        require_inspection_belongs_to_delivery({"delivery_id": 20}, 99)


def test_state_rule_accepts_allowed_state():
    assert require_state("DRAFT", {"DRAFT", "SUBMITTED"}, message="invalid") is None


def test_state_rule_rejects_disallowed_state():
    with pytest.raises(HTTPException) as exc:
        require_state("COMPLETED", {"DRAFT", "SUBMITTED"}, message="invalid")
    assert exc.value.status_code == 409


def test_procurement_transition_rules_are_frozen():
    assert VALID_TRANSITIONS["DRAFT"] == {"SUBMITTED", "CANCELLED"}
    assert VALID_TRANSITIONS["COMPLETED"] == set()
    assert VALID_TRANSITIONS["CANCELLED"] == set()


class FakePerformanceCursor:
    def __init__(self, rows):
        self.rows = rows
        self.procurement_queries = []
        self.current = None

    def execute(self, sql, params=None):
        self.current = sql
        if "FROM procurements p JOIN purchase_orders" in sql:
            self.result = self.rows
        else:
            self.result = [{"accepted": Decimal("430")}]

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result[0]


def test_supplier_performance_without_history_is_neutral():
    cursor = FakePerformanceCursor([])
    result = calculate_supplier_performance(cursor, 7)
    assert result["status"] == "NO_HISTORY"
    assert result["observation_count"] == 0
    assert result["fulfilment_rate"] is None
    assert result["quantity_variance_rate"] is None
    assert result["on_time_delivery_rate"] is None
    assert result["quality_acceptance_rate"] is None


def test_supplier_performance_calculates_fulfilment_and_variance():
    rows = [{
        "procurement_id": 1,
        "commitment_id": 10,
        "promised_qty": Decimal("500"),
        "delivery_end": date(2026, 10, 3),
        "delivery_id": 20,
        "delivery_date": date(2026, 10, 3),
        "inspection_id": 30,
        "result": "ACCEPTED",
        "received_qty": Decimal("430"),
    }]
    cursor = FakePerformanceCursor(rows)
    result = calculate_supplier_performance(cursor, 7)
    assert result["status"] == "AVAILABLE"
    assert result["observation_count"] == 1
    assert result["promised_quantity"] == Decimal("500")
    assert result["accepted_quantity"] == Decimal("430")
    assert result["fulfilment_rate"] == Decimal("86.00")
    assert result["quantity_variance_rate"] == Decimal("14.00")
    assert result["on_time_delivery_rate"] == Decimal("100.00")
    assert result["quality_acceptance_rate"] == Decimal("100.00")


def test_supplier_evaluation_no_history_is_not_poor_performance():
    from unittest.mock import Mock
    from app.services.supplier_evaluation_service import _evaluate_one

    cursor = Mock()
    cursor.fetchone.side_effect = [
        {
            "id": 7,
            "status": "ACTIVE",
            "supplier_name": "Supplier A",
            "organization_status": "ACTIVE",
            "verification_status": "VERIFIED",
        },
        {"item_name": "Maize flour"},
        {"required_item_match": True},
        None,
        {
            "evaluation_status": "ELIGIBLE",
            "historical_evidence_status": "NO_HISTORY",
            "indicator_explanation": "Eligible based on current supplier and item evidence; no historical delivery evidence is available.",
        },
    ]

    result = _evaluate_one(
        cursor,
        {"id": 1},
        supplier_id=7,
        user_id=100,
    )

    assert result["evaluation_status"] == "ELIGIBLE"
    assert result["historical_evidence_status"] == "NO_HISTORY"
    assert "no historical delivery evidence" in result["indicator_explanation"]
    assert "POOR PERFORMANCE" not in result["indicator_explanation"]


def test_supplier_evaluation_unverified_supplier_is_ineligible():
    from unittest.mock import Mock
    from app.services.supplier_evaluation_service import _evaluate_one

    cursor = Mock()
    cursor.fetchone.side_effect = [
        {
            "id": 8,
            "status": "ACTIVE",
            "supplier_name": "Supplier B",
            "organization_status": "ACTIVE",
            "verification_status": "PENDING",
        },
        {"item_name": "Maize flour"},
        {"required_item_match": True},
        None,
        {
            "evaluation_status": "INELIGIBLE",
            "historical_evidence_status": "NO_HISTORY",
            "mandatory_eligible": False,
        },
    ]

    result = _evaluate_one(cursor, {"id": 1}, supplier_id=8, user_id=100)

    assert result["evaluation_status"] == "INELIGIBLE"
    assert result["mandatory_eligible"] is False
