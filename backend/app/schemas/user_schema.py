from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator
)
from datetime import datetime

class UserRegister(BaseModel):

    name: str = Field(..., min_length=2, max_length=100)

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=72
    )

    role: str


    @field_validator("name")
    @classmethod
    def validate_name(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Name cannot be blank."
            )

        return value


    @field_validator("role")
    @classmethod
    def validate_role(cls, value):

        value = value.strip().lower()

        allowed = {

            "supplier",
            "farmer",
            "processor",
            "cooperative",
            "trader",
            "school",
            "buyer"

        }

        if value not in allowed:

            raise ValueError(
                "Invalid role."
            )

        return value

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    created_at: datetime