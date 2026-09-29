from fastapi import HTTPException

from app.core.db import get_db
from app.core.transactions import write_transaction
from app.utils.audit import create_audit_log


def list_organization_members(
    organization_id: int
):
    conn, cursor = get_db()

    try:
        cursor.execute(
            """
            SELECT
                om.id AS membership_id,
                om.user_id,
                u.name AS full_name,
                u.email,
                om.status AS membership_status,
                o.organization_type,

                COALESCE(
                    json_agg(
                        json_build_object(
                            'code', r.code,
                            'name', r.name
                        )
                        ORDER BY r.code
                    )
                    FILTER (
                        WHERE r.id IS NOT NULL
                    ),
                    '[]'
                ) AS responsibilities

            FROM organization_memberships om

            JOIN users u
                ON u.id = om.user_id

            JOIN organizations o
                ON o.id = om.organization_id

            LEFT JOIN membership_responsibilities mr
                ON mr.membership_id = om.id

            LEFT JOIN responsibilities r
                ON r.id = mr.responsibility_id

            WHERE om.organization_id = %s

            GROUP BY
                om.id,
                om.user_id,
                u.name,
                u.email,
                om.status,
                o.organization_type

            ORDER BY
                u.name ASC
            """,
            (organization_id,)
        )

        return cursor.fetchall()

    finally:
        conn.close()


def list_assignable_responsibilities(
    organization_id: int
):
    conn, cursor = get_db()

    try:
        cursor.execute(
            """
            SELECT
                code,
                name,
                description,
                organization_type

            FROM responsibilities

            WHERE
                organization_type IS NULL
                OR organization_type = 'ANY'
                OR organization_type = (
                    SELECT organization_type
                    FROM organizations
                    WHERE id = %s
                )

            ORDER BY name ASC
            """,
            (organization_id,)
        )

        return cursor.fetchall()

    finally:
        conn.close()


def add_membership_responsibility(
    organization_id: int,
    target_user_id: int,
    responsibility_code: str,
    actor_user_id: int,
):
    responsibility_code = (
        responsibility_code.strip().upper()
    )

    conn, cursor = get_db()

    try:
        with write_transaction(conn):

            # --------------------------------------------------
            # Target membership
            # --------------------------------------------------

            cursor.execute(
                """
                SELECT
                    om.id,
                    om.user_id,
                    om.status,
                    o.organization_type,
                    o.status AS organization_status,
                    o.verification_status

                FROM organization_memberships om

                JOIN organizations o
                    ON o.id = om.organization_id

                WHERE om.organization_id = %s
                  AND om.user_id = %s

                FOR UPDATE
                """,
                (
                    organization_id,
                    target_user_id,
                )
            )

            membership = cursor.fetchone()

            if not membership:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "User is not a member of this organization."
                    )
                )

            if membership["status"] != "ACTIVE":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The target membership is not active."
                    )
                )

            if (
                membership["organization_status"]
                != "ACTIVE"
                or
                membership["verification_status"]
                != "VERIFIED"
            ):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Organization is not active and verified."
                    )
                )

            # --------------------------------------------------
            # Responsibility
            # --------------------------------------------------

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
                (responsibility_code,)
            )

            responsibility = cursor.fetchone()

            if not responsibility:
                raise HTTPException(
                    status_code=404,
                    detail="Responsibility not found."
                )

            allowed_type = responsibility[
                "organization_type"
            ]

            if (
                allowed_type is not None
                and allowed_type != "ANY"
                and allowed_type
                != membership["organization_type"]
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "This responsibility is not valid "
                        "for this organization type."
                    )
                )

            # --------------------------------------------------
            # Prevent duplicate assignment
            # --------------------------------------------------

            cursor.execute(
                """
                SELECT 1

                FROM membership_responsibilities

                WHERE membership_id = %s
                  AND responsibility_id = %s
                """,
                (
                    membership["id"],
                    responsibility["id"],
                )
            )

            if cursor.fetchone():
                return {
                    "status": "ALREADY_ASSIGNED",
                    "membership_id":
                        membership["id"],
                    "user_id":
                        target_user_id,
                    "responsibility":
                        responsibility["code"],
                }

            # --------------------------------------------------
            # Assign
            # --------------------------------------------------

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
                )
            )

            create_audit_log(
                cursor=cursor,
                user_id=actor_user_id,
                action="ASSIGN_MEMBERSHIP_RESPONSIBILITY",
                entity_type="organization_membership",
                entity_id=membership["id"],
                old_data=None,
                new_data={
                    "user_id": target_user_id,
                    "responsibility":
                        responsibility["code"],
                }
            )

            return {
                "status": "ASSIGNED",
                "membership_id":
                    membership["id"],
                "user_id":
                    target_user_id,
                "responsibility":
                    responsibility["code"],
            }
    finally:
        conn.close()