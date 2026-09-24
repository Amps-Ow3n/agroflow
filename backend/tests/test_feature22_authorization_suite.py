"""Feature 22 - Layer 4: authorization and organization isolation.

The contract is derived from Feature 21's centralized authorization map and
resource-organization resolution code. The tests deliberately distinguish:

1. permission possession (role/responsibility -> permission), and
2. resource ownership/isolation (permission in the resource's organization).
"""

from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.authorization import (  # noqa: E402
    ORGANIZATION_ADMIN,
    PROCUREMENT_OFFICER,
    PROCUREMENT_REVIEWER,
    RECEIVING_OFFICER,
    SUPPLIER_ADMIN,
    SUPPLIER_USER,
    PERMISSION_COMMITMENT_ACCEPT,
    PERMISSION_COMMITMENT_CREATE,
    PERMISSION_DELIVERY_CREATE,
    PERMISSION_DELIVERY_INSPECT,
    PERMISSION_INSPECTION_ACCEPT,
    PERMISSION_INSPECTION_REJECT,
    PERMISSION_PROCUREMENT_CREATE,
    PERMISSION_PROCUREMENT_EVALUATE,
    PERMISSION_PROCUREMENT_VIEW,
    PERMISSION_SUPPLIER_PERFORMANCE_VIEW,
    PERMISSION_SUPPLIER_UPDATE,
    membership_has_permission,
    user_has_permission,
)
from app.core.resource_authorization import (  # noqa: E402
    get_resource_organization_ids,
    require_resource_access,
    user_can_access_resource,
)


def organization(org_id, org_type="SCHOOL", *, status="ACTIVE", verification="VERIFIED"):
    return {
        "id": org_id,
        "organization_type": org_type,
        "status": status,
        "verification_status": verification,
    }


def membership(
    org_id,
    responsibility,
    *,
    org_type=None,
    status="ACTIVE",
    org_status="ACTIVE",
    verification="VERIFIED",
):
    if org_type is None:
        org_type = "SUPPLIER" if responsibility in {SUPPLIER_USER, SUPPLIER_ADMIN} else "SCHOOL"
    return {
        "status": status,
        "responsibilities": [{"code": responsibility}],
        "organization": organization(
            org_id,
            org_type,
            status=org_status,
            verification=verification,
        ),
    }


def identity(*memberships):
    return {
        "user": {"id": 10, "status": "ACTIVE"},
        "memberships": list(memberships),
    }


class ResourceCursor:
    """Cursor stub keyed by resource type SQL emitted by Feature 21."""

    def __init__(self, resource_rows):
        self.resource_rows = resource_rows
        self.row = None

    def execute(self, query, params):
        rid = int(params[0])
        self.row = self.resource_rows.get(rid)

    def fetchone(self):
        if self.row is None:
            return None
        return self.row


# ---------------------------------------------------------------------------
# 1. Role authorization matrix -- derived from actual Feature 21 policy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "responsibility,permission,expected",
    [
        (SUPPLIER_USER, PERMISSION_COMMITMENT_CREATE, True),
        (SUPPLIER_USER, PERMISSION_DELIVERY_INSPECT, False),
        (SUPPLIER_USER, PERMISSION_PROCUREMENT_CREATE, False),
        (SUPPLIER_ADMIN, PERMISSION_SUPPLIER_UPDATE, True),
        (SUPPLIER_ADMIN, PERMISSION_DELIVERY_CREATE, True),
        (SUPPLIER_ADMIN, PERMISSION_DELIVERY_INSPECT, False),
        (PROCUREMENT_OFFICER, PERMISSION_PROCUREMENT_CREATE, True),
        (PROCUREMENT_OFFICER, PERMISSION_COMMITMENT_ACCEPT, True),
        (PROCUREMENT_OFFICER, PERMISSION_DELIVERY_INSPECT, False),
        (PROCUREMENT_REVIEWER, PERMISSION_PROCUREMENT_EVALUATE, True),
        (PROCUREMENT_REVIEWER, PERMISSION_PROCUREMENT_CREATE, False),
        (RECEIVING_OFFICER, PERMISSION_DELIVERY_INSPECT, True),
        (RECEIVING_OFFICER, PERMISSION_INSPECTION_ACCEPT, True),
        (RECEIVING_OFFICER, PERMISSION_INSPECTION_REJECT, True),
        (RECEIVING_OFFICER, PERMISSION_COMMITMENT_CREATE, False),
        (ORGANIZATION_ADMIN, PERMISSION_PROCUREMENT_CREATE, True),
        (ORGANIZATION_ADMIN, PERMISSION_DELIVERY_INSPECT, True),
    ],
)
def test_role_permission_matrix(responsibility, permission, expected):
    assert membership_has_permission(membership(1, responsibility), permission) is expected


