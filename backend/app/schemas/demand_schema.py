from datetime import date

from pydantic import (
    BaseModel,
    Field,
    field_validator
)


class DemandCreate(BaseModel):

    product: str = Field(
        ...,
        min_length=2,
        max_length=100
    )

    quantity: float = Field(
        ...,
        gt=0
    )

    location: str = Field(
        ...,
        min_length=2,
        max_length=150
    )

    delivery_start: date

    delivery_end: date


    @field_validator("product")
    @classmethod
    def validate_product(cls, value):

        value = value.strip().lower()

        if not value:
            raise ValueError(
                "Product cannot be blank."
            )

        return value


    @field_validator("location")
    @classmethod
    def validate_location(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Location cannot be blank."
            )

        return value


class DemandUpdate(DemandCreate):
    pass