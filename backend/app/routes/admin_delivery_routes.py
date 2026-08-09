from fastapi import APIRouter, Depends, HTTPException

from app.core.db import get_db
from app.core.dependencies import require_admin

from app.utils.delivery_validators import (
    validate_verified_delivery
)

from app.engines.delivery_engine import (
    compute_truth_confidence
)
from app.utils.audit import create_audit_log
from app.logs.decision_logger import log_decision
from app.core.logger import log_error
router = APIRouter(
    prefix="/dashboard/system",
    tags=["Admin Delivery Control"]
)

# ============================================
# GET DELIVERY HISTORY FOR COMMITMENT
# ============================================

@router.get("/commitment/{commitment_id}/deliveries")
def get_commitment_deliveries(
    commitment_id:int,
    limit: int = 20,
    offset: int = 0,
    user=Depends(require_admin)
):

    conn, cursor = get_db()

    try:

        cursor.execute("""
            SELECT
                d.*,
                c.product,
                s.name AS supplier_name,
                sch.name AS school_name

            FROM deliveries d

            JOIN supplier_commitments c
            ON d.commitment_id = c.id

            JOIN users s
            ON c.supplier_id = s.id

            JOIN users sch
            ON c.school_id = sch.id

            WHERE d.commitment_id=%s

            ORDER BY d.created_at DESC
            LIMIT %s
            OFFSET %s

        """,(commitment_id, limit, offset))

        return cursor.fetchall()

    finally:
        conn.close()

# ============================================
# ADMIN CORRECTION
# ============================================
@router.put("/delivery/{delivery_id}")
def correct_delivery(
    delivery_id: int,
    payload: dict,
    user=Depends(require_admin)
):

    conn, cursor = get_db()

    try:

        cursor.execute("""
            SELECT *
            FROM deliveries
            WHERE id=%s
        """, (delivery_id,))

        delivery = cursor.fetchone()

        if not delivery:
            raise HTTPException(
                status_code=404,
                detail="Delivery not found"
            )

        # =====================================================
        # NORMALIZE QUANTITIES
        # =====================================================
        # Frontend form values may arrive as strings.
        # Convert them before applying business rules.

        delivered_qty = payload.get(
            "delivered_qty",
            delivery["delivered_qty"]
        )

        received_qty = payload.get(
            "received_qty",
            delivery["received_qty"]
        )

        try:

            if delivered_qty is not None:
                delivered_qty = int(delivered_qty)

            if received_qty is not None:
                received_qty = int(received_qty)

        except (TypeError, ValueError):

            raise HTTPException(
                status_code=400,
                detail="Delivered and received quantities must be valid numbers"
            )

        # =====================================================
        # QUANTITY BUSINESS RULES
        # =====================================================

        if delivered_qty is not None and delivered_qty < 0:

            raise HTTPException(
                status_code=400,
                detail="Delivered quantity cannot be negative"
            )

        if received_qty is not None and received_qty < 0:

            raise HTTPException(
                status_code=400,
                detail="Received quantity cannot be negative"
            )

        # =====================================================
        # QUANTITY BUSINESS RULES
        # =====================================================

        if delivered_qty is not None and delivered_qty < 0:

            raise HTTPException(
        status_code=400,
        detail="Delivered quantity cannot be negative"
    )

        if received_qty is not None and received_qty < 0:

            raise HTTPException(
        status_code=400,
        detail="Received quantity cannot be negative"
    )

     # Physical truth invariant:
     # quantity received cannot exceed quantity actually delivered.
     # This does NOT prevent an administrator from correcting
     # delivered_qty upward when the original delivery entry
     # was wrong. It only prevents an impossible relationship.

        if (
    received_qty is not None
    and delivered_qty is not None
    and received_qty > delivered_qty
):

            raise HTTPException(
        status_code=400,
        detail=(
            "Received quantity cannot exceed delivered quantity. "
            "Correct the delivered quantity first if the original "
            "delivery record was entered incorrectly."
        )
    )

        # =====================================================
        # OTHER TRUTH FIELDS
        # =====================================================

        quality_status = payload.get(
            "quality_status",
            delivery["quality_status"]
        )

        delay_status = payload.get(
            "delay_status",
            delivery["delay_status"]
        )

        verification_status = payload.get(
            "verification_status",
            delivery["verification_status"]
        )

        verification_notes = payload.get(
            "verification_notes",
            "Admin correction"
        )

        # =====================================================
        # CORE TRUTH VALIDATION
        # =====================================================

        validate_verified_delivery(
            verification_status,
            received_qty,
            quality_status,
            delay_status
        )

        # =====================================================
        # TRUTH CONFIDENCE
        # =====================================================

        confidence = compute_truth_confidence(
            verification_status,
            quality_status,
            delay_status
        )

        # The confidence engine returns an intelligence object:
        #
        # {
        #     "score": 1.0,
        #     "factors": {...}
        # }
        #
        # The database confidence_score column stores only
        # the numeric score.

        if isinstance(confidence, dict):

            confidence_score = confidence.get("score")

        else:

            confidence_score = confidence

        if confidence_score is None:

            raise HTTPException(
                status_code=500,
                detail="Truth confidence engine returned no score"
            )

        # =====================================================
        # DECISION LOG
        # =====================================================

        log_decision(

            cursor,

            actor_id=user["id"],

            decision_type="TRUTH_CONFIDENCE",

            reference_id=delivery["id"],

            explanation=(
                f"Computed confidence score "
                f"{confidence_score}."
            )

        )

        # =====================================================
        # UPDATE DELIVERY
        # =====================================================

        cursor.execute("""
            UPDATE deliveries

            SET

                delivered_qty=%s,
                received_qty=%s,
                quality_status=%s,
                delay_status=%s,
                verification_status=%s,

                verification_notes=%s,

                verified_by=%s,

                confidence_score=%s,

                verified_at=CURRENT_TIMESTAMP

            WHERE id=%s

            RETURNING *

        """, (
            delivered_qty,
            received_qty,
            quality_status,
            delay_status,
            verification_status,

            verification_notes,

            user["id"],

            confidence_score,

            delivery_id
        ))

        updated = cursor.fetchone()

        # =====================================================
        # AUDIT LOG
        # =====================================================

        create_audit_log(

            cursor,

            user["id"],

            "CORRECT_DELIVERY",

            "delivery",

            delivery_id,

            old_data=dict(delivery),

            new_data=dict(updated)

        )

        # =====================================================
        # COMMIT
        # =====================================================

        conn.commit()

        return {

            "message": "Delivery corrected",

            "delivery": updated

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

        raise

    finally:

        conn.close()
