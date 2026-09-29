from fastapi import (
    APIRouter,
    Depends,
)

from app.core.dependencies import (
    require_organization_manage_members,
)

from app.services.organization_membership_service import (
    list_organization_members,
    list_assignable_responsibilities,
    add_membership_responsibility,
)


router = APIRouter(
    prefix="/organizations",
    tags=["Organization Members"],
)


@router.get(
    "/{organization_id}/members"
)
def get_members(
    organization_id: int,
    user=Depends(
        require_organization_manage_members
    ),
):
    return {
        "members": list_organization_members(
            organization_id
        )
    }


@router.get(
    "/{organization_id}/responsibilities"
)
def get_responsibilities(
    organization_id: int,
    user=Depends(
        require_organization_manage_members
    ),
):
    return {
        "responsibilities":
            list_assignable_responsibilities(
                organization_id
            )
    }


@router.post(
    "/{organization_id}/members/"
    "{user_id}/responsibilities"
)
def assign_responsibility(
    organization_id: int,
    user_id: int,
    payload: dict,
    identity=Depends(
        require_organization_manage_members
    ),
):
    return add_membership_responsibility(
        organization_id=organization_id,
        target_user_id=user_id,
        responsibility_code=payload[
            "responsibility_code"
        ],
        actor_user_id=identity[
            "user"
        ]["id"],
    )