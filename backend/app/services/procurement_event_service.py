from fastapi import HTTPException


# =========================================================
# PROCUREMENT ACCESS
# =========================================================

def ensure_procurement_access(
    cursor,
    procurement_id,
    user_id
):

    cursor.execute(
        """
        SELECT
            p.id,
            p.organization_id
        FROM procurements p

        JOIN organization_memberships om
            ON om.organization_id =
                p.organization_id

        WHERE p.id = %s

          AND om.user_id = %s

          AND om.status = 'ACTIVE'
        """,
        (
            procurement_id,
            user_id
        )
    )

    procurement = cursor.fetchone()


    if not procurement:

        raise HTTPException(
            status_code=404,
            detail="Procurement not found."
        )


    return procurement


# =========================================================
# TIMELINE
# =========================================================

def get_procurement_timeline(
    cursor,
    procurement_id,
    user_id
):

    ensure_procurement_access(
        cursor,
        procurement_id,
        user_id
    )


    cursor.execute(
        """
        SELECT

            pe.id,

            pe.procurement_id,

            pe.event_type,

            pe.title,

            pe.description,

            pe.actor_id,

            actor.name
                AS actor_name,

            pe.entity_type,

            pe.entity_id,

            pe.occurred_at,

            pe.metadata,

            pe.created_at

        FROM procurement_events pe

        JOIN users actor
            ON actor.id =
                pe.actor_id

        WHERE pe.procurement_id = %s

        ORDER BY
            pe.occurred_at ASC,
            pe.id ASC
        """,
        (
            procurement_id,
        )
    )

    events = cursor.fetchall()


    # -----------------------------------------------------
    # ATTACH EVENT EVIDENCE
    # -----------------------------------------------------

    for event in events:

        cursor.execute(
            """
            SELECT

                ed.id,

                ed.document_type,

                ed.document_name,

                ed.original_filename,

                ed.mime_type,

                ed.file_size,

                ed.visibility,

                ed.uploaded_by,

                u.name
                    AS uploaded_by_name,

                ed.uploaded_at

            FROM evidence_documents ed

            JOIN users u
                ON u.id =
                    ed.uploaded_by

            WHERE ed.event_id = %s

              AND ed.deleted_at IS NULL

            ORDER BY
                ed.uploaded_at ASC,
                ed.id ASC
            """,
            (
                event["id"],
            )
        )


        event["evidence"] = (
            cursor.fetchall()
        )


    return events


# =========================================================
# AUDIT TRAIL
# =========================================================

def get_procurement_audit(
    cursor,
    procurement_id,
    user_id
):

    ensure_procurement_access(
        cursor,
        procurement_id,
        user_id
    )


    cursor.execute(
        """
        SELECT

            ae.id,

            ae.procurement_id,

            ae.actor_id,

            actor.name
                AS actor_name,

            ae.action,

            ae.entity_type,

            ae.entity_id,

            ae.previous_state,

            ae.new_state,

            ae.metadata,

            ae.created_at

        FROM audit_events ae

        JOIN users actor
            ON actor.id =
                ae.actor_id

        WHERE ae.procurement_id = %s

        ORDER BY
            ae.created_at ASC,
            ae.id ASC
        """,
        (
            procurement_id,
        )
    )


    return cursor.fetchall()