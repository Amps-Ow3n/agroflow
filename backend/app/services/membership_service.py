from fastapi import HTTPException

from app.core.db import get_db
from app.core.transactions import write_transaction


def add_membership_responsibility(
    organization_id: int,
    target_user_id: int,
    responsibility_code: str,
    actor_user_id: int,
):
    responsibility_code = responsibility_code.strip().upper()

    if not responsibility_code:
        raise HTTPException(
            status_code=400,
            detail="Responsibility code is required.",
        )

    conn, cursor = get_db()

    try:
        with write_transaction(conn):

            # ---------------------------------------------------------
            # 1. Verify the actor has an active membership in this
            #    organization and is an ORGANIZATION_ADMIN.
            # ---------------------------------------------------------

            cursor.execute(
                """
                SELECT
                    om.id,
                    om.user_id,
                    om.organization_id,
                    om.status
                FROM organization_memberships om

                JOIN membership_responsibilities mr
                    ON mr.membership_id = om.id

                JOIN responsibilities r
                    ON r.id = mr.responsibility_id

                JOIN organizations o
                    ON o.id = om.organization_id

                WHERE om.user_id = %s
                  AND om.organization_id = %s
                  AND om.status = 'ACTIVE'
                  AND o.status = 'ACTIVE'
                  AND o.verification_status = 'VERIFIED'
                  AND r.code = 'ORGANIZATION_ADMIN'

                FOR UPDATE
                """,
                (
                    actor_user_id,
                    organization_id,
                ),
            )

            actor_membership = cursor.fetchone()

            if not actor_membership:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "You must be an active organization administrator "
                        "of this organization."
                    ),
                )

            # ---------------------------------------------------------
            # 2. Find the target user's existing membership.
            # ---------------------------------------------------------

            cursor.execute(
                """
                SELECT
                    om.id,
                    om.user_id,
                    om.organization_id,
                    om.status
                FROM organization_memberships om

                WHERE om.user_id = %s
                  AND om.organization_id = %s

                FOR UPDATE
                """,
                (
                    target_user_id,
                    organization_id,
                ),
            )

            membership = cursor.fetchone()

            if not membership:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "The target user does not have a membership "
                        "in this organization."
                    ),
                )

            if membership["status"] != "ACTIVE":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The target user's organization membership "
                        "is not active."
                    ),
                )

            # ---------------------------------------------------------
            # 3. Find the requested responsibility.
            # ---------------------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    code,
                    name,
                    organization_type
                FROM responsibilities
                WHERE code = %s
                """,
                (responsibility_code,),
            )

            responsibility = cursor.fetchone()

            if not responsibility:
                raise HTTPException(
                    status_code=404,
                    detail="Responsibility not found.",
                )

            # ---------------------------------------------------------
            # 4. Verify responsibility is compatible with the
            #    organization's type.
            # ---------------------------------------------------------

            cursor.execute(
                """
                SELECT
                    organization_type
                FROM organizations
                WHERE id = %s
                """,
                (organization_id,),
            )

            organization = cursor.fetchone()

            if not organization:
                raise HTTPException(
                    status_code=404,
                    detail="Organization not found.",
                )

            responsibility_org_type = responsibility[
                "organization_type"
            ]

            if (
                responsibility_org_type is not None
                and responsibility_org_type != "ANY"
                and responsibility_org_type
                != organization["organization_type"]
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "This responsibility is not valid for "
                        "this organization type."
                    ),
                )

            # ---------------------------------------------------------
            # 5. Check whether the membership already has the role.
            # ---------------------------------------------------------

            cursor.execute(
                """
                SELECT
                    1
                FROM membership_responsibilities
                WHERE membership_id = %s
                  AND responsibility_id = %s
                """,
                (
                    membership["id"],
                    responsibility["id"],
                ),
            )

            existing = cursor.fetchone()

            if existing:
                return {
                    "membership_id": membership["id"],
                    "user_id": target_user_id,
                    "organization_id": organization_id,
                    "responsibility_code": responsibility["code"],
                    "status": "ALREADY_ASSIGNED",
                }

            # ---------------------------------------------------------
            # 6. Add the responsibility to the EXISTING membership.
            # ---------------------------------------------------------

            cursor.execute(
                """
                INSERT INTO membership_responsibilities (
                    membership_id,
                    responsibility_id
                )
                VALUES (%s, %s)
                """,
                (
                    membership["id"],
                    responsibility["id"],
                ),
            )

            return {
                "membership_id": membership["id"],
                "user_id": target_user_id,
                "organization_id": organization_id,
                "responsibility_code": responsibility["code"],
                "status": "ASSIGNED",
            }

    finally:
        conn.close()