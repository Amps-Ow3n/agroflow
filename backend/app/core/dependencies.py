import secrets
from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)

from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.auth import decode_access_token
from app.core.db import get_db
from app.core.logger import log_warning
from app.core.security import get_auth_token

from app.services.identity_service import (
    get_user_identity,
)

from app.core.authorization import (
    PERMISSION_ORGANIZATION_VIEW,
    PERMISSION_ORGANIZATION_UPDATE,
    PERMISSION_ORGANIZATION_MANAGE_MEMBERS,

    PERMISSION_PROCUREMENT_VIEW,
    PERMISSION_PROCUREMENT_CREATE,
    PERMISSION_PROCUREMENT_UPDATE,
    PERMISSION_PROCUREMENT_SUBMIT,
    PERMISSION_PROCUREMENT_EVALUATE,
    PERMISSION_PROCUREMENT_SELECT,
    PERMISSION_PROCUREMENT_CANCEL,
    PERMISSION_PROCUREMENT_TRANSITION,

    PERMISSION_PURCHASE_ORDER_VIEW,
    PERMISSION_PURCHASE_ORDER_CREATE,

    PERMISSION_COMMITMENT_VIEW,
    PERMISSION_COMMITMENT_CREATE,
    PERMISSION_COMMITMENT_ACCEPT,
    PERMISSION_COMMITMENT_REJECT,

    PERMISSION_DELIVERY_VIEW,
    PERMISSION_DELIVERY_CREATE,
    PERMISSION_DELIVERY_INSPECT,

    PERMISSION_INSPECTION_CREATE,
    PERMISSION_INSPECTION_ACCEPT,
    PERMISSION_INSPECTION_REJECT,

    PERMISSION_CORRECTIVE_ACTION_CREATE,

    PERMISSION_EVIDENCE_VIEW,
    PERMISSION_EVIDENCE_UPLOAD,
    PERMISSION_EVIDENCE_DELETE,

    PERMISSION_SUPPLIER_VIEW,
    PERMISSION_SUPPLIER_UPDATE,
    PERMISSION_SUPPLIER_MANAGE_CAPABILITIES,

    PERMISSION_SUPPLIER_PERFORMANCE_VIEW,

    PERMISSION_DASHBOARD_VIEW,

    PERMISSION_REALITY_REPORT_VIEW,

    get_authorized_membership,
)

from app.core.resource_authorization import (
    get_resource_organization_ids,
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="login",
    auto_error=False,
)


# =========================================================
# AUTHENTICATED USER
# =========================================================

def require_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
):

    token = get_auth_token(request, token)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = decode_access_token(token)

    user_id = payload.get("id")

    if not user_id:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )

    identity = get_user_identity(
        int(user_id)
    )

    if not identity:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identity not found",
        )

    if identity["user"]["status"] != "ACTIVE":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )

    return identity


# =========================================================
# PLATFORM SYSTEM ADMIN
# =========================================================

def require_system_admin(
    user=Depends(require_user),
):

    if not user["user"]["is_system_admin"]:

        log_warning(
            message="Platform administration access denied",
            user_id=user["user"]["id"],
            action="SYSTEM_ADMIN_ACCESS_DENIED",
            entity="platform",
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System administrator access required.",
        )

    return user


# =========================================================
# MEMBERSHIP LOOKUP
# =========================================================

def get_membership_for_organization(
    identity,
    organization_id: int,
):
    """
    Return the user's membership for exactly one organization.

    This function performs lookup only.

    It does not grant authorization.
    """

    for membership in identity.get(
        "memberships",
        [],
    ):

        organization = membership.get(
            "organization",
            {},
        )

        if organization.get(
            "id"
        ) == organization_id:

            return membership

    return None


# =========================================================
# VERIFIED ORGANIZATION MEMBERSHIP
# =========================================================

def get_verified_organization_membership(
    identity,
    organization_type: str,
):
    """
    Resolve exactly one active + verified organization of the
    requested type.

    Used for operations where the organization is implicit,
    such as:

        POST /procurements
        GET /suppliers/me
    """

    expected_type = (
        organization_type
        .strip()
        .upper()
    )

    matches = []

    for membership in identity.get(
        "memberships",
        [],
    ):

        if membership.get(
            "status"
        ) != "ACTIVE":
            continue

        organization = membership.get(
            "organization",
            {},
        )

        if organization.get(
            "status"
        ) != "ACTIVE":
            continue

        if organization.get(
            "verification_status"
        ) != "VERIFIED":
            continue

        if organization.get(
            "organization_type"
        ) != expected_type:
            continue

        matches.append(
            membership
        )

    if not matches:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "No active verified "
                f"{expected_type.lower()} organization "
                "is available to this user."
            ),
        )

    if len(matches) > 1:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Multiple active verified "
                f"{expected_type.lower()} organizations "
                "are associated with this user. "
                "An explicit organization context is required."
            ),
        )

    return matches[0]


