from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator, model_validator

from app.schemas.base import (
    AgroFlowRequest,
    PositiveId,
    PositiveQuantity,
    NonNegativeMoney,
)


PROCUREMENT_METHODS = {
    "MICRO_PROCUREMENT",
    "QUOTATION",
    "RESTRICTED_DOMESTIC_BIDDING",
    "OPEN_DOMESTIC_BIDDING",
    "FRAMEWORK_CONTRACT",
    "DIRECT_PROCUREMENT",
}


PROCUREMENT_STATUSES = {
    "DRAFT",
    "SUBMITTED",
    "EVALUATION",
    "SELECTED",
    "ORDERED",
    "COMMITTED",
    "DELIVERY",
    "INSPECTION",
    "ACCEPTED",
    "COMPLETED",
    "CANCELLED",
}


class ProcurementCreate(AgroFlowRequest):

    title: str = Field(
        ...,
        min_length=2,
        max_length=200
    )

    description: Optional[str] = Field(
        default=None,
        max_length=5000
    )

    procurement_date: Optional[date] = None

    required_by_date: date

    item_name: str = Field(
        ...,
        min_length=2,
        max_length=200
    )

    item_description: Optional[str] = Field(
        default=None,
        max_length=5000
    )

    quantity: PositiveQuantity

    unit: str = Field(
        ...,
        min_length=1,
        max_length=50
    )

    location: str = Field(
        ...,
        min_length=2,
        max_length=200
    )

    specifications: Optional[str] = Field(
        default=None,
        max_length=5000
    )

    quality_requirements: Optional[str] = Field(
        default=None,
        max_length=5000
    )

    estimated_cost: Optional[NonNegativeMoney] = None

    procurement_method: str = Field(
        ...,
        min_length=2,
        max_length=80
    )

    notes: Optional[str] = Field(
        default=None,
        max_length=5000
    )

    requesting_department: Optional[str] = Field(
        default=None,
        max_length=200
    )

    @field_validator(
        "title",
        "item_name",
        "unit",
        "location",
        "procurement_method",
        "requesting_department",
        mode="before"
    )
    @classmethod
    def normalize_text(cls, value):

        if value is None:
            return value

        value = value.strip()

        if not value:
            raise ValueError(
                "Field cannot be blank."
            )

        return value

    @field_validator("procurement_method")
    @classmethod
    def validate_procurement_method(cls, value):

        value = value.upper()

        if value not in PROCUREMENT_METHODS:
            raise ValueError(
                "Invalid procurement method."
            )

        return value

    @model_validator(mode="after")
    def validate_dates(self):

        if (
            self.procurement_date is not None
            and self.required_by_date < self.procurement_date
        ):
            raise ValueError(
                "required_by_date cannot be before procurement_date."
            )

        return self


class ProcurementUpdate(ProcurementCreate):
    pass


class ProcurementCancel(AgroFlowRequest):

    reason: str = Field(
        ...,
        min_length=3,
        max_length=1000
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Cancellation reason is required."
            )

        return value


class ProcurementTransition(AgroFlowRequest):

    status: str = Field(
        ...,
        min_length=2,
        max_length=30
    )

    reason: Optional[str] = Field(
        default=None,
        max_length=1000
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):

        normalized = value.strip().upper()

        if normalized not in PROCUREMENT_STATUSES:
            raise ValueError(
                "Invalid procurement status."
            )

        return normalized

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value):

        if value is None:
            return None

        value = value.strip()

        return value or None


class PurchaseOrderLineCreate(AgroFlowRequest):

    procurement_item_id: PositiveId

    quantity: PositiveQuantity

    unit_price: Optional[NonNegativeMoney] = None

    description: Optional[str] = Field(
        default=None,
        max_length=2000
    )


class PurchaseOrderCreate(AgroFlowRequest):

    expected_delivery_date: Optional[date] = None

    notes: Optional[str] = Field(
        default=None,
        max_length=5000
    )

    lines: list[PurchaseOrderLineCreate] = Field(
        ...,
        min_length=1,
        max_length=100
    )


# IMPORTANT:
# ProcurementDocumentCreate is legacy.
# Evidence documents are handled by the evidence-document
# endpoint and schema.