# ---------------------------------------------------------------------------
# 2. Active membership / organization conditions
# ---------------------------------------------------------------------------

def test_inactive_membership_cannot_authorize():
    user = identity(membership(1, PROCUREMENT_OFFICER, status="INACTIVE"))
    assert not user_has_permission(user, PERMISSION_PROCUREMENT_CREATE, organization_id=1)


def test_inactive_organization_cannot_authorize():
    user = identity(membership(1, PROCUREMENT_OFFICER, org_status="INACTIVE"))
    assert not user_has_permission(user, PERMISSION_PROCUREMENT_CREATE, organization_id=1)


def test_unverified_membership_still_has_role_permission_but_resource_dependency_must_apply_verification_policy():
    # membership_has_permission is intentionally a pure role -> permission
    # lookup. This keeps policy evaluation separate from membership state.
    user = identity(membership(1, PROCUREMENT_OFFICER, verification="PENDING"))
    assert membership_has_permission(user["memberships"][0], PERMISSION_PROCUREMENT_CREATE)


# ---------------------------------------------------------------------------
# 3. Organization isolation
# ---------------------------------------------------------------------------

def test_permission_is_scoped_to_organization():
    user = identity(membership(1, PROCUREMENT_OFFICER))
    assert user_has_permission(user, PERMISSION_PROCUREMENT_CREATE, organization_id=1)
    assert not user_has_permission(user, PERMISSION_PROCUREMENT_CREATE, organization_id=2)


def test_same_user_can_have_different_responsibilities_in_different_orgs():
    user = identity(
        membership(1, PROCUREMENT_OFFICER),
        membership(2, PROCUREMENT_REVIEWER),
    )
    assert user_has_permission(user, PERMISSION_PROCUREMENT_CREATE, organization_id=1)
    assert not user_has_permission(user, PERMISSION_PROCUREMENT_CREATE, organization_id=2)
    assert user_has_permission(user, PERMISSION_PROCUREMENT_EVALUATE, organization_id=2)


def test_user_cannot_cross_access_another_supplier_resource():
    supplier_a = identity(membership(9, SUPPLIER_USER))
    assert not user_can_access_resource(
        supplier_a,
        PERMISSION_SUPPLIER_UPDATE,
        [10],
    )


def test_resource_access_is_allowed_when_user_has_permission_in_any_legitimate_resource_org():
    school_reviewer = identity(membership(1, PROCUREMENT_REVIEWER))
    assert user_can_access_resource(
        school_reviewer,
        PERMISSION_PROCUREMENT_VIEW,
        [1, 9],
    )
    assert not user_can_access_resource(
        school_reviewer,
        PERMISSION_PROCUREMENT_VIEW,
        [2, 9],
    )


# ---------------------------------------------------------------------------
# 4. Resource -> organization resolution
# ---------------------------------------------------------------------------

def test_procurement_resolves_to_owning_school():
    cursor = ResourceCursor({101: {"organization_id": 1}})
    assert get_resource_organization_ids(cursor, "procurement", 101) == [1]


