from fastapi import APIRouter, Depends

from app.core.dependencies import require_user


router = APIRouter(
    prefix="/identity",
    tags=["Identity"]
)


from app.core.authorization import (
    RESPONSIBILITY_PERMISSIONS,
)


@router.get("/me")
def get_current_identity(
    identity=Depends(require_user),
):
    """
    Return authenticated identity plus derived permissions.

    Permissions are derived server-side from the user's active
    organization responsibilities.

    The frontend may use these for UI decisions, but the backend
    remains authoritative.
    """

    enriched_identity = dict(identity)

    memberships = []

    for membership in identity.get(
        "memberships",
        [],
    ):

        membership_copy = dict(membership)

        permission_set = set()

        for responsibility in membership.get(
            "responsibilities",
            [],
        ):

            responsibility_code = responsibility.get(
                "code"
            )

            permission_set.update(
                RESPONSIBILITY_PERMISSIONS.get(
                    responsibility_code,
                    frozenset(),
                )
            )

        membership_copy["permissions"] = sorted(
            permission_set
        )

        memberships.append(
            membership_copy
        )

    enriched_identity["memberships"] = memberships

    return enriched_identity

@router.get("/memberships")
def get_my_memberships(
    identity=Depends(require_user)
):

    return {
        "memberships": identity["memberships"]
    }

@router.get("/organization")
def get_current_organization(
    identity=Depends(require_user),
):
    """
    Compatibility endpoint.

    If the user has exactly one active organization membership,
    return it.

    If the user belongs to multiple organizations, do not
    silently select one.
    """

    active_memberships = [
        membership
        for membership in identity.get("memberships", [])
        if membership.get("status") == "ACTIVE"
        and membership.get("organization", {}).get("status") == "ACTIVE"
        and membership.get("organization", {}).get("verification_status") == "VERIFIED"
    ]

    if not active_memberships:
        return {
            "organization": None
        }

    if len(active_memberships) > 1:
        return {
            "organization": None,
            "requires_organization_selection": True,
            "organizations": [
                membership["organization"]
                for membership in active_memberships
            ],
        }

    return {
        "organization": active_memberships[0]["organization"]
    }