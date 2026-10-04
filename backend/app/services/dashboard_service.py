from fastapi import HTTPException


ACTIVE_STATUSES = {
    "SUBMITTED",
    "EVALUATION",
    "SELECTED",
    "ORDERED",
    "COMMITTED",
    "DELIVERY",
    "INSPECTION",
    "ACCEPTED",
}


def _require_school_organization(cursor, organization_id):
    cursor.execute(
        """
        SELECT id, name, organization_type, status, verification_status
        FROM organizations
        WHERE id = %s
        """,
        (organization_id,),
    )
    organization = cursor.fetchone()

    if not organization:
        raise HTTPException(404, "Organization not found.")

    if organization["organization_type"] != "SCHOOL":
        raise HTTPException(409, "This dashboard is only available for school organizations.")

    if organization["status"] != "ACTIVE" or organization["verification_status"] != "VERIFIED":
        raise HTTPException(403, "The organization must be active and verified.")

    return organization


def get_school_dashboard(cursor, organization_id):
    organization = _require_school_organization(cursor, organization_id)

    cursor.execute(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE p.status IN (
                    'SUBMITTED','EVALUATION','SELECTED','ORDERED',
                    'COMMITTED','DELIVERY','INSPECTION','ACCEPTED'
                )
            ) AS active_count,
            COUNT(*) FILTER (WHERE p.status = 'EVALUATION') AS awaiting_selection_count,
            COUNT(*) FILTER (WHERE p.status IN ('COMMITTED','DELIVERY')) AS awaiting_delivery_count,
            COUNT(*) FILTER (WHERE p.status = 'COMPLETED') AS completed_count,
            COUNT(*) FILTER (WHERE p.status = 'CANCELLED') AS cancelled_count,
            COUNT(*) AS total_count
        FROM procurements p
        WHERE p.organization_id = %s
        """,
        (organization_id,),
    )
    counts = cursor.fetchone() or {}

    cursor.execute(
        """
        WITH promised AS (
            SELECT po.procurement_id, SUM(sc.promised_qty) AS promised_qty
            FROM purchase_orders po
            JOIN supplier_commitments sc
              ON sc.purchase_order_id = po.id
             AND sc.status = 'ACCEPTED'
            WHERE po.procurement_id IN (
                SELECT id FROM procurements WHERE organization_id = %s
            )
            GROUP BY po.procurement_id
        ),
        delivered AS (
            SELECT po.procurement_id, SUM(dl.actual_quantity) AS delivered_qty
            FROM purchase_orders po
            JOIN supplier_commitments sc ON sc.purchase_order_id = po.id
            JOIN deliveries d ON d.commitment_id = sc.id
            JOIN delivery_lines dl ON dl.delivery_id = d.id
            GROUP BY po.procurement_id
        ),
        verified AS (
            SELECT po.procurement_id, SUM(i.received_qty) AS verified_qty
            FROM purchase_orders po
            JOIN supplier_commitments sc ON sc.purchase_order_id = po.id
            JOIN deliveries d ON d.commitment_id = sc.id
            JOIN inspections i ON i.delivery_id = d.id
            WHERE i.result = 'ACCEPTED'
            GROUP BY po.procurement_id
        ),
        inspection_flags AS (
            SELECT
                po.procurement_id,
                COUNT(*) FILTER (WHERE i.result = 'REJECTED') AS rejected_count,
                COUNT(*) FILTER (WHERE i.delay_status = 'DELAYED') AS delayed_count
            FROM purchase_orders po
            JOIN supplier_commitments sc ON sc.purchase_order_id = po.id
            JOIN deliveries d ON d.commitment_id = sc.id
            JOIN inspections i ON i.delivery_id = d.id
            GROUP BY po.procurement_id
        )
        SELECT COUNT(*) AS discrepancy_count
        FROM procurements p
        LEFT JOIN promised pr ON pr.procurement_id = p.id
        LEFT JOIN delivered de ON de.procurement_id = p.id
        LEFT JOIN verified ve ON ve.procurement_id = p.id
        LEFT JOIN inspection_flags f ON f.procurement_id = p.id
        WHERE p.organization_id = %s
          AND (
              (pr.promised_qty IS NOT NULL AND COALESCE(de.delivered_qty, 0) <> pr.promised_qty)
              OR (pr.promised_qty IS NOT NULL AND ve.procurement_id IS NOT NULL
                  AND COALESCE(ve.verified_qty, 0) <> pr.promised_qty)
              OR COALESCE(f.rejected_count, 0) > 0
              OR COALESCE(f.delayed_count, 0) > 0
          )
        """,
        (organization_id, organization_id),
    )
    discrepancy_count = (cursor.fetchone() or {}).get("discrepancy_count", 0)

    cursor.execute(
        """
        SELECT COUNT(*) AS awaiting_inspection_count
        FROM deliveries d
        JOIN supplier_commitments sc ON sc.id = d.commitment_id
        JOIN purchase_orders po ON po.id = sc.purchase_order_id
        JOIN procurements p ON p.id = po.procurement_id
        WHERE p.organization_id = %s
          AND d.delivery_status = 'AWAITING_INSPECTION'
        """,
        (organization_id,),
    )
    awaiting_inspection_count = (cursor.fetchone() or {}).get("awaiting_inspection_count", 0)

    cursor.execute(
        """
        SELECT
            d.id,
            d.delivery_date,
            p.id AS procurement_id,
            p.procurement_identifier,
            p.title,
            d.delivery_status,
            s.supplier_code,
            so.name AS supplier_name
        FROM deliveries d
        JOIN supplier_commitments sc ON sc.id = d.commitment_id
        JOIN purchase_orders po ON po.id = sc.purchase_order_id
        JOIN procurements p ON p.id = po.procurement_id
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN organizations so ON so.id = s.organization_id
        WHERE p.organization_id = %s
          AND d.delivery_status = 'AWAITING_INSPECTION'
        ORDER BY d.delivery_date ASC, d.id ASC
        LIMIT 8
        """,
        (organization_id,),
    )
    pending_inspections = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            p.id,
            p.procurement_identifier,
            p.title,
            p.status,
            p.required_by_date,
            p.updated_at,
            pe.event_type,
            pe.title AS last_event_title,
            pe.occurred_at AS last_event_at,
            actor.name AS last_actor_name
        FROM procurements p
        LEFT JOIN LATERAL (
            SELECT event_type, title, occurred_at, actor_id
            FROM procurement_events
            WHERE procurement_id = p.id
            ORDER BY occurred_at DESC, id DESC
            LIMIT 1
        ) pe ON TRUE
        LEFT JOIN users actor ON actor.id = pe.actor_id
        WHERE p.organization_id = %s
        ORDER BY p.updated_at DESC, p.id DESC
        LIMIT 8
        """,
        (organization_id,),
    )
    recent_procurements = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            u.id AS user_id,
            u.name AS user_name,
            COUNT(pe.id) AS event_count,
            MAX(pe.occurred_at) AS last_activity_at,
            ARRAY_AGG(DISTINCT pe.event_type) FILTER (WHERE pe.event_type IS NOT NULL) AS actions
        FROM procurement_events pe
        JOIN procurements p ON p.id = pe.procurement_id
        JOIN users u ON u.id = pe.actor_id
        WHERE p.organization_id = %s
        GROUP BY u.id, u.name
        ORDER BY MAX(pe.occurred_at) DESC, u.id
        LIMIT 8
        """,
        (organization_id,),
    )
    team_activity = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            u.id AS user_id,
            u.name,
            u.email,
            m.id AS membership_id,
            m.status AS membership_status,
            COALESCE(
                ARRAY_AGG(DISTINCT r.code) FILTER (WHERE r.code IS NOT NULL),
                ARRAY[]::text[]
            ) AS responsibilities
        FROM organization_memberships m
        JOIN users u ON u.id = m.user_id
        LEFT JOIN membership_responsibilities mr ON mr.membership_id = m.id
        LEFT JOIN responsibilities r ON r.id = mr.responsibility_id
        WHERE m.organization_id = %s
        GROUP BY u.id, u.name, u.email, m.id, m.status
        ORDER BY u.name, u.id
        """,
        (organization_id,),
    )
    members = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            p.id AS procurement_id,
            p.procurement_identifier,
            p.title,
            p.status,
            i.id AS inspection_id,
            i.result,
            i.quality_status,
            i.delay_status,
            i.received_qty,
            d.delivery_date
        FROM procurements p
        JOIN purchase_orders po ON po.procurement_id = p.id
        JOIN supplier_commitments sc ON sc.purchase_order_id = po.id
        JOIN deliveries d ON d.commitment_id = sc.id
        JOIN inspections i ON i.delivery_id = d.id
        WHERE p.organization_id = %s
          AND (
              i.result = 'REJECTED'
              OR i.delay_status = 'DELAYED'
              OR i.quality_status = 'FAILED'
          )
        ORDER BY i.inspected_at DESC, i.id DESC
        LIMIT 8
        """,
        (organization_id,),
    )
    attention_items = cursor.fetchall()

    return {
        "organization": dict(organization),
        "overview": {
            "active": counts.get("active_count", 0),
            "awaiting_selection": counts.get("awaiting_selection_count", 0),
            "awaiting_delivery": counts.get("awaiting_delivery_count", 0),
            "awaiting_inspection": awaiting_inspection_count,
            "discrepancies": discrepancy_count,
            "completed": counts.get("completed_count", 0),
            "cancelled": counts.get("cancelled_count", 0),
            "total": counts.get("total_count", 0),
        },
        "recent_procurements": [dict(row) for row in recent_procurements],
        "pending_inspections": [dict(row) for row in pending_inspections],
        "team_activity": [dict(row) for row in team_activity],
        "members": [dict(row) for row in members],
        "attention_required": [dict(row) for row in attention_items],
    }
