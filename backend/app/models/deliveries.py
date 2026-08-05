from app.core.db import get_db

def log_delivery(
    commitment_id,
    delivered_qty,
    week_start,
    week_end
):
    conn, cursor = get_db()

    cursor.execute("""
        INSERT INTO deliveries (
            commitment_id,
            delivered_qty,
            week_start,
            week_end
        )
        VALUES (%s,%s,%s,%s)
        RETURNING *
    """, (
        commitment_id,
        delivered_qty,
        week_start,
        week_end
    ))

    delivery = cursor.fetchone()

    conn.commit()
    conn.close()

    return delivery

def get_supplier_deliveries(supplier_id, limit=20,
    offset=0):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT
    d.id,

    d.delivered_qty,
    d.week_start,
    d.week_end,
    d.received_qty,

    d.quality_status,
    d.delay_status,
    d.verification_status,
    d.confidence_score,
    d.verified_at,

    c.product,
    c.promised_qty,

    school.name AS school_name

FROM deliveries d

JOIN supplier_commitments c
ON d.commitment_id = c.id

JOIN users school
ON school.id = c.school_id

WHERE c.supplier_id=%s

ORDER BY d.created_at DESC
LIMIT %s
OFFSET %s
    """, (supplier_id, limit, offset))

    deliveries = cursor.fetchall()

    conn.close()

    return deliveries

def verify_delivery(
    delivery_id,
    received_qty,
    quality_status,
    delay_status,
    verification_status,
    notes,
    verified_by
):
    conn, cursor = get_db()

    cursor.execute("""
        UPDATE deliveries
        SET
            received_qty = %s,
            quality_status = %s,
            delay_status = %s,
            verification_status = %s,
            verification_notes = %s,
            verified_by = %s,
            verified_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
    """, (
        received_qty,
        quality_status,
        delay_status,
        verification_status,
        notes,
        verified_by,
        delivery_id
    ))

    delivery = cursor.fetchone()

    conn.commit()
    conn.close()

    return delivery


def get_commitment_deliveries(commitment_id):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT *
        FROM deliveries
        WHERE commitment_id = %s
    """, (commitment_id,))

    deliveries = cursor.fetchall()

    conn.close()

    return deliveries

def get_latest_pending_delivery(cursor, commitment_id, limit=20,
    offset=0):
    cursor.execute("""
        SELECT *
        FROM deliveries
        WHERE commitment_id = %s
        AND verification_status IS NULL
        ORDER BY id DESC
        LIMIT 1
    """, (commitment_id, limit, offset))

    return cursor.fetchone()

def verify_delivery_record(
    cursor,
    delivery_id,
    payload,
    verified_by,
    confidence,
    limit=20,
    offset=0
):
    # Step 1: Load current delivery
    cursor.execute("""
        SELECT delivered_qty
        FROM deliveries
        WHERE id = %s
    """, (delivery_id, limit, offset))

    delivery = cursor.fetchone()

    if not delivery:
        raise Exception("Delivery not found")

    # Step 2: Enforce the invariant
    if payload.received_qty > delivery["delivered_qty"]:
        raise Exception(
            "Received quantity cannot exceed delivered quantity."
        )

    # Step 3: Update
    cursor.execute("""
        UPDATE deliveries
        SET
            received_qty = %s,
            quality_status = %s,
            delay_status = %s,
            verification_status = %s,
            verification_notes = %s,
            verified_by = %s,
            confidence_score = %s,
            verified_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
    """, (
        payload.received_qty,
        payload.quality_status,
        payload.delay_status,
        payload.verification_status,
        payload.verification_notes,
        verified_by,
        confidence,
        delivery_id
    ))

    return cursor.fetchone()