from pydantic import BaseModel, EmailStr


class AddMembershipResponsibilityRequest(
    BaseModel
):
    responsibility_code: str

class AddOrganizationMemberRequest(
    BaseModel
):
    email: EmailStr
    responsibility_code: str