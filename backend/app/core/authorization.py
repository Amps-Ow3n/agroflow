"""
AgroFlow centralized authorization.

Feature 19:
Role-Based Authorization & Organization Isolation

Authorization model:

    authentication
        ↓
    active membership
        ↓
    permission
        ↓
    organization/resource access
        ↓
    business rules
        ↓
    state transition

Important:
- Responsibilities are assigned to memberships.
- Permissions are defined centrally in backend code.
- Permissions are NOT stored as arbitrary database configuration.
- users.role is NOT an authorization source.
- System administrators are platform-level and separate from
  organization responsibilities.
"""

from __future__ import annotations

from typing import Iterable


# ============================================================
# RESPONSIBILITIES
# ============================================================

ORGANIZATION_ADMIN = "ORGANIZATION_ADMIN"
PROCUREMENT_OFFICER = "PROCUREMENT_OFFICER"
PROCUREMENT_REVIEWER = "PROCUREMENT_REVIEWER"
RECEIVING_OFFICER = "RECEIVING_OFFICER"
SUPPLIER_USER = "SUPPLIER_USER"
SUPPLIER_ADMIN = "SUPPLIER_ADMIN"


# ============================================================
# CENTRAL PERMISSIONS
# ============================================================

PERMISSION_ORGANIZATION_VIEW = "organization:view"
PERMISSION_ORGANIZATION_UPDATE = "organization:update"
PERMISSION_ORGANIZATION_MANAGE_MEMBERS = (
    "organization:manage_members"
)

PERMISSION_PROCUREMENT_VIEW = "procurement:view"
PERMISSION_PROCUREMENT_CREATE = "procurement:create"
PERMISSION_PROCUREMENT_UPDATE = "procurement:update"
PERMISSION_PROCUREMENT_SUBMIT = "procurement:submit"
PERMISSION_PROCUREMENT_EVALUATE = "procurement:evaluate"
PERMISSION_PROCUREMENT_SELECT = "procurement:select"
PERMISSION_PROCUREMENT_CANCEL = "procurement:cancel"
PERMISSION_PROCUREMENT_TRANSITION = "procurement:transition"

PERMISSION_PURCHASE_ORDER_VIEW = "purchase_order:view"
PERMISSION_PURCHASE_ORDER_CREATE = "purchase_order:create"

PERMISSION_COMMITMENT_VIEW = "commitment:view"
PERMISSION_COMMITMENT_CREATE = "commitment:create"
PERMISSION_COMMITMENT_ACCEPT = "commitment:accept"
PERMISSION_COMMITMENT_REJECT = "commitment:reject"

PERMISSION_DELIVERY_VIEW = "delivery:view"
PERMISSION_DELIVERY_CREATE = "delivery:create"
PERMISSION_DELIVERY_INSPECT = "delivery:inspect"

PERMISSION_INSPECTION_CREATE = "inspection:create"
PERMISSION_INSPECTION_ACCEPT = "inspection:accept"
PERMISSION_INSPECTION_REJECT = "inspection:reject"

PERMISSION_CORRECTIVE_ACTION_CREATE = (
    "corrective_action:create"
)

PERMISSION_EVIDENCE_VIEW = "evidence:view"
PERMISSION_EVIDENCE_UPLOAD = "evidence:upload"
PERMISSION_EVIDENCE_DELETE = "evidence:delete"

PERMISSION_SUPPLIER_VIEW = "supplier:view"
PERMISSION_SUPPLIER_UPDATE = "supplier:update"
PERMISSION_SUPPLIER_MANAGE_CAPABILITIES = (
    "supplier:manage_capabilities"
)

PERMISSION_SUPPLIER_PERFORMANCE_VIEW = (
    "supplier_performance:view"
)

PERMISSION_DASHBOARD_VIEW = "dashboard:view"

PERMISSION_REALITY_REPORT_VIEW = (
    "reality_report:view"
)

PERMISSION_PLATFORM_MANAGE_ORGANIZATIONS = (
    "platform:manage_organizations"
)

PERMISSION_PLATFORM_MANAGE_VERIFICATION = (
    "platform:manage_verification"
)

PERMISSION_PLATFORM_MANAGE_USERS = (
    "platform:manage_users"
)


# ============================================================
# RESPONSIBILITY → PERMISSION MAP
# ============================================================

