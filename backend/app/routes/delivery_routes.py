from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import require_buyer
from app.core.dependencies import require_supplier
from app.schemas.delivery_schema import (
    DeliveryLogCreate,
    DeliveryVerify
)
from app.models.deliveries import (
    get_latest_pending_delivery,
    verify_delivery_record,
    get_supplier_deliveries
)
from app.core.db import get_db
from app.engines.delivery_engine import compute_truth_confidence
from app.utils.delivery_validators import validate_verified_delivery
import logging

logger=logging.getLogger("agroflow")
router = APIRouter()

@router.post("/delivery/verify/{commitment_id}")
def verify_delivery(
    commitment_id: int,
    payload: DeliveryVerify,
    user=Depends(require_buyer)
):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT *
        FROM supplier_commitments
        WHERE id = %s
    """, (commitment_id,))
    commitment = cursor.fetchone()

    if not commitment:
        conn.close()
        raise HTTPException(404, "Commitment not found")

    if commitment["school_id"] != user["id"]:
        conn.close()
        raise HTTPException(403, "Not your commitment")

    delivery = get_latest_pending_delivery(cursor, commitment_id)

    if not delivery:
        conn.close()
        raise HTTPException(404, "No pending delivery")

    confidence = compute_truth_confidence(
        payload.verification_status,
        payload.quality_status,
        payload.delay_status
    )

    validate_verified_delivery(
    payload.verification_status,
    payload.received_qty,
    payload.quality_status,
    payload.delay_status
)

    updated_delivery = verify_delivery_record(
    cursor,
    delivery["id"],
    payload,
    user["id"],
    confidence
)

    conn.commit()
    conn.close()

    return {
    "message":"Delivery verified",
    "delivery":updated_delivery,
    "confidence_score":confidence
}

@router.get("/school/deliveries")
def get_school_deliveries(user=Depends(require_buyer)):
    conn, cursor = get_db()

    try:
        cursor.execute("""
    SELECT 
        d.id,
        d.commitment_id,

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

        supplier.name AS supplier_name,
        school.name AS school_name

    FROM deliveries d

    JOIN supplier_commitments c
    ON d.commitment_id = c.id

    JOIN users supplier
    ON c.supplier_id = supplier.id

    JOIN users school
    ON c.school_id = school.id

    WHERE c.school_id=%s

    ORDER BY d.created_at DESC

""",(user["id"],))
        deliveries = cursor.fetchall()

        logger.info(
    "School deliveries loaded",
    extra={
        "school_id":user["id"],
        "count":len(deliveries)
    }
)
        return deliveries
        
    finally:
        conn.close()
        
@router.post("/supplier/delivery/log/{commitment_id}")
def log_delivery(
    commitment_id: int,
    payload: DeliveryLogCreate,
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    cursor.execute("""
SELECT supplier_id
FROM supplier_commitments
WHERE id=%s
""",(
    commitment_id,
))

    commitment=cursor.fetchone()

    if commitment is None:
        raise HTTPException(
        status_code=404,
        detail="Commitment not found"
    )

    if commitment["supplier_id"]!=user["id"]:
        raise HTTPException(
        status_code=403,
        detail="Cannot deliver another supplier's commitment"
    )
    try:
        cursor.execute("""
SELECT id
FROM deliveries
WHERE commitment_id=%s
AND week_start=%s
AND week_end=%s
""",(
    payload.commitment_id,
    payload.week_start,
    payload.week_end
))

        if cursor.fetchone():
            raise HTTPException(
        status_code=409,
        detail="Delivery already submitted for this period"
    )
        cursor.execute("""
            INSERT INTO deliveries (
                commitment_id,
                delivered_qty,
                week_start,
                week_end
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (
            commitment_id,
            payload.delivered_qty,
            payload.week_start,
            payload.week_end
        ))

        delivery = cursor.fetchone()
        conn.commit()

        return {
            "status": "LOGGED",
            "delivery_id": delivery["id"]
        }

    finally:
        conn.close()

@router.get("/supplier/deliveries")
def supplier_deliveries(
    user=Depends(require_supplier)
):
    return get_supplier_deliveries(user["id"])