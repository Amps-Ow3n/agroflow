from pydantic import BaseModel, Field
from datetime import date, datetime


class SupplySourceCreate(BaseModel):
    actor_type: str
    product: str
    qty_available: int = Field(..., gt=0)
    location: str
    available_from: date
    available_to: date

class SupplySourceUpdate(BaseModel):
    qty_available: int | None = Field(None, gt=0)
    available_from: date | None = None
    available_to: date | None = None

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