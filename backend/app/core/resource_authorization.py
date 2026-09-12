from fastapi import HTTPException, status


RESOURCE_ID_PARAMETER = {
    "procurement": "procurement_id",
    "purchase_order": "order_id",
    "commitment": "commitment_id",
    "delivery": "delivery_id",
    "inspection": "inspection_id",
    "supplier": "supplier_id",
}


def _get_required_resource_id(
    path_params: dict,
    parameter_name: str,
):
    resource_id = path_params.get(parameter_name)

    if resource_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Authorization configuration error: "
                f"missing resource parameter '{parameter_name}'."
            ),
        )

    try:
        return int(resource_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resource identifier.",
        )


def get_resource_organization_ids(
    cursor,
    resource_type: str,
    resource_id: int,
) -> list[int]:
    """
    Resolve the organizations that legitimately own or participate
    in a resource.

    This function performs NO permission check.

    It only answers:

        Which organization(s) are associated with this resource?

    Authorization is performed separately by require_permission().
    """

    if resource_type == "procurement":

        cursor.execute(
            """
            SELECT
                p.organization_id
            FROM procurements p
            WHERE p.id = %s
            """,
            (resource_id,),
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Procurement not found.",
            )

        return [
            row["organization_id"]
        ]


    if resource_type == "purchase_order":

        cursor.execute(
            """
            SELECT
                p.organization_id,
                s.organization_id AS supplier_organization_id

            FROM purchase_orders po

            JOIN procurements p
                ON p.id = po.procurement_id

            JOIN suppliers s
                ON s.id = po.supplier_id

            WHERE po.id = %s
            """,
            (resource_id,),
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found.",
            )

        return list(
            dict.fromkeys(
                [
                    row["organization_id"],
                    row["supplier_organization_id"],
                ]
            )
        )


    if resource_type == "commitment":

        cursor.execute(
            """
            SELECT
                p.organization_id,
                s.organization_id AS supplier_organization_id

            FROM supplier_commitments sc

            JOIN purchase_orders po
                ON po.id = sc.purchase_order_id

            JOIN procurements p
                ON p.id = po.procurement_id

            JOIN suppliers s
                ON s.id = sc.supplier_id

            WHERE sc.id = %s
            """,
            (resource_id,),
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Commitment not found.",
            )

        return list(
            dict.fromkeys(
                [
                    row["organization_id"],
                    row["supplier_organization_id"],
                ]
            )
        )


    if resource_type == "delivery":

        cursor.execute(
            """
            SELECT
                p.organization_id,
                s.organization_id AS supplier_organization_id

            FROM deliveries d

            JOIN supplier_commitments sc
                ON sc.id = d.commitment_id

            JOIN purchase_orders po
                ON po.id = sc.purchase_order_id

            JOIN procurements p
                ON p.id = po.procurement_id

            JOIN suppliers s
                ON s.id = sc.supplier_id

            WHERE d.id = %s
            """,
            (resource_id,),
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery not found.",
            )

        return list(
            dict.fromkeys(
                [
                    row["organization_id"],
                    row["supplier_organization_id"],
                ]
            )
        )


    if resource_type == "inspection":

        cursor.execute(
            """
            SELECT
                p.organization_id,
                s.organization_id AS supplier_organization_id

            FROM inspections i

            JOIN deliveries d
                ON d.id = i.delivery_id

            JOIN supplier_commitments sc
                ON sc.id = d.commitment_id

            JOIN purchase_orders po
                ON po.id = sc.purchase_order_id

            JOIN procurements p
                ON p.id = po.procurement_id

            JOIN suppliers s
                ON s.id = sc.supplier_id

            WHERE i.id = %s
            """,
            (resource_id,),
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inspection not found.",
            )

        return list(
            dict.fromkeys(
                [
                    row["organization_id"],
                    row["supplier_organization_id"],
                ]
            )
        )


    if resource_type == "supplier":

        cursor.execute(
            """
            SELECT
                s.organization_id

            FROM suppliers s

            WHERE s.id = %s
            """,
            (resource_id,),
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found.",
            )

        return [
            row["organization_id"]
        ]


    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=(
            "Authorization configuration error: "
            f"unsupported resource type '{resource_type}'."
        ),
    )


def organization_type_for_resource(
    cursor,
    organization_id: int,
) -> str | None:

    cursor.execute(
        """
        SELECT
            organization_type,
            status,
            verification_status

        FROM organizations

        WHERE id = %s
        """,
        (organization_id,),
    )

    row = cursor.fetchone()

    if not row:
        return None

    if row["status"] != "ACTIVE":
        return None

    if row["verification_status"] != "VERIFIED":
        return None

    return row["organization_type"]


def user_can_access_resource(
    identity: dict,
    permission: str,
    resource_organization_ids: list[int],
) -> bool:
    """
    Determine whether the authenticated user possesses the required
    permission in an organization legitimately associated with the
    resource.

    IMPORTANT:

    A responsibility held in Organization A cannot authorize access
    to a resource belonging only to Organization B.
    """

    from app.core.authorization import (
        get_authorized_membership,
    )

    for organization_id in resource_organization_ids:

        membership = get_authorized_membership(
            identity,
            permission,
            organization_id=organization_id,
        )

        if membership:
            return True

    return False


def require_resource_access(
    cursor,
    identity: dict,
    permission: str,
    resource_type: str,
    resource_id: int,
):
    """
    Authorize access to a resource.

    Security sequence:

        resource exists
            ↓
        resolve resource organization(s)
            ↓
        organization is active + verified
            ↓
        user has active membership there
            ↓
        user's responsibility in THAT membership
            ↓
        responsibility grants required permission
    """

    organization_ids = get_resource_organization_ids(
        cursor,
        resource_type,
        resource_id,
    )

    if not organization_ids:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found.",
        )

    if not user_can_access_resource(
        identity,
        permission,
        organization_ids,
    ):

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have permission to access "
                "this resource."
            ),
        )

    return True