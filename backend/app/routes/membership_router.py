from fastapi import APIRouter, Depends

from app.core.dependencies import (
    require_membership_responsibility_manage,
)
from app.schemas.membership_schema import (
    AddMembershipResponsibilityRequest,
)
from app.services.membership_service import (
    add_membership_responsibility,
)


router = APIRouter(
    prefix="/organizations",
    tags=["Organization Memberships"],
)


@router.post(
    "/{organization_id}/memberships/{user_id}/responsibilities",
)
def add_responsibility(
    organization_id: int,
    user_id: int,
    payload: AddMembershipResponsibilityRequest,
    user=Depends(
        require_membership_responsibility_manage
    ),
):
    return add_membership_responsibility(
        organization_id=organization_id,
        target_user_id=user_id,
        responsibility_code=payload.responsibility_code,
        actor_user_id=user["user"]["id"],
    )