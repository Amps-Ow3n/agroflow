from pydantic import Field, field_validator

from app.schemas.base import (
    AgroFlowRequest,
    PositiveId,
)


class SupplierSelectionCreate(
    AgroFlowRequest
):

    supplier_id: PositiveId

    decision_reason: str = Field(
        ...,
        min_length=3,
        max_length=2000
    )

    @field_validator("decision_reason")
    @classmethod
    def normalize_reason(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Decision reason is required."
            )

        return value


class SupplierReselectionCreate(
    AgroFlowRequest
):

    supplier_id: PositiveId

    decision_reason: str = Field(
        ...,
        min_length=3,
        max_length=2000
    )

    @field_validator("decision_reason")
    @classmethod
    def normalize_reason(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Decision reason is required."
            )

        return value