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
from app.core.logger import (
    log_warning,
    log_error,
    log_info
)
from app.utils.audit import create_audit_log
from app.logs.decision_logger import log_decision

router = APIRouter()

@router.post("/delivery/verify/{commitment_id}")
def verify_delivery(
    commitment_id: int,
    payload: DeliveryVerify,
    user=Depends(require_buyer)
):
    conn, cursor = get_db()

    try:

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
    
        log_decision(

    cursor,

    actor_id=user["id"],

    decision_type="TRUTH_CONFIDENCE",

    reference_id=delivery["id"],

    explanation=(
        f"Computed confidence score "
        f"{confidence}."
    )

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
        create_audit_log(

    cursor,

    user["id"],

    "VERIFY_DELIVERY",

    "delivery",

    delivery["id"],

    new_data={
        "verification_status":
            payload.verification_status,
        "quality_status":
            payload.quality_status,
        "delay_status":
            payload.delay_status
    }

)
        conn.commit()
        return {
    "message":"Delivery verified",
    "delivery":updated_delivery,
    "confidence_score":confidence
}

    except Exception as e:

        conn.rollback()

        log_error(
        message="Database transaction failed",
        user_id=user["id"],
        action="DATABASE_ERROR",
        entity="delivery",
        extra={
            "exception": str(e)
        }
    )

        raise

    finally:

        conn.close()

@router.get("/school/deliveries")
def get_school_deliveries(
    limit: int = 20,
    offset: int = 0,
    user=Depends(require_buyer)
):
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
    LIMIT %s
OFFSET %s

""",(user["id"], limit, offset))
        deliveries = cursor.fetchall()

        log_info(
    message="School viewed deliveries",
    user_id=user["id"],
    action="VIEW_DELIVERIES",
    entity="supply_source",
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

        create_audit_log(

    cursor,

    user["id"],

    "CREATE_DELIVERY",

    "delivery",

    delivery["id"],

    new_data={
        "quantity":
            payload.delivered_qty,
        "commitment_id":
            commitment_id
    }

)

        conn.commit()
        return {
            "status": "LOGGED",
            "delivery_id": delivery["id"]
        }

    finally:
        conn.close()

@router.get("/supplier/deliveries")
def supplier_deliveries(
    limit: int = 20,
    offset: int = 0,
    user=Depends(require_supplier)
):
    return get_supplier_deliveries(user["id"], limit, offset)