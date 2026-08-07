from pydantic import (
BaseModel,
Field,
field_validator,
model_validator
)
from datetime import date, datetime
from typing import Optional

class DeliveryLogCreate(BaseModel):
    delivered_qty: int = Field(
        ...,
        gt=0
    )

    week_start: date

    week_end: date


    @model_validator(mode="after")

    def validate_dates(self):

        if self.week_end < self.week_start:

            raise ValueError(
                "week_end cannot be before week_start."
            )

        return self
    
class DeliveryVerify(BaseModel):

    received_qty: int = Field(
        ...,
        ge=0
    )

    quality_status: str

    delay_status: str

    verification_status: str

    verification_notes: Optional[str] = Field(
        default=None,
        max_length=500
    )


    @field_validator(

        "quality_status",

        "delay_status",

        "verification_status"

    )

    @classmethod

    def normalize(cls, value):

        value = value.strip().upper()

        if not value:

            raise ValueError(
                "Field cannot be blank."
            )

        return value
    
class DeliveryOut(BaseModel):
    id: int
    commitment_id: int
    delivered_qty: int
    received_qty: Optional[int]
    week_start: date
    week_end: date
    verification_status: Optional[str]
    quality_status: Optional[str]
    delay_status: Optional[str]
    verified_by: Optional[int]
    verified_at: Optional[datetime]