from typing import Optional

from pydantic import Field, field_validator

from app.schemas.base import (
    AgroFlowRequest,
    PositiveId,
)


SUPPLIER_STATUSES = {
    "ACTIVE",
    "SUSPENDED",
    "INACTIVE",
}


class SupplierCreate(AgroFlowRequest):

    organization_id: PositiveId


class SupplierUpdate(AgroFlowRequest):

    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):

        if value is None:
            return None

        value = value.strip().upper()

        if value not in SUPPLIER_STATUSES:
            raise ValueError(
                "Invalid supplier status."
            )

        return value


class CapabilityCreate(AgroFlowRequest):

    capability: str = Field(
        ...,
        min_length=1,
        max_length=150
    )

    @field_validator("capability")
    @classmethod
    def normalize_capability(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Capability cannot be blank."
            )

        return value


class ProductCreate(AgroFlowRequest):

    product: str = Field(
        ...,
        min_length=1,
        max_length=150
    )

    @field_validator("product")
    @classmethod
    def normalize_product(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Product cannot be blank."
            )

        return value


class ContactCreate(AgroFlowRequest):

    contact_name: str = Field(
        ...,
        min_length=1,
        max_length=150
    )

    phone: Optional[str] = Field(
        default=None,
        max_length=50
    )

    email: Optional[str] = Field(
        default=None,
        max_length=254
    )

    role: Optional[str] = Field(
        default=None,
        max_length=100
    )

    is_primary: bool = False