from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator
)
from datetime import date, datetime

class SupplySourceCreate(BaseModel):

    actor_type: str

    product: str = Field(
        ...,
        min_length=2,
        max_length=100
    )

    qty_available: int = Field(
        ...,
        gt=0
    )

    location: str = Field(
        ...,
        min_length=2,
        max_length=150
    )

    available_from: date

    available_to: date


    @field_validator(
        "actor_type",
        "product",
        "location"
    )

    @classmethod
    def normalize_text(cls, value):

        value = value.strip()

        if not value:

            raise ValueError(
                "Field cannot be blank."
            )

        return value.lower()


    @model_validator(mode="after")

    def validate_dates(self):

        if self.available_to < self.available_from:

            raise ValueError(
                "available_to cannot be before available_from."
            )

        return self
    
class SupplySourceUpdate(BaseModel):

    qty_available: int | None = Field(
        None,
        gt=0
    )

    available_from: date | None = None

    available_to: date | None = None


    @model_validator(mode="after")

    def validate_dates(self):

        if (

            self.available_from

            and

            self.available_to

            and

            self.available_to < self.available_from

        ):

            raise ValueError(
                "available_to cannot be before available_from."
            )

        return self
    
class SupplySourceOut(BaseModel):
    id: int
    actor_id: int
    actor_type: str
    actor_name: str
    product: str
    qty_available: int
    location: str
    available_from: date
    available_to: date
    last_updated: datetime