from pydantic import (
    Field,
    EmailStr,
    field_validator,
    model_validator
)

from app.schemas.base import AgroFlowRequest

from datetime import datetime


class UserRegister(AgroFlowRequest):

    full_name: str = Field(
        ...,
        min_length=2,
        max_length=100
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=72
    )

    organization_name: str = Field(
        ...,
        min_length=2,
        max_length=200
    )

    organization_type: str

    responsibility: str


    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Full name cannot be blank."
            )

        return value


    @field_validator("organization_name")
    @classmethod
    def validate_organization_name(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Organization name cannot be blank."
            )

        return value


    @field_validator("organization_type")
    @classmethod
    def validate_organization_type(cls, value):

        value = value.strip().upper()

        allowed = {
            "SCHOOL",
            "SUPPLIER"
        }

        if value not in allowed:

            raise ValueError(
                "Invalid organization type."
            )

        return value


    @field_validator("responsibility")
    @classmethod
    def validate_responsibility(cls, value):

        value = value.strip().upper()

        allowed = {
            "ORGANIZATION_ADMIN",
            "PROCUREMENT_OFFICER",
            "PROCUREMENT_REVIEWER",
            "RECEIVING_OFFICER",
            "SUPPLIER_USER",
            "SUPPLIER_ADMIN"
        }

        if value not in allowed:

            raise ValueError(
                "Invalid responsibility."
            )

        return value

    @model_validator(mode="after")
    def validate_responsibility_for_organization(self):

        school_responsibilities = {
            "ORGANIZATION_ADMIN",
            "PROCUREMENT_OFFICER",
            "PROCUREMENT_REVIEWER",
            "RECEIVING_OFFICER"
        }

        supplier_responsibilities = {
            "ORGANIZATION_ADMIN",
            "SUPPLIER_USER",
            "SUPPLIER_ADMIN"
        }

        if self.organization_type == "SCHOOL":

            if self.responsibility not in school_responsibilities:

                raise ValueError(
                    "This responsibility is not valid for a school."
                )

        elif self.organization_type == "SUPPLIER":

            if self.responsibility not in supplier_responsibilities:

                raise ValueError(
                    "This responsibility is not valid for a supplier."
                )

        return self
class UserLogin(AgroFlowRequest):

    email: EmailStr

    password: str


class UserOut(AgroFlowRequest):

    id: int

    full_name: str

    email: EmailStr

    status: str

    is_system_admin: bool

    created_at: datetime

class OrganizationOut(AgroFlowRequest):

    id: int

    name: str

    organization_type: str

    status: str

    verification_status: str


class ResponsibilityOut(AgroFlowRequest):

    code: str

    name: str


class MembershipOut(AgroFlowRequest):

    id: int

    organization: OrganizationOut

    responsibilities: list[ResponsibilityOut]