# =========================================================
# ORGANIZATION MEMBERSHIP
# =========================================================

def require_organization_member(
    organization_id: int,
    user=Depends(require_user),
):

    membership = get_membership_for_organization(
        user,
        organization_id,
    )

    if not membership:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not belong to this organization."
            ),
        )

    if membership.get(
        "status"
    ) != "ACTIVE":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your membership in this organization "
                "is not active."
            ),
        )

    organization = membership.get(
        "organization",
        {},
    )

    if organization.get(
        "status"
    ) != "ACTIVE":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This organization is not active."
            ),
        )

    if organization.get(
        "verification_status"
    ) != "VERIFIED":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This organization has not been verified."
            ),
        )

    return membership


# =========================================================
# PERMISSION DEPENDENCY
# =========================================================

def require_permission(
    permission: str,
    resource_type: str | None = None,
    organization_type: str | tuple[str, ...] | None = None,
):
    """
    Central authorization dependency.

    If resource_type is supplied:

        authenticate
            ↓
        resource exists
            ↓
        resolve resource organization
            ↓
        find user's membership in that organization
            ↓
        verify active membership
            ↓
        verify active + verified organization
            ↓
        verify permission in THAT membership

    If resource_type is None:

        resolve an organization from the authenticated identity
        and verify the permission there.

    This prevents cross-organization authorization.
    """

    def wrapper(
        request: Request,
        user=Depends(require_user),
    ):

        # -------------------------------------------------
        # RESOURCE-SCOPED AUTHORIZATION
        # -------------------------------------------------

        if resource_type is not None:

            parameter_name = {
                "procurement": "procurement_id",
                "purchase_order": "order_id",
                "commitment": "commitment_id",
                "delivery": "delivery_id",
                "inspection": "inspection_id",
                "supplier": "supplier_id",
            }.get(resource_type)

            if parameter_name is None:

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Authorization configuration error."
                    ),
                )

            raw_resource_id = request.path_params.get(
                parameter_name
            )

            if raw_resource_id is None:

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Authorization configuration error: "
                        f"missing {parameter_name}."
                    ),
                )

            try:

                resource_id = int(
                    raw_resource_id
                )

            except (
                TypeError,
                ValueError,
            ):

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid resource identifier.",
                )

            conn, cursor = get_db()

            try:

                organization_ids = (
                    get_resource_organization_ids(
                        cursor,
                        resource_type,
                        resource_id,
                    )
                )

                if not organization_ids:

                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Resource not found.",
                    )

                authorized_membership = None

                for organization_id in organization_ids:

                    membership = (
                        get_authorized_membership(
                            user,
                            permission,
                            organization_id=organization_id,
                        )
                    )

                    if not membership:
                        continue

                    organization = (
                        membership.get(
                            "organization",
                            {},
                        )
                    )

                    if organization.get(
                        "status"
                    ) != "ACTIVE":

                        continue

                    if organization.get(
                        "verification_status"
                    ) != "VERIFIED":

                        continue

                    if organization_type is not None:

                        allowed_types = (
                            organization_type
                            if isinstance(
                                organization_type,
                                tuple,
                            )
                            else (
                                organization_type,
                            )
                        )

                        if organization.get(
                            "organization_type"
                        ) not in allowed_types:

                            continue

                    authorized_membership = membership

                    break

                if authorized_membership:

                    return user

                # -----------------------------------------
                # Supplier registry special visibility rule
                # -----------------------------------------
                #
                # Verified SCHOOL organizations may view
                # supplier registry resources because supplier
                # information is part of procurement decision
                # support.
                #
                # This does NOT give a school permission to
                # modify the supplier's organization.

                if (
                    resource_type == "supplier"
                    and permission
                    in {
                        PERMISSION_SUPPLIER_VIEW,
                        PERMISSION_SUPPLIER_PERFORMANCE_VIEW,
                    }
                ):

                    for membership in user.get(
                        "memberships",
                        [],
                    ):

                        if membership.get(
                            "status"
                        ) != "ACTIVE":
                            continue

                        organization = membership.get(
                            "organization",
                            {},
                        )

                        if (
                            organization.get(
                                "status"
                            ) == "ACTIVE"
                            and organization.get(
                                "verification_status"
                            ) == "VERIFIED"
                            and organization.get(
                                "organization_type"
                            ) == "SCHOOL"
                            and get_authorized_membership(
                                user,
                                permission,
                                organization_id=organization.get(
                                    "id"
                                ),
                            )
                        ):

                            return user

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You do not have permission to "
                        "access this resource."
                    ),
                )

            finally:

                conn.close()

        # -------------------------------------------------
        # ORGANIZATION-SCOPED AUTHORIZATION
        # -------------------------------------------------

        if organization_type is not None:

            allowed_types = (
                organization_type
                if isinstance(
                    organization_type,
                    tuple,
                )
                else (
                    organization_type,
                )
            )

            matches = []

            for membership in user.get(
                "memberships",
                [],
            ):

                if membership.get(
                    "status"
                ) != "ACTIVE":

                    continue

                organization = membership.get(
                    "organization",
                    {},
                )

                if organization.get(
                    "status"
                ) != "ACTIVE":

                    continue

                if organization.get(
                    "verification_status"
                ) != "VERIFIED":

                    continue

                if organization.get(
                    "organization_type"
                ) not in allowed_types:

                    continue

                if get_authorized_membership(
                    user,
                    permission,
                    organization_id=organization.get(
                        "id"
                    ),
                ):

                    matches.append(
                        membership
                    )

            if not matches:

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You do not have the required "
                        "permission in a verified active "
                        "organization."
                    ),
                )

            return user

        # -------------------------------------------------
        # FALLBACK
        # -------------------------------------------------

        membership = get_authorized_membership(
            user,
            permission,
        )

        if not membership:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You do not have permission to "
                    "perform this action."
                ),
            )

        return user

    return wrapper
