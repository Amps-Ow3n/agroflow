from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from typing import Literal
from pydantic import (
    Field,
    field_validator,
    model_validator,
)
from app.schemas.base import (
    AgroFlowRequest,
    PositiveId,
    NonNegativeQuantity,
)


class DeliveryLineCreate(AgroFlowRequest):

    procurement_item_id: PositiveId

    actual_quantity: NonNegativeQuantity


class DeliveryCreate(AgroFlowRequest):

    commitment_id: PositiveId

    parent_delivery_id: Optional[PositiveId] = None

    delivery_date: date

    condition: str = Field(
        ...,
        min_length=1,
        max_length=1000
    )

    notes: Optional[str] = Field(
        default=None,
        max_length=5000
    )

    lines: list[DeliveryLineCreate] = Field(
        ...,
        min_length=1,
        max_length=100
    )

    @field_validator("condition")
    @classmethod
    def normalize_condition(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Delivery condition is required."
            )

        return value


class InspectionCreate(AgroFlowRequest):

    received_qty: NonNegativeQuantity

    result: Literal[
        "ACCEPTED",
        "REJECTED"
    ]

    quality_status: Literal[
        "GOOD",
        "FAILED"
    ]

    delay_status: Literal[
        "ON_TIME",
        "DELAYED"
    ]

    rejection_reason: Optional[str] = Field(
        default=None,
        max_length=1000
    )

    notes: Optional[str] = Field(
        default=None,
        max_length=2000
    )

    @field_validator(
        "rejection_reason",
        "notes"
    )
    @classmethod
    def normalize_text(cls, value):

        if value is None:
            return None

        value = value.strip()

        return value or None

    @model_validator(mode="after")
    def validate_rejection(self):

        if (
            self.result == "REJECTED"
            and not self.rejection_reason
        ):
            raise ValueError(
                "A rejection reason is required."
            )

        if (
            self.result == "ACCEPTED"
            and self.rejection_reason
        ):
            raise ValueError(
                "An accepted inspection cannot have "
                "a rejection reason."
            )

        return self


class CorrectiveActionCreate(
    AgroFlowRequest
):

    description: str = Field(
        ...,
        min_length=2,
        max_length=2000
    )

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Corrective action description is required."
            )

        return value


class DeliveryOut(AgroFlowRequest):

    id: int
    commitment_id: int
    receiving_user_id: int
    delivery_date: date
    condition: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    lines: list[dict]


class InspectionOut(AgroFlowRequest):

    id: int
    delivery_id: int
    result: str
    received_qty: Decimal
    quality_status: str
    delay_status: str
    rejection_reason: Optional[str]
    notes: Optional[str]
    inspected_by: int
    inspected_by_name: Optional[str]
    inspected_at: datetime


class CorrectiveActionOut(
    AgroFlowRequest
):

    id: int
    inspection_id: int
    description: str
    status: str
    replacement_delivery_id: Optional[int]
    created_by: int
    created_by_name: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]