def test_purchase_order_resolves_to_school_and_supplier():
    cursor = ResourceCursor({102: {"organization_id": 1, "supplier_organization_id": 9}})
    assert get_resource_organization_ids(cursor, "purchase_order", 102) == [1, 9]


def test_commitment_resolves_to_school_and_supplier():
    cursor = ResourceCursor({103: {"organization_id": 1, "supplier_organization_id": 9}})
    assert get_resource_organization_ids(cursor, "commitment", 103) == [1, 9]


def test_delivery_resolves_to_school_and_supplier():
    cursor = ResourceCursor({104: {"organization_id": 1, "supplier_organization_id": 9}})
    assert get_resource_organization_ids(cursor, "delivery", 104) == [1, 9]


def test_inspection_resolves_to_school_and_supplier():
    cursor = ResourceCursor({105: {"organization_id": 1, "supplier_organization_id": 9}})
    assert get_resource_organization_ids(cursor, "inspection", 105) == [1, 9]


def test_supplier_resolves_to_supplier_organization():
    cursor = ResourceCursor({106: {"organization_id": 9}})
    assert get_resource_organization_ids(cursor, "supplier", 106) == [9]


def test_missing_resource_is_not_authorized():
    cursor = ResourceCursor({})
    user = identity(membership(1, PROCUREMENT_REVIEWER))

    with pytest.raises(HTTPException) as exc:
        require_resource_access(
            cursor,
            user,
            PERMISSION_PROCUREMENT_VIEW,
            "procurement",
            999,
        )

    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# 5. End-to-end resource authorization helper
# ---------------------------------------------------------------------------

def test_resource_access_helper_allows_authorized_school_user():
    cursor = ResourceCursor({201: {"organization_id": 1}})
    user = identity(membership(1, PROCUREMENT_REVIEWER))

    assert require_resource_access(
        cursor,
        user,
        PERMISSION_PROCUREMENT_VIEW,
        "procurement",
        201,
    ) is True


def test_resource_access_helper_denies_wrong_organization():
    cursor = ResourceCursor({202: {"organization_id": 1}})
    user = identity(membership(2, PROCUREMENT_REVIEWER))

    with pytest.raises(HTTPException) as exc:
        require_resource_access(
            cursor,
            user,
            PERMISSION_PROCUREMENT_VIEW,
            "procurement",
            202,
        )

    assert exc.value.status_code == 403


def test_supplier_side_commitment_access_requires_supplier_permission_in_that_supplier_org():
    cursor = ResourceCursor({203: {"organization_id": 1, "supplier_organization_id": 9}})
    supplier = identity(membership(9, SUPPLIER_USER))
    unrelated_supplier = identity(membership(10, SUPPLIER_USER))

    assert require_resource_access(
        cursor,
        supplier,
        PERMISSION_COMMITMENT_CREATE,
        "commitment",
        203,
    ) is True

    with pytest.raises(HTTPException) as exc:
        require_resource_access(
            cursor,
            unrelated_supplier,
            PERMISSION_COMMITMENT_CREATE,
            "commitment",
            203,
        )
    assert exc.value.status_code == 403


def test_school_receiving_officer_can_inspect_delivery_but_supplier_cannot():
    cursor = ResourceCursor({204: {"organization_id": 1, "supplier_organization_id": 9}})
    receiver = identity(membership(1, RECEIVING_OFFICER))
    supplier = identity(membership(9, SUPPLIER_USER))

    assert require_resource_access(
        cursor,
        receiver,
        PERMISSION_DELIVERY_INSPECT,
        "delivery",
        204,
    ) is True

    with pytest.raises(HTTPException) as exc:
        require_resource_access(
            cursor,
            supplier,
            PERMISSION_DELIVERY_INSPECT,
            "delivery",
            204,
        )
    assert exc.value.status_code == 403


def test_unknown_permission_is_never_authorized():
    user = identity(membership(1, ORGANIZATION_ADMIN))
    assert not user_has_permission(user, "not:a:real:permission", organization_id=1)
