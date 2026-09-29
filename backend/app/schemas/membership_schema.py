from pydantic import BaseModel


class AddMembershipResponsibilityRequest(
    BaseModel
):
    responsibility_code: str