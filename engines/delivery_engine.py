from fastapi import HTTPException

from db import get_db
from engines.trust_engine import update_farmer_trust
from engines.risk_engine import recompute_all_risks
from utils import compute_confidence_score


def update_verification(
    cursor,
    delivery_id,
    payload,
    user_id,
    confidence_score
):

    cursor.execute("""
        UPDATE deliveries
        SET
            verification_status=%s,
            confidence_score=%s,
            verification_notes=%s,
            verified_by=%s,
            verified_at=CURRENT_TIMESTAMP
        WHERE id=%s
    """,(
        payload.verification_status,
        confidence_score,
        payload.verification_notes,
        user_id,
        delivery_id
    ))


def recompute_commitment_status(
    cursor,
    commitment_id,
    promised_qty
):

    cursor.execute("""
        SELECT COALESCE(
            SUM(delivered_qty),
            0
        ) AS total_verified
        FROM deliveries
        WHERE commitment_id=%s
        AND verification_status='VERIFIED'
    """,(commitment_id,))

    verified_total = (
        cursor.fetchone()["total_verified"]
    )

    verified_total=min(
        verified_total,
        promised_qty
    )

    if verified_total>=promised_qty:
        status="COMPLETED"

    elif verified_total>0:
        status="PARTIAL"

    else:
        status="PENDING"

    cursor.execute("""
        UPDATE commitments
        SET
            status=%s,
            last_updated=CURRENT_TIMESTAMP
        WHERE id=%s
    """,(
        status,
        commitment_id
    ))

    return status,verified_total


def verify_delivery_core(
    delivery_id,
    payload,
    user
):

    conn,cursor=get_db()

    try:

        allowed=[
            "VERIFIED",
            "PARTIAL",
            "REJECTED"
        ]

        if payload.verification_status not in allowed:

            raise HTTPException(
                status_code=400,
                detail="Invalid status"
            )

        cursor.execute("""
            SELECT
                d.id,
                c.id as commitment_id,
                c.farmer_id,
                c.promised_qty
            FROM deliveries d
            JOIN commitments c
            ON d.commitment_id=c.id
            WHERE d.id=%s
        """,(delivery_id,))

        row=cursor.fetchone()

        if not row:

            raise HTTPException(
                status_code=404,
                detail="Delivery not found"
            )

        confidence_score=compute_confidence_score(
            payload.verification_status
        )

        update_verification(
            cursor,
            delivery_id,
            payload,
            user["id"],
            confidence_score
        )

        commitment_status,verified_total=\
            recompute_commitment_status(
                cursor,
                row["commitment_id"],
                row["promised_qty"]
            )

        conn.commit()

        update_farmer_trust(
            row["farmer_id"],
            payload.verification_status
        )

        recompute_all_risks()

        return {

            "message":
            "Delivery verification updated",

            "delivery_id":
            delivery_id,

            "verification_status":
            payload.verification_status,

            "confidence_score":
            confidence_score,

            "commitment_status":
            commitment_status,

            "verified_total":
            verified_total
        }

    finally:
        conn.close()

# -----------------------------------
# Compute delivery status
# -----------------------------------
def compute_delivery_status(delivered, promised):
    """
    Compute delivery status based on TOTAL commitment fulfillment.
    This ensures consistency across:
    - Delivery table
    - Commitment table
    - Farmer dashboard
    - Admin dashboard
    """
    delivered = delivered or 0
    promised = promised or 0

    if promised <= 0:
        return "COMPLETED" if delivered > 0 else "FAILED"

    fulfillment_ratio = delivered / promised

    if fulfillment_ratio >= 1:
        return "COMPLETED"
    elif fulfillment_ratio >= 0.5:
        return "PARTIAL"
    elif fulfillment_ratio > 0:
        return "LOW"
    else:
        return "FAILED"

def compute_delivery_status_with_reason(delivered, promised):
    """
    Extends compute_delivery_status with human-readable explanation.
    DOES NOT break existing logic.
    """

    status = compute_delivery_status(delivered, promised)

    delivered = delivered or 0
    promised = promised or 0

    if promised <= 0:
        if delivered > 0:
            reason = f"Delivered {delivered} units without a formal commitment."
        else:
            reason = "No commitment and no delivery recorded."
        return status, reason

    shortfall = max(promised - delivered, 0)
    ratio = (delivered / promised) if promised > 0 else 0

    if status == "COMPLETED":
        reason = f"Delivered {delivered}/{promised} units (100% fulfillment)."

    elif status == "PARTIAL":
        reason = f"Delivered {delivered}/{promised} units ({round(ratio*100)}%). Shortfall: {shortfall} units."

    elif status == "LOW":
        reason = f"Low fulfillment: {delivered}/{promised} units ({round(ratio*100)}%). Major shortfall: {shortfall} units."

    elif status == "FAILED":
        reason = f"No delivery made. Expected {promised} units."

    else:
        reason = "Unknown delivery state."

    return status, reason

# ==================================================
# VERIFICATION CONFIDENCE ENGINE
# ==================================================
def compute_confidence_score(verification_status):

    if verification_status == "VERIFIED":
        return 1.0

    elif verification_status == "PARTIAL":
        return 0.5

    elif verification_status == "REJECTED":
        return 0.0

    return 0.0
