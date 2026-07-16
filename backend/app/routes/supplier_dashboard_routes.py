# core/routes/supplier_dashboard_routes.py
from fastapi import APIRouter, Depends
from app.core.db import get_db
from app.core.dependencies import require_supplier
from app.engines.support.reliability_engine import compute_supplier_reliability

router = APIRouter(prefix="/dashboard/supplier", tags=["Supplier Dashboard"])


@router.get("/overview")
def supplier_overview(user=Depends(require_supplier)):
    conn, cursor = get_db()

    try:
        supplier_id = user["id"]

        # Active commitments
        cursor.execute("""
    SELECT COUNT(*) AS total
    FROM supplier_commitments
    WHERE supplier_id = %s
    AND delivery_end >= CURRENT_DATE
""", (supplier_id,))
        active_commitments = cursor.fetchone()["total"]

        # Fulfillment progress
        cursor.execute("""
            SELECT
                COALESCE(SUM(c.promised_qty), 0) AS promised,
                COALESCE(SUM(d.received_qty), 0) AS delivered
            FROM supplier_commitments c
            LEFT JOIN deliveries d
            ON d.commitment_id = c.id
            WHERE c.supplier_id = %s
        """, (supplier_id,))

        result = cursor.fetchone()

        promised = result["promised"]
        delivered = result["delivered"]

        fulfillment_progress = (
            round((delivered / promised) * 100, 2)
            if promised > 0 else 0
        )

        # Bottlenecks
        cursor.execute("""
    SELECT COUNT(*) AS total
    FROM deliveries
    WHERE verification_status IN ('SHORTFALL', 'UNDERALLOCATED')
    AND commitment_id IN (
        SELECT id FROM supplier_commitments
        WHERE supplier_id = %s
    )
""", (supplier_id,))
        chain_bottlenecks = cursor.fetchone()["total"]

        reliability_score = compute_supplier_reliability(
            cursor,
            supplier_id
        )

        return {
            "active_commitments": active_commitments,
            "fulfillment_progress": fulfillment_progress,
            "chain_bottlenecks": chain_bottlenecks,
            "reliability_score": reliability_score
        }

    finally:
        conn.close()