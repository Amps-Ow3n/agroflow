from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.procurement_schema import (
    ProcurementCreate,
    PurchaseOrderCreate,
)
from app.schemas.commitment_schema import (
    SupplierCommitmentCreate,
)
from app.schemas.delivery_schema import (
    DeliveryCreate,
    DeliveryLineCreate,
    InspectionCreate,
    CorrectiveActionCreate,
)


def valid_procurement():
    return {
        "title": "Maize procurement",
        "required_by_date": date(2026, 10, 1),
        "item_name": "Maize flour",
        "quantity": Decimal("500.00"),
        "unit": "kg",
        "location": "Kampala",
        "procurement_method": "QUOTATION",
    }


def test_procurement_quantity_must_be_positive():

    data = valid_procurement()

    data["quantity"] = Decimal("0")

    with pytest.raises(ValidationError):
        ProcurementCreate(**data)


def test_procurement_rejects_unknown_fields():

    data = valid_procurement()

    data["unexpected_field"] = "attack"

    with pytest.raises(ValidationError):
        ProcurementCreate(**data)


def test_procurement_required_date_cannot_precede_procurement_date():

    data = valid_procurement()

    data["procurement_date"] = date(2026, 10, 5)

    with pytest.raises(ValidationError):
        ProcurementCreate(**data)


def test_procurement_method_is_normalized():

    data = valid_procurement()

    data["procurement_method"] = " quotation "

    result = ProcurementCreate(**data)

    assert result.procurement_method == "QUOTATION"


def test_po_requires_at_least_one_line():

    with pytest.raises(ValidationError):

        PurchaseOrderCreate(
            lines=[]
        )


def test_commitment_delivery_window_is_valid():

    result = SupplierCommitmentCreate(
        purchase_order_line_id=1,
        promised_qty=Decimal("500.00"),
        delivery_start=date(2026, 10, 1),
        delivery_end=date(2026, 10, 3),
    )

    assert result.delivery_start < result.delivery_end


def test_commitment_delivery_end_cannot_precede_start():

    with pytest.raises(ValidationError):

        SupplierCommitmentCreate(
            purchase_order_line_id=1,
            promised_qty=Decimal("500.00"),
            delivery_start=date(2026, 10, 5),
            delivery_end=date(2026, 10, 3),
        )


def test_delivery_requires_lines():

    with pytest.raises(ValidationError):

        DeliveryCreate(
            commitment_id=1,
            delivery_date=date(2026, 10, 2),
            condition="Good",
            lines=[]
        )


def test_delivery_actual_quantity_cannot_be_negative():

    with pytest.raises(ValidationError):

        DeliveryLineCreate(
            procurement_item_id=1,
            actual_quantity=Decimal("-1")
        )


def test_rejected_inspection_requires_reason():

    with pytest.raises(ValidationError):

        InspectionCreate(
            received_qty=Decimal("400"),
            result="REJECTED",
            quality_status="FAILED",
            delay_status="ON_TIME",
        )


def test_accepted_inspection_cannot_have_rejection_reason():

    with pytest.raises(ValidationError):

        InspectionCreate(
            received_qty=Decimal("500"),
            result="ACCEPTED",
            quality_status="GOOD",
            delay_status="ON_TIME",
            rejection_reason="Some reason",
        )


def test_corrective_action_description_required():

    with pytest.raises(ValidationError):

        CorrectiveActionCreate(
            description=" "
        )