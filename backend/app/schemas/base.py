from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class AgroFlowRequest(BaseModel):
    """
    Base class for all client request schemas.

    Unknown fields are rejected so the API contract
    cannot silently accept undeclared input.
    """

    model_config = ConfigDict(
        extra="forbid"
    )


PositiveId = Annotated[
    int,
    Field(gt=0)
]


PositiveQuantity = Annotated[
    Decimal,
    Field(
        gt=0,
        max_digits=16,
        decimal_places=2
    )
]


NonNegativeQuantity = Annotated[
    Decimal,
    Field(
        ge=0,
        max_digits=16,
        decimal_places=2
    )
]


NonNegativeMoney = Annotated[
    Decimal,
    Field(
        ge=0,
        max_digits=16,
        decimal_places=2
    )
]