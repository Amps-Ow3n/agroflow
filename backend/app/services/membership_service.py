from fastapi import HTTPException

from app.core.db import get_db
from app.core.transactions import write_transaction
from app.models.procurement_events import (
    record_audit_event,
)


def list_organization_members(
    organization_id: int,
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
                o.organization_type

            FROM organization_memberships om

            JOIN users u
                ON u.id = om.user_id

            JOIN organizations o
                ON o.id = om.organization_id

            WHERE om.organization_id = %s

            ORDER BY
                u.name ASC
            """,
            (
                organization_id,
            ),
        )

        members = cursor.fetchall()

        for member in members:
            cursor.execute(
                """
                SELECT
                    r.code,
                    r.name

                FROM membership_responsibilities mr

                JOIN responsibilities r
                    ON r.id = mr.responsibility_id

                WHERE mr.membership_id = %s

                ORDER BY
                    r.code
                """,
                (
                    member["membership_id"],
                ),
            )

            member["responsibilities"] = (
                cursor.fetchall()
            )

        return members

    finally:
        conn.close()


def list_assignable_responsibilities(
    organization_id: int,
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

            ORDER BY
                name ASC
            """,
            (
                organization_id,
            ),
        )

        return cursor.fetchall()

    finally:
        conn.close()

def add_organization_member(
    organization_id: int,
    email: str,
    responsibility_code: str,
    actor_user_id: int,
):
    email = email.strip().lower()

    responsibility_code = (
        responsibility_code.strip().upper()
    )

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Email is required.",
        )

    if not responsibility_code:
        raise HTTPException(
            status_code=400,
            detail="Responsibility code is required.",
        )

    conn, cursor = get_db()

    try:
        with write_transaction(conn):

            # --------------------------------------------------
            # 1. Verify organization
            # --------------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    organization_type,
                    status,
                    verification_status

                FROM organizations

                WHERE id = %s

                FOR UPDATE
                """,
                (
                    organization_id,
                ),
            )

            organization = cursor.fetchone()

            if not organization:
                raise HTTPException(
                    status_code=404,
                    detail="Organization not found.",
                )

            if organization["status"] != "ACTIVE":
                raise HTTPException(
                    status_code=403,
                    detail="This organization is not active.",
                )

            if (
                organization["verification_status"]
                != "VERIFIED"
            ):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "This organization has not "
                        "been verified."
                    ),
                )

            # --------------------------------------------------
            # 2. Find existing user
            # --------------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    email,
                    status

                FROM users

                WHERE LOWER(email) = LOWER(%s)
                """,
                (
                    email,
                ),
            )

            target_user = cursor.fetchone()

            if not target_user:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "No AgroFlow user exists "
                        "with that email address."
                    ),
                )

            if target_user["status"] != "ACTIVE":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The user's account is not active."
                    ),
                )

            target_user_id = target_user["id"]

            # --------------------------------------------------
            # 3. Check whether membership already exists
            # --------------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    status

                FROM organization_memberships

                WHERE
                    organization_id = %s
                    AND user_id = %s

                FOR UPDATE
                """,
                (
                    organization_id,
                    target_user_id,
                ),
            )

            existing_membership = cursor.fetchone()

            if existing_membership:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This user is already a member "
                        "of this organization."
                    ),
                )

            # --------------------------------------------------
            # 4. Find requested responsibility
            # --------------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    code,
                    name,
                    description,
                    organization_type

                FROM responsibilities

                WHERE code = %s
                """,
                (
                    responsibility_code,
                ),
            )

            responsibility = cursor.fetchone()

            if not responsibility:
                raise HTTPException(
                    status_code=404,
                    detail="Responsibility not found.",
                )

            # --------------------------------------------------
            # 5. Verify responsibility fits organization
            # --------------------------------------------------

            allowed_type = (
                responsibility["organization_type"]
            )

            if (
                allowed_type is not None
                and allowed_type != "ANY"
                and allowed_type
                != organization["organization_type"]
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "This responsibility is not valid "
                        "for this organization type."
                    ),
                )

            # --------------------------------------------------
            # 6. Create active membership
            # --------------------------------------------------

            cursor.execute(
                """
                INSERT INTO organization_memberships (
                    organization_id,
                    user_id,
                    status
                )

                VALUES (
                    %s,
                    %s,
                    'ACTIVE'
                )

                RETURNING id
                """,
                (
                    organization_id,
                    target_user_id,
                ),
            )

            membership = cursor.fetchone()

            # --------------------------------------------------
            # 7. Assign initial responsibility
            # --------------------------------------------------

            cursor.execute(
                """
                INSERT INTO membership_responsibilities (
                    membership_id,
                    responsibility_id
                )

                VALUES (
                    %s,
                    %s
                )
                """,
                (
                    membership["id"],
                    responsibility["id"],
                ),
            )

            # --------------------------------------------------
            # 8. Audit
            # --------------------------------------------------

            record_audit_event(
                cursor,
                None,
                actor_user_id,
                "ADD_ORGANIZATION_MEMBER",
                "organization_membership",
                membership["id"],
                None,
                {
                    "user_id":
                        target_user_id,

                    "organization_id":
                        organization_id,

                    "email":
                        target_user["email"],

                    "responsibility":
                        responsibility["code"],
                },
            )

            return {
                "status": "ADDED",
                "membership_id":
                    membership["id"],
                "user_id":
                    target_user_id,
                "organization_id":
                    organization_id,
                "email":
                    target_user["email"],
                "full_name":
                    target_user["name"],
                "responsibility":
                    responsibility["code"],
            }

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

    if not responsibility_code:
        raise HTTPException(
            status_code=400,
            detail="Responsibility code is required.",
        )

    conn, cursor = get_db()

    try:
        with write_transaction(conn):

            # --------------------------------------------------
            # 1. Verify target organization membership
            # --------------------------------------------------

            cursor.execute(
                """
                SELECT
                    om.id,
                    om.user_id,
                    om.organization_id,
                    om.status,

                    o.organization_type,
                    o.status AS organization_status,
                    o.verification_status

                FROM organization_memberships om

                JOIN organizations o
                    ON o.id = om.organization_id

                WHERE
                    om.organization_id = %s
                    AND om.user_id = %s

                FOR UPDATE
                """,
                (
                    organization_id,
                    target_user_id,
                ),
            )

            membership = cursor.fetchone()

            if not membership:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "The target user does not have "
                        "a membership in this organization."
                    ),
                )

            if membership["status"] != "ACTIVE":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The target user's organization "
                        "membership is not active."
                    ),
                )

            if (
                membership["organization_status"]
                != "ACTIVE"
            ):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "This organization is not active."
                    ),
                )

            if (
                membership["verification_status"]
                != "VERIFIED"
            ):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "This organization has not "
                        "been verified."
                    ),
                )

            # --------------------------------------------------
            # 2. Find requested responsibility
            # --------------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    code,
                    name,
                    description,
                    organization_type

                FROM responsibilities

                WHERE code = %s
                """,
                (
                    responsibility_code,
                ),
            )

            responsibility = cursor.fetchone()

            if not responsibility:
                raise HTTPException(
                    status_code=404,
                    detail="Responsibility not found.",
                )

            # --------------------------------------------------
            # 3. Verify responsibility fits organization
            # --------------------------------------------------

            allowed_type = (
                responsibility["organization_type"]
            )

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
                    ),
                )

            # --------------------------------------------------
            # 4. Prevent duplicate responsibility
            # --------------------------------------------------

            cursor.execute(
                """
                SELECT
                    1

                FROM membership_responsibilities

                WHERE
                    membership_id = %s
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
                    "membership_id":
                        membership["id"],
                    "user_id":
                        target_user_id,
                    "organization_id":
                        organization_id,
                    "responsibility_code":
                        responsibility["code"],
                    "status":
                        "ALREADY_ASSIGNED",
                }

            # --------------------------------------------------
            # 5. Add responsibility to EXISTING membership
            # --------------------------------------------------

            cursor.execute(
                """
                INSERT INTO membership_responsibilities (
                    membership_id,
                    responsibility_id
                )

                VALUES (
                    %s,
                    %s
                )
                """,
                (
                    membership["id"],
                    responsibility["id"],
                ),
            )

            # --------------------------------------------------
            # 6. Audit
            # --------------------------------------------------

            record_audit_event(
                cursor,
                None,
                actor_user_id,
                "ASSIGN_MEMBERSHIP_RESPONSIBILITY",
                "organization_membership",
                membership["id"],
                None,
                {
                    "user_id":
                        target_user_id,

                    "organization_id":
                        organization_id,

                    "responsibility":
                        responsibility["code"],
                },
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