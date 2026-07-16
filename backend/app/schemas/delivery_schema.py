from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional


class DeliveryLogCreate(BaseModel):
    delivered_qty: int = Field(..., ge=0)
    week_start: date
    week_end: date

class DeliveryVerify(BaseModel):
    received_qty: int = Field(..., ge=0)
    quality_status: str
    delay_status: str
    verification_status: str
    verification_notes: Optional[str] = None

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