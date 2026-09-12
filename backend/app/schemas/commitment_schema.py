from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator, model_validator

from app.schemas.base import (
    AgroFlowRequest,
    PositiveId,
    PositiveQuantity,
)


class SupplierCommitmentCreate(AgroFlowRequest):

    purchase_order_line_id: PositiveId

    promised_qty: PositiveQuantity

    delivery_start: date

    delivery_end: date

    @model_validator(mode="after")
    def validate_delivery_window(self):

        if self.delivery_end < self.delivery_start:
            raise ValueError(
                "delivery_end cannot be before delivery_start."
            )

        return self


class SupplierCommitmentAccept(
    AgroFlowRequest
):
    pass


class SupplierCommitmentReject(
    AgroFlowRequest
):

    reason: str = Field(
        ...,
        min_length=2,
        max_length=500
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Rejection reason is required."
            )

        return value


class SupplierCommitmentOut(
    AgroFlowRequest
):

    id: int

    purchase_order_id: int

    purchase_order_line_id: int

    supplier_id: int

    supplier_name: Optional[str]

    product: str

    promised_qty: Decimal

    delivery_start: date

    delivery_end: date

    capacity_available: Optional[Decimal]

    capacity_sufficient: Optional[bool]

    status: str

    submitted_by: Optional[int]

    submitted_at: Optional[datetime]

    accepted_by: Optional[int]

    accepted_at: Optional[datetime]

    rejection_reason: Optional[str]

    created_at: datetime