# =========================================================
# ORGANIZATION PERMISSION HELPER
# =========================================================

def require_organization_permission(
    permission: str,
    organization_id: int,
    user,
):
    """
    Explicit service-level organization authorization.

    Use when the organization ID is already known inside
    application/service code.
    """

    membership = get_authorized_membership(
        user,
        permission,
        organization_id=organization_id,
    )

    if not membership:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have permission in this organization."
            ),
        )

    organization = membership.get(
        "organization",
        {},
    )

    if organization.get(
        "status"
    ) != "ACTIVE":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This organization is not active."
            ),
        )

    if organization.get(
        "verification_status"
    ) != "VERIFIED":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This organization has not been verified."
            ),
        )

    if membership.get(
        "status"
    ) != "ACTIVE":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your membership in this organization "
                "is not active."
            ),
        )

    return membership


# =========================================================
# ORGANIZATION ADMIN
# =========================================================

require_admin = require_permission(
    PERMISSION_ORGANIZATION_UPDATE,
    organization_type=(
        "SCHOOL",
        "SUPPLIER",
    ),
)


# =========================================================
# PROCUREMENT
# =========================================================

require_procurement_viewer = require_permission(
    PERMISSION_PROCUREMENT_VIEW,
    resource_type="procurement",
    organization_type="SCHOOL",
)


require_procurement_manager = require_permission(
    PERMISSION_PROCUREMENT_UPDATE,
    resource_type="procurement",
    organization_type="SCHOOL",
)


require_procurement_officer = require_permission(
    PERMISSION_PROCUREMENT_CREATE,
    organization_type="SCHOOL",
)


require_supplier_evaluation = require_permission(
    PERMISSION_PROCUREMENT_EVALUATE,
    resource_type="procurement",
    organization_type="SCHOOL",
)


# =========================================================
# RECEIVING
# =========================================================

require_receiving_officer = require_permission(
    PERMISSION_DELIVERY_INSPECT,
    resource_type="delivery",
    organization_type="SCHOOL",
)


# =========================================================
# SUPPLIER
# =========================================================

require_supplier_user = require_permission(
    PERMISSION_SUPPLIER_VIEW,
    organization_type="SUPPLIER",
)


# =========================================================
# PROCUREMENT PERMISSIONS
# =========================================================

require_procurement_create = require_permission(
    PERMISSION_PROCUREMENT_CREATE,
    organization_type="SCHOOL",
)

