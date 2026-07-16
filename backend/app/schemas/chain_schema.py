from pydantic import BaseModel, Field
from datetime import datetime


class ChainLinkCreate(BaseModel):
    source_id: int
    allocated_qty: int = Field(..., gt=0)
    chain_position: int = Field(..., gt=0)


class ChainLinkOut(BaseModel):
    id: int
    commitment_id: int
    source_id: int
    allocated_qty: int
    chain_position: int
    created_at: datetime