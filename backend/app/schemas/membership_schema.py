from pydantic import BaseModel, Field


class AddMembershipResponsibilityRequest(BaseModel):
    responsibility_code: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )