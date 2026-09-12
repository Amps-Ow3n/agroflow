from fastapi import HTTPException

from app.core.db import get_db
from app.core.transactions import write_transaction


def list_pending_verifications():

    conn, cursor = get_db()

    try:

        cursor.execute(
            """
            SELECT
                v.id,
                v.organization_id,
                v.status,
                v.verification_type,
                v.submitted_by,
                v.submitted_at,

                o.name AS organization_name,
                o.organization_type,
                o.status AS organization_status,
                o.verification_status,

                u.name AS submitted_by_name,
                u.email AS submitted_by_email

            FROM organization_verification_records v

            JOIN organizations o
                ON o.id = v.organization_id

            LEFT JOIN users u
                ON u.id = v.submitted_by

            WHERE v.status = 'PENDING'

            ORDER BY v.submitted_at ASC
            """
        )

        return cursor.fetchall()

    finally:

        conn.close()


def get_verification(
    organization_id: int,
):

    conn, cursor = get_db()

    try:

        cursor.execute(
            """
            SELECT
                v.id,
                v.organization_id,
                v.status,
                v.verification_type,
                v.submitted_by,
                v.submitted_at,
                v.reviewed_by,
                v.reviewed_at,
                v.reason,
                v.evidence_reference,

                o.name AS organization_name,
                o.organization_type,
                o.status AS organization_status,
                o.verification_status

            FROM organization_verification_records v

            JOIN organizations o
                ON o.id = v.organization_id

            WHERE v.organization_id = %s

            ORDER BY v.id DESC

            LIMIT 1
            """,
            (organization_id,),
        )

        record = cursor.fetchone()

        if not record:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Verification record not found."
                ),
            )

        return record

    finally:

        conn.close()


def decide_verification(
    organization_id: int,
    decision: str,
    reason: str | None,
    reviewer_id: int,
):

    decision = decision.strip().upper()

    if decision not in {
        "VERIFIED",
        "REJECTED",
    }:

        raise HTTPException(
            status_code=400,
            detail=(
                "Verification decision must be "
                "VERIFIED or REJECTED."
            ),
        )

    if decision == "REJECTED":

        if reason is None or not reason.strip():

            raise HTTPException(
                status_code=400,
                detail=(
                    "A rejection reason is required."
                ),
            )

    conn, cursor = get_db()

    try:

        with write_transaction(conn):

            cursor.execute(
                """
                SELECT
                    id,
                    status,
                    verification_status

                FROM organizations

                WHERE id = %s

                FOR UPDATE
                """,
                (organization_id,),
            )

            organization = cursor.fetchone()

            if not organization:

                raise HTTPException(
                    status_code=404,
                    detail="Organization not found.",
                )

            cursor.execute(
                """
                SELECT
                    id,
                    status,
                    verification_type,
                    submitted_by

                FROM organization_verification_records

                WHERE organization_id = %s
                  AND status = 'PENDING'

                ORDER BY id DESC

                LIMIT 1

                FOR UPDATE
                """,
                (organization_id,),
            )

            verification = cursor.fetchone()

            if not verification:

                raise HTTPException(
                    status_code=409,
                    detail=(
                        "There is no pending verification "
                        "for this organization."
                    ),
                )

            if decision == "VERIFIED":

                cursor.execute(
                    """
                    UPDATE organizations

                    SET
                        status = 'ACTIVE',
                        verification_status = 'VERIFIED',
                        updated_at = CURRENT_TIMESTAMP

                    WHERE id = %s
                    """,
                    (organization_id,),
                )

                cursor.execute(
                    """
                    UPDATE organization_memberships

                    SET
                        status = 'ACTIVE',
                        updated_at = CURRENT_TIMESTAMP

                    WHERE organization_id = %s
                      AND status = 'PENDING'
                    """,
                    (organization_id,),
                )

            else:

                cursor.execute(
                    """
                    UPDATE organizations

                    SET
                        status = 'PENDING',
                        verification_status = 'REJECTED',
                        updated_at = CURRENT_TIMESTAMP

                    WHERE id = %s
                    """,
                    (organization_id,),
                )

                cursor.execute(
                    """
                    UPDATE organization_memberships

                    SET
                        status = 'REJECTED',
                        updated_at = CURRENT_TIMESTAMP

                    WHERE organization_id = %s
                      AND status = 'PENDING'
                    """,
                    (organization_id,),
                )

            cursor.execute(
                """
                UPDATE organization_verification_records

                SET
                    status = %s,
                    reviewed_by = %s,
                    reviewed_at = CURRENT_TIMESTAMP,
                    reason = %s

                WHERE id = %s
                """,
                (
                    decision,
                    reviewer_id,
                    reason.strip()
                    if reason
                    else None,
                    verification["id"],
                ),
            )

            return {
                "organization_id": organization_id,
                "verification_status": decision,
                "membership_status": (
                    "ACTIVE"
                    if decision == "VERIFIED"
                    else "REJECTED"
                ),
            }

    finally:

        conn.close()