RESPONSIBILITY_PERMISSIONS: dict[str, frozenset[str]] = {

    # --------------------------------------------------------
    # ORGANIZATION ADMIN
    # --------------------------------------------------------

    ORGANIZATION_ADMIN: frozenset({
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
    }),

    # --------------------------------------------------------
    # PROCUREMENT OFFICER
    # --------------------------------------------------------

    PROCUREMENT_OFFICER: frozenset({
        PERMISSION_ORGANIZATION_VIEW,

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

        PERMISSION_EVIDENCE_VIEW,
        PERMISSION_EVIDENCE_UPLOAD,

        PERMISSION_SUPPLIER_VIEW,
        PERMISSION_SUPPLIER_PERFORMANCE_VIEW,

        PERMISSION_DASHBOARD_VIEW,
        PERMISSION_REALITY_REPORT_VIEW,
    }),

    # --------------------------------------------------------
    # PROCUREMENT REVIEWER
    # --------------------------------------------------------

    PROCUREMENT_REVIEWER: frozenset({
        PERMISSION_ORGANIZATION_VIEW,

        PERMISSION_PROCUREMENT_VIEW,
        PERMISSION_PROCUREMENT_EVALUATE,
        PERMISSION_SUPPLIER_VIEW,
        PERMISSION_SUPPLIER_PERFORMANCE_VIEW,

        PERMISSION_PURCHASE_ORDER_VIEW,
        PERMISSION_COMMITMENT_VIEW,
        PERMISSION_DELIVERY_VIEW,

        PERMISSION_EVIDENCE_VIEW,

        PERMISSION_DASHBOARD_VIEW,
        PERMISSION_REALITY_REPORT_VIEW,
    }),

    # --------------------------------------------------------
    # RECEIVING OFFICER
    # --------------------------------------------------------

    RECEIVING_OFFICER: frozenset({
        PERMISSION_ORGANIZATION_VIEW,

        PERMISSION_PROCUREMENT_VIEW,

        PERMISSION_PURCHASE_ORDER_VIEW,

        PERMISSION_COMMITMENT_VIEW,

        PERMISSION_DELIVERY_VIEW,
        PERMISSION_DELIVERY_CREATE,
        PERMISSION_DELIVERY_INSPECT,

        PERMISSION_INSPECTION_CREATE,
        PERMISSION_INSPECTION_ACCEPT,
        PERMISSION_INSPECTION_REJECT,

        PERMISSION_CORRECTIVE_ACTION_CREATE,

        PERMISSION_EVIDENCE_VIEW,
        PERMISSION_EVIDENCE_UPLOAD,

        PERMISSION_DASHBOARD_VIEW,
        PERMISSION_REALITY_REPORT_VIEW,
    }),

    # --------------------------------------------------------
    # SUPPLIER USER
    # --------------------------------------------------------

    SUPPLIER_USER: frozenset({
        PERMISSION_ORGANIZATION_VIEW,

        PERMISSION_PROCUREMENT_VIEW,

        PERMISSION_PURCHASE_ORDER_VIEW,

        PERMISSION_COMMITMENT_VIEW,
        PERMISSION_COMMITMENT_CREATE,

        PERMISSION_DELIVERY_VIEW,

        PERMISSION_EVIDENCE_VIEW,
        PERMISSION_EVIDENCE_UPLOAD,

        PERMISSION_SUPPLIER_VIEW,
        PERMISSION_SUPPLIER_UPDATE,

        PERMISSION_SUPPLIER_PERFORMANCE_VIEW,

        PERMISSION_DASHBOARD_VIEW,
    }),

    # --------------------------------------------------------
    # SUPPLIER ADMIN
    # --------------------------------------------------------

    SUPPLIER_ADMIN: frozenset({
        PERMISSION_ORGANIZATION_VIEW,
        PERMISSION_ORGANIZATION_UPDATE,
        PERMISSION_ORGANIZATION_MANAGE_MEMBERS,

        PERMISSION_PROCUREMENT_VIEW,

        PERMISSION_PURCHASE_ORDER_VIEW,

        PERMISSION_COMMITMENT_VIEW,
        PERMISSION_COMMITMENT_CREATE,

        PERMISSION_DELIVERY_VIEW,
        PERMISSION_DELIVERY_CREATE,

        PERMISSION_EVIDENCE_VIEW,
        PERMISSION_EVIDENCE_UPLOAD,

        PERMISSION_SUPPLIER_VIEW,
        PERMISSION_SUPPLIER_UPDATE,
        PERMISSION_SUPPLIER_MANAGE_CAPABILITIES,

        PERMISSION_SUPPLIER_PERFORMANCE_VIEW,

        PERMISSION_DASHBOARD_VIEW,
    }),
}


