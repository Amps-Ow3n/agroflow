from fastapi import APIRouter, Depends

from app.core.dependencies import (
    require_membership_responsibility_manage,
)

from app.schemas.membership_schema import (
    AddMembershipResponsibilityRequest,
)

from app.services.membership_service import (
    add_membership_responsibility,
    list_organization_members,
    list_assignable_responsibilities,
)


router = APIRouter(
    prefix="/organizations",
    tags=["Organization Memberships"],
)


@router.get(
    "/{organization_id}/memberships",
)
def get_organization_members(
    organization_id: int,
    user=Depends(
        require_membership_responsibility_manage
    ),
):

    return {
        "members": list_organization_members(
            organization_id
        )
    }


@router.get(
    "/{organization_id}/responsibilities",
)
def get_assignable_responsibilities(
    organization_id: int,
    user=Depends(
        require_membership_responsibility_manage
    ),
):

    return {
        "responsibilities":
            list_assignable_responsibilities(
                organization_id
            )
    }


@router.post(
    "/{organization_id}/memberships/"
    "{user_id}/responsibilities",
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
        responsibility_code=(
            payload.responsibility_code
        ),
        actor_user_id=user["user"]["id"],
    )