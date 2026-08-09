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

        confidence_result = compute_truth_confidence(
    payload.verification_status,
    payload.quality_status,
    payload.delay_status
)

        confidence_score = confidence_result["score"]
        log_decision(

    cursor,

    actor_id=user["id"],

    decision_type="TRUTH_CONFIDENCE",

    reference_id=delivery["id"],

    explanation=(
    f"Confidence score: {confidence_score}. "
    f"Factors: {confidence_result['factors']}"
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
    confidence_score
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
    "confidence_score":confidence_score
}

    except HTTPException:
        conn.rollback()
        raise

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

        raise HTTPException(
            status_code=500,
            detail="Verification failed due to a server error."
        )

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
    commitment_id,
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

@router.put("/supplier/delivery/{delivery_id}")
def edit_supplier_delivery(
    delivery_id: int,
    payload: DeliveryLogCreate,
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    try:

        # =====================================================
        # LOAD DELIVERY + OWNERSHIP
        # =====================================================

        cursor.execute("""
            SELECT
                d.*,
                c.supplier_id
            FROM deliveries d

            JOIN supplier_commitments c
            ON d.commitment_id = c.id

            WHERE d.id = %s
        """, (delivery_id,))

        delivery = cursor.fetchone()

        if not delivery:
            raise HTTPException(
                status_code=404,
                detail="Delivery not found"
            )

        if delivery["supplier_id"] != user["id"]:
            raise HTTPException(
                status_code=403,
                detail="Cannot edit another supplier's delivery"
            )

        # =====================================================
        # VERIFIED RECORDS ARE NOT SILENTLY OVERWRITTEN
        # =====================================================

        if delivery["verification_status"] in (
            "VERIFIED",
            "PARTIAL"
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This delivery has already been verified. "
                    "A verified delivery must be corrected through "
                    "the verification correction process."
                )
            )

        # =====================================================
        # UPDATE SUPPLIER'S DELIVERY ENTRY
        # =====================================================

        cursor.execute("""
            UPDATE deliveries
            SET
                delivered_qty = %s,
                week_start = %s,
                week_end = %s
            WHERE id = %s
            RETURNING *
        """, (
            payload.delivered_qty,
            payload.week_start,
            payload.week_end,
            delivery_id
        ))

        updated = cursor.fetchone()

        create_audit_log(
            cursor,
            user["id"],
            "EDIT_DELIVERY",
            "delivery",
            delivery_id,
            old_data=dict(delivery),
            new_data=dict(updated)
        )

        conn.commit()

        return {
            "message": "Delivery updated",
            "delivery": updated
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception as e:

        conn.rollback()

        log_error(
            message="Supplier delivery edit failed",
            user_id=user["id"],
            action="EDIT_DELIVERY",
            entity="delivery",
            extra={
                "exception": str(e)
            }
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to update delivery."
        )

    finally:
        conn.close()

@router.delete("/supplier/delivery/{delivery_id}")
def delete_supplier_delivery(
    delivery_id: int,
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    try:

        cursor.execute("""
            SELECT
                d.*,
                c.supplier_id
            FROM deliveries d

            JOIN supplier_commitments c
            ON d.commitment_id = c.id

            WHERE d.id = %s
        """, (delivery_id,))

        delivery = cursor.fetchone()

        if not delivery:
            raise HTTPException(
                status_code=404,
                detail="Delivery not found"
            )

        if delivery["supplier_id"] != user["id"]:
            raise HTTPException(
                status_code=403,
                detail="Cannot delete another supplier's delivery"
            )

        if delivery["verification_status"] in (
            "VERIFIED",
            "PARTIAL"
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Verified deliveries cannot be deleted. "
                    "Use the correction process instead."
                )
            )

        create_audit_log(
            cursor,
            user["id"],
            "DELETE_DELIVERY",
            "delivery",
            delivery_id,
            old_data=dict(delivery)
        )

        cursor.execute("""
            DELETE FROM deliveries
            WHERE id = %s
        """, (delivery_id,))

        conn.commit()

        return {
            "message": "Delivery deleted",
            "delivery_id": delivery_id
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception as e:

        conn.rollback()

        log_error(
            message="Supplier delivery deletion failed",
            user_id=user["id"],
            action="DELETE_DELIVERY",
            entity="delivery",
            extra={
                "exception": str(e)
            }
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to delete delivery."
        )

    finally:
        conn.close()

@router.put("/delivery/verification/{delivery_id}")
def correct_delivery_verification(
    delivery_id: int,
    payload: DeliveryVerify,
    user=Depends(require_buyer)
):
    conn, cursor = get_db()

    try:

        cursor.execute("""
            SELECT
                d.*,
                c.school_id
            FROM deliveries d

            JOIN supplier_commitments c
            ON d.commitment_id = c.id

            WHERE d.id = %s
        """, (delivery_id,))

        delivery = cursor.fetchone()

        if not delivery:
            raise HTTPException(
                status_code=404,
                detail="Delivery not found"
            )

        if delivery["school_id"] != user["id"]:
            raise HTTPException(
                status_code=403,
                detail="Not your delivery"
            )

        # The school may correct the verification truth,
        # but may not alter the supplier's delivered quantity.
        if payload.received_qty > delivery["delivered_qty"]:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Received quantity cannot exceed "
                    "delivered quantity."
                )
            )

        confidence_result = compute_truth_confidence(
            payload.verification_status,
            payload.quality_status,
            payload.delay_status
        )

        confidence_score = confidence_result["score"]

        validate_verified_delivery(
            payload.verification_status,
            payload.received_qty,
            payload.quality_status,
            payload.delay_status
        )

        log_decision(
            cursor,
            actor_id=user["id"],
            decision_type="TRUTH_CONFIDENCE_CORRECTION",
            reference_id=delivery_id,
            explanation=(
                f"Verification corrected. "
                f"Confidence score: {confidence_score}. "
                f"Factors: {confidence_result['factors']}"
            )
        )

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
            user["id"],
            confidence_score,
            delivery_id
        ))

        updated = cursor.fetchone()

        create_audit_log(
            cursor,
            user["id"],
            "CORRECT_DELIVERY_VERIFICATION",
            "delivery",
            delivery_id,
            old_data=dict(delivery),
            new_data=dict(updated)
        )

        conn.commit()

        return {
            "message": "Delivery verification corrected",
            "delivery": updated,
            "confidence_score": confidence_score
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception as e:

        conn.rollback()

        log_error(
            message="Delivery verification correction failed",
            user_id=user["id"],
            action="CORRECT_DELIVERY_VERIFICATION",
            entity="delivery",
            extra={
                "exception": str(e)
            }
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to correct delivery verification."
        )

    finally:
        conn.close()

@router.get("/supplier/deliveries")
def supplier_deliveries(
    limit: int = 20,
    offset: int = 0,
    user=Depends(require_supplier)
):
    return get_supplier_deliveries(user["id"], limit, offset)

@router.delete("/delivery/verification/{delivery_id}")
def reset_delivery_verification(
    delivery_id: int,
    user=Depends(require_buyer)
):
    conn, cursor = get_db()

    try:

        cursor.execute("""
            SELECT
                d.*,
                c.school_id
            FROM deliveries d

            JOIN supplier_commitments c
            ON d.commitment_id = c.id

            WHERE d.id = %s
        """, (delivery_id,))

        delivery = cursor.fetchone()

        if not delivery:
            raise HTTPException(
                status_code=404,
                detail="Delivery not found"
            )

        if delivery["school_id"] != user["id"]:
            raise HTTPException(
                status_code=403,
                detail="Not your delivery"
            )

        create_audit_log(
            cursor,
            user["id"],
            "RESET_DELIVERY_VERIFICATION",
            "delivery",
            delivery_id,
            old_data=dict(delivery)
        )

        cursor.execute("""
            UPDATE deliveries
            SET
                received_qty = NULL,
                quality_status = NULL,
                delay_status = NULL,
                verification_status = NULL,
                verification_notes = NULL,
                verified_by = NULL,
                confidence_score = NULL,
                verified_at = NULL
            WHERE id = %s
            RETURNING *
        """, (delivery_id,))

        updated = cursor.fetchone()

        conn.commit()

        return {
            "message": "Delivery verification reset",
            "delivery": updated
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception as e:

        conn.rollback()

        log_error(
            message="Delivery verification reset failed",
            user_id=user["id"],
            action="RESET_DELIVERY_VERIFICATION",
            entity="delivery",
            extra={
                "exception": str(e)
            }
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to reset delivery verification."
        )

    finally:
        conn.close()