# ============================================================
# VALIDATION
# ============================================================

ALL_PERMISSIONS = frozenset(
    permission
    for permissions in RESPONSIBILITY_PERMISSIONS.values()
    for permission in permissions
)


def is_known_permission(permission: str) -> bool:
    """
    Return True when the permission exists in the central
    authorization vocabulary.
    """

    return permission in ALL_PERMISSIONS


# ============================================================
# MEMBERSHIP PERMISSION CHECK
# ============================================================

def membership_has_permission(
    membership: dict,
    permission: str,
) -> bool:
    """
    Check whether one specific organization membership has
    the requested permission.

    This function deliberately examines ONLY this membership.

    That is the key security difference from the old
    require_responsibility() implementation, which searched
    across every membership belonging to the user.
    """

    responsibilities = membership.get(
        "responsibilities",
        [],
    )

    for responsibility in responsibilities:
        responsibility_code = responsibility.get("code")

        allowed_permissions = RESPONSIBILITY_PERMISSIONS.get(
            responsibility_code,
            frozenset(),
        )

        if permission in allowed_permissions:
            return True

    return False


# ============================================================
# USER PERMISSION CHECK
# ============================================================

def user_has_permission(
    identity: dict,
    permission: str,
    organization_id: int | None = None,
) -> bool:
    """
    Check whether an authenticated identity has a permission.

    If organization_id is supplied, ONLY memberships belonging
    to that organization are considered.

    This prevents:

        User has PROCUREMENT_OFFICER in School A
        +
        User requests School B resource
        =
        DENIED

    """

    if not is_known_permission(permission):
        return False

    memberships = identity.get("memberships", [])

    for membership in memberships:

        organization = membership.get(
            "organization",
            {},
        )

        membership_organization_id = organization.get("id")

        if organization_id is not None:
            if membership_organization_id != organization_id:
                continue

        if organization.get("status") != "ACTIVE":
            continue

        # Organization-scoped authorization must not grant access to an
        # unverified organization. Route-level checks are defense in depth;
        # this central helper is also a security boundary for resource-level
        # authorization tests and direct service callers.
        if organization.get("verification_status") != "VERIFIED":
            continue

        if membership.get("status") != "ACTIVE":
            continue

        if membership_has_permission(
            membership,
            permission,
        ):
            return True

    return False


# ============================================================
# FIND AUTHORIZED MEMBERSHIP
# ============================================================

def get_authorized_membership(
    identity: dict,
    permission: str,
    organization_id: int | None = None,
) -> dict | None:
    """
    Return the specific membership that grants the permission.

    Returns None when no authorized membership exists.
    """

    if not is_known_permission(permission):
        return None

    memberships = identity.get("memberships", [])

    for membership in memberships:

        organization = membership.get(
            "organization",
            {},
        )

        membership_organization_id = organization.get("id")

        if organization_id is not None:
            if membership_organization_id != organization_id:
                continue

        if organization.get("status") != "ACTIVE":
            continue

        if membership.get("status") != "ACTIVE":
            continue

        if membership_has_permission(
            membership,
            permission,
        ):
            return membership

    return None


# ============================================================
# MULTIPLE PERMISSION CHECK
# ============================================================

def user_has_any_permission(
    identity: dict,
    permissions: Iterable[str],
    organization_id: int | None = None,
) -> bool:
    """
    Return True if the user has at least one of the supplied
    permissions within the requested organization.
    """

    return any(
        user_has_permission(
            identity,
            permission,
            organization_id=organization_id,
        )
        for permission in permissions
    )


def user_has_all_permissions(
    identity: dict,
    permissions: Iterable[str],
    organization_id: int | None = None,
) -> bool:
    """
    Return True only if the user has every supplied permission
    within the requested organization.
    """

    return all(
        user_has_permission(
            identity,
            permission,
            organization_id=organization_id,
        )
        for permission in permissions
    )

# ============================================================
# RESOURCE ORGANIZATION RESOLUTION
# ============================================================

def get_procurement_organization_id(
    cursor,
    procurement_id: int,
) -> int | None:
    """
    Return the organization owning a procurement.
    """

    cursor.execute(
        """
        SELECT organization_id
        FROM procurements
        WHERE id = %s
        """,
        (procurement_id,),
    )

    row = cursor.fetchone()

    if not row:
        return None

    return row["organization_id"]


