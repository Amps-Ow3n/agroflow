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

        """,(commitment_id,))


        return cursor.fetchall()


    finally:
        conn.close()



# ============================================
# ADMIN CORRECTION
# ============================================

@router.put("/delivery/{delivery_id}")
def correct_delivery(
    delivery_id:int,
    payload:dict,
    user=Depends(require_admin)
):

    conn,cursor=get_db()


    try:

        cursor.execute("""
            SELECT *
            FROM deliveries
            WHERE id=%s
        """,(delivery_id,))

        delivery=cursor.fetchone()

        received_qty = payload.get(
                    "received_qty",
                    delivery["received_qty"]
                )
        
        if (
           received_qty is not None
           and
           received_qty > delivery["delivered_qty"]
):
           raise HTTPException(
        status_code=400,
        detail="Received quantity cannot exceed delivered quantity"
    )
        if not delivery:

            raise HTTPException(
                status_code=404,
                detail="Delivery not found"
            )

        if received_qty is not None:
            received_qty = int(received_qty)

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


        # CORE RULE CHECK
        validate_verified_delivery(
            verification_status,
            received_qty,
            quality_status,
            delay_status
        )


        confidence = compute_truth_confidence(
            verification_status,
            quality_status,
            delay_status
        )


        cursor.execute("""
            UPDATE deliveries

            SET

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

        """,(
            received_qty,
            quality_status,
            delay_status,
            verification_status,

            payload.get(
                "verification_notes",
                "Admin correction"
            ),

            user["id"],

            confidence,

            delivery_id
        ))

        updated = cursor.fetchone()


        create_audit_log(
    cursor,
    user["id"],
    "CORRECT_DELIVERY",
    "delivery",
    delivery_id,
    old_data=dict(delivery),
    new_data=dict(updated)
)


        conn.commit()

        return {
            "message":"Delivery corrected",
            "delivery":updated
        }


    finally:

        conn.close()