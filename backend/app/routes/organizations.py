from fastapi import APIRouter, Depends

from app.core.dependencies import require_system_admin

from app.schemas.verification_schema import (
    VerificationDecision,
)

from app.services.organization_verification_service import (
    list_pending_verifications,
    get_verification,
    decide_verification,
)


router = APIRouter(
    prefix="/organizations",
    tags=["Organizations"],
)


@router.get("/verifications/pending")
def get_pending_verifications(
    identity=Depends(require_system_admin),
):

    return {
        "verifications": (
            list_pending_verifications()
        )
    }


@router.get("/{organization_id}/verification")
def get_organization_verification(
    organization_id: int,
    identity=Depends(require_system_admin),
):

    return get_verification(
        organization_id
    )


@router.post(
    "/{organization_id}/verification/decision"
)
def decide_organization_verification(
    organization_id: int,
    payload: VerificationDecision,
    identity=Depends(require_system_admin),
):

    return decide_verification(
        organization_id=organization_id,
        decision=payload.decision,
        reason=payload.reason,
        reviewer_id=identity["user"]["id"],
    )