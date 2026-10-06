from fastapi import APIRouter, Depends

from app.core.dependencies import (
    require_membership_responsibility_manage,
)
from app.schemas.membership_schema import (
    AddMembershipResponsibilityRequest,
    AddOrganizationMemberRequest,
    MembershipDecisionRequest,
)
from app.services.membership_service import (
    add_membership_responsibility,
    add_organization_member,
    list_organization_members,
    list_assignable_responsibilities,
    decide_membership_request,
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

@router.post(
    "/{organization_id}/memberships",
)
def add_member(
    organization_id: int,
    payload: AddOrganizationMemberRequest,
    user=Depends(
        require_membership_responsibility_manage
    ),
):
    return add_organization_member(
        organization_id=organization_id,
        email=str(payload.email),
        responsibility_code=(
            payload.responsibility_code
        ),
        actor_user_id=user["user"]["id"],
    )

@router.post("/{organization_id}/memberships/{membership_id}/decision")
def decide_membership(
    organization_id: int,
    membership_id: int,
    payload: MembershipDecisionRequest,
    user=Depends(require_membership_responsibility_manage),
):
    return decide_membership_request(
        organization_id=organization_id,
        membership_id=membership_id,
        decision=payload.decision,
        actor_user_id=user["user"]["id"],
    )