require_procurement_update = require_permission(
    PERMISSION_PROCUREMENT_UPDATE,
    resource_type="procurement",
)

require_procurement_submit = require_permission(
    PERMISSION_PROCUREMENT_SUBMIT,
    resource_type="procurement",
)

require_procurement_select = require_permission(
    PERMISSION_PROCUREMENT_SELECT,
    resource_type="procurement",
)

require_procurement_cancel = require_permission(
    PERMISSION_PROCUREMENT_CANCEL,
    resource_type="procurement",
)

require_procurement_transition = require_permission(
    PERMISSION_PROCUREMENT_TRANSITION,
    resource_type="procurement",
)


# =========================================================
# PURCHASE ORDERS
# =========================================================

require_purchase_order_view = require_permission(
    PERMISSION_PURCHASE_ORDER_VIEW,
    resource_type="purchase_order",
)

require_purchase_order_create = require_permission(
    PERMISSION_PURCHASE_ORDER_CREATE,
    resource_type="procurement",
)


# =========================================================
# COMMITMENTS
# =========================================================

require_commitment_view = require_permission(
    PERMISSION_COMMITMENT_VIEW,
    resource_type="commitment",
)

require_commitment_create = require_permission(
    PERMISSION_COMMITMENT_CREATE,
    resource_type="purchase_order",
    organization_type="SUPPLIER",
)

require_commitment_accept = require_permission(
    PERMISSION_COMMITMENT_ACCEPT,
    resource_type="commitment",
    organization_type="SCHOOL",
)

require_commitment_reject = require_permission(
    PERMISSION_COMMITMENT_REJECT,
    resource_type="commitment",
    organization_type="SCHOOL",
)


# =========================================================
# DELIVERIES
# =========================================================

require_delivery_view = require_permission(
    PERMISSION_DELIVERY_VIEW,
    resource_type="delivery",
)

require_delivery_create = require_permission(
    PERMISSION_DELIVERY_CREATE,
    organization_type="SCHOOL",
)

require_delivery_inspect = require_permission(
    PERMISSION_DELIVERY_INSPECT,
    resource_type="delivery",
    organization_type="SCHOOL",
)


# =========================================================
# INSPECTION
# =========================================================

require_inspection_create = require_permission(
    PERMISSION_INSPECTION_CREATE,
    resource_type="delivery",
    organization_type="SCHOOL",
)

require_inspection_accept = require_permission(
    PERMISSION_INSPECTION_ACCEPT,
    resource_type="inspection",
    organization_type="SCHOOL",
)

require_inspection_reject = require_permission(
    PERMISSION_INSPECTION_REJECT,
    resource_type="inspection",
    organization_type="SCHOOL",
)


# =========================================================
# CORRECTIVE ACTION
# =========================================================

require_corrective_action_create = require_permission(
    PERMISSION_CORRECTIVE_ACTION_CREATE,
    resource_type="inspection",
    organization_type="SCHOOL",
)


# =========================================================
# EVIDENCE
# =========================================================

require_evidence_view = require_permission(
    PERMISSION_EVIDENCE_VIEW,
    resource_type="procurement",
)

require_evidence_upload = require_permission(
    PERMISSION_EVIDENCE_UPLOAD,
    resource_type="procurement",
)

require_evidence_delete = require_permission(
    PERMISSION_EVIDENCE_DELETE,
    resource_type="procurement",
)


# =========================================================
# SUPPLIER
# =========================================================

require_supplier_view = require_permission(
    PERMISSION_SUPPLIER_VIEW,
    resource_type="supplier",
)

require_supplier_update = require_permission(
    PERMISSION_SUPPLIER_UPDATE,
    resource_type="supplier",
)

require_supplier_performance_view = require_permission(
    PERMISSION_SUPPLIER_PERFORMANCE_VIEW,
    resource_type="supplier",
)

require_supplier_performance_refresh = require_permission(
    PERMISSION_SUPPLIER_PERFORMANCE_VIEW,
    resource_type="supplier",
    organization_type="SCHOOL",
)


# =========================================================
# DASHBOARDS / REPORTS
# =========================================================

require_dashboard_view = require_permission(
    PERMISSION_DASHBOARD_VIEW,
)

require_reality_report_view = require_permission(
    PERMISSION_REALITY_REPORT_VIEW,
)

# Browser-cookie CSRF protection for state-changing requests.
def require_csrf(request: Request):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return True
    cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME)
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed.")
    return True