def get_purchase_order_organization_id(
    cursor,
    purchase_order_id: int,
) -> int | None:
    """
    Resolve:

        purchase_order
            → procurement
            → organization
    """

    cursor.execute(
        """
        SELECT p.organization_id
        FROM purchase_orders po

        JOIN procurements p
            ON p.id = po.procurement_id

        WHERE po.id = %s
        """,
        (purchase_order_id,),
    )

    row = cursor.fetchone()

    if not row:
        return None

    return row["organization_id"]


def get_commitment_organization_id(
    cursor,
    commitment_id: int,
) -> int | None:
    """
    Resolve:

        commitment
            → purchase order
            → procurement
            → organization
    """

    cursor.execute(
        """
        SELECT p.organization_id
        FROM supplier_commitments sc

        JOIN purchase_orders po
            ON po.id = sc.purchase_order_id

        JOIN procurements p
            ON p.id = po.procurement_id

        WHERE sc.id = %s
        """,
        (commitment_id,),
    )

    row = cursor.fetchone()

    if not row:
        return None

    return row["organization_id"]


def get_delivery_organization_id(
    cursor,
    delivery_id: int,
) -> int | None:
    """
    Resolve:

        delivery
            → commitment
            → purchase order
            → procurement
            → organization
    """

    cursor.execute(
        """
        SELECT p.organization_id
        FROM deliveries d

        JOIN supplier_commitments sc
            ON sc.id = d.commitment_id

        JOIN purchase_orders po
            ON po.id = sc.purchase_order_id

        JOIN procurements p
            ON p.id = po.procurement_id

        WHERE d.id = %s
        """,
        (delivery_id,),
    )

    row = cursor.fetchone()

    if not row:
        return None

    return row["organization_id"]


def get_inspection_organization_id(
    cursor,
    inspection_id: int,
) -> int | None:
    """
    Resolve:

        inspection
            → delivery
            → commitment
            → purchase order
            → procurement
            → organization
    """

    cursor.execute(
        """
        SELECT p.organization_id
        FROM inspections i

        JOIN deliveries d
            ON d.id = i.delivery_id

        JOIN supplier_commitments sc
            ON sc.id = d.commitment_id

        JOIN purchase_orders po
            ON po.id = sc.purchase_order_id

        JOIN procurements p
            ON p.id = po.procurement_id

        WHERE i.id = %s
        """,
        (inspection_id,),
    )

    row = cursor.fetchone()

    if not row:
        return None

    return row["organization_id"]


# ============================================================
# RESOURCE AUTHORIZATION
# ============================================================

def authorize_procurement(
    cursor,
    identity: dict,
    procurement_id: int,
    permission: str,
) -> int:
    """
    Authorize access to a procurement.

    Returns the owning organization ID.

    Raises:
        404 when procurement does not exist.
        403 when user lacks permission in that organization.
    """

    from fastapi import HTTPException, status

    organization_id = get_procurement_organization_id(
        cursor,
        procurement_id,
    )

    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Procurement not found.",
        )

    if not user_has_permission(
        identity,
        permission,
        organization_id=organization_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this procurement.",
        )

    return organization_id


def authorize_purchase_order(
    cursor,
    identity: dict,
    purchase_order_id: int,
    permission: str,
) -> int:

    from fastapi import HTTPException, status

    organization_id = get_purchase_order_organization_id(
        cursor,
        purchase_order_id,
    )

    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found.",
        )

    if not user_has_permission(
        identity,
        permission,
        organization_id=organization_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this purchase order.",
        )

    return organization_id


def authorize_commitment(
    cursor,
    identity: dict,
    commitment_id: int,
    permission: str,
) -> int:

    from fastapi import HTTPException, status

    organization_id = get_commitment_organization_id(
        cursor,
        commitment_id,
    )

    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commitment not found.",
        )

    if not user_has_permission(
        identity,
        permission,
        organization_id=organization_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this commitment.",
        )

    return organization_id


def authorize_delivery(
    cursor,
    identity: dict,
    delivery_id: int,
    permission: str,
) -> int:

    from fastapi import HTTPException, status

    organization_id = get_delivery_organization_id(
        cursor,
        delivery_id,
    )

    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery not found.",
        )

    if not user_has_permission(
        identity,
        permission,
        organization_id=organization_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this delivery.",
        )

    return organization_id