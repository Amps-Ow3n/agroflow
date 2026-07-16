from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional
from pydantic import field_validator

class SupplierCommitmentCreate(BaseModel):
    school_id: int
    product: str
    promised_qty: int = Field(..., gt=0)
    delivery_start: date
    delivery_end: date

    @field_validator("product")
    @classmethod
    def normalize_product(cls, value):

        return value.strip().lower()

class SupplierCommitmentUpdate(BaseModel):
    promised_qty: Optional[int] = Field(None, gt=0)
    delivery_start: Optional[date] = None
    delivery_end: Optional[date] = None
    status: Optional[str] = None


class SupplierCommitmentOut(BaseModel):
    id: int
    supplier_id: int
    school_id: int
    product: str
    promised_qty: int
    delivery_start: date
    delivery_end: date
    chain_id: Optional[int]
    status: str
    created_at: datetime