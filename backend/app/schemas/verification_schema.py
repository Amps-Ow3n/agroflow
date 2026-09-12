from typing import Literal

from pydantic import Field, model_validator

from app.schemas.base import AgroFlowRequest


class VerificationDecision(AgroFlowRequest):

    decision: Literal[
        "VERIFIED",
        "REJECTED",
    ]

    reason: str | None = Field(
        default=None,
        max_length=1000,
    )

    @model_validator(mode="after")
    def validate_decision(self):

        if self.decision == "REJECTED":

            if self.reason is None:
                raise ValueError(
                    "A rejection reason is required."
                )

            if not self.reason.strip():
                raise ValueError(
                    "A rejection reason cannot be blank."
                )

        return self