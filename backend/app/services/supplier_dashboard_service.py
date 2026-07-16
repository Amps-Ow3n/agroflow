# backend/app/services/supplier_dashboard_service.py

from app.engines.support.reliability_engine import compute_supplier_reliability
from app.utils.status_mapper import (
    map_supplier_risk,
    VERIFIED_DELIVERY_STATUSES
)


def generate_supplier_dashboard(cursor, supplier_id: int):
    """
    Supplier performance dashboard.
    """

    # ACTIVE COMMITMENTS
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM supplier_commitments
        WHERE supplier_id = %s
        AND status NOT IN ('COMPLETED', 'FAILED')
    """, (supplier_id,))

    active_commitments = cursor.fetchone()["total"]

    # VERIFIED PERFORMANCE
    cursor.execute("""
        SELECT
            COALESCE(SUM(c.promised_qty), 0) AS total_promised,
            COALESCE(SUM(d.received_qty), 0) AS total_received
        FROM supplier_commitments c
        LEFT JOIN deliveries d
            ON d.commitment_id = c.id
        WHERE c.supplier_id = %s
        AND d.verification_status = ANY(%s)
    """, (supplier_id, VERIFIED_DELIVERY_STATUSES))

    perf = cursor.fetchone()

    total_promised = perf["total_promised"]
    total_received = perf["total_received"]

    fulfillment_progress = (
        round((total_received / total_promised) * 100, 2)
        if total_promised > 0 else 0
    )

    # BOTTLENECKS
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM supplier_commitments
        WHERE supplier_id = %s
        AND status IN (
            'SHORTFALL',
            'UNDERALLOCATED',
            'UNFULFILLABLE',
            'LATE_CHAIN',
            'FRAGILE_CHAIN'
        )
    """, (supplier_id,))

    bottlenecks = cursor.fetchone()["total"]

    # RELIABILITY
    reliability_score = compute_supplier_reliability(
        cursor,
        supplier_id
    )

    return {
        "active_commitments": active_commitments,
        "fulfillment_progress": fulfillment_progress,
        "chain_bottlenecks": bottlenecks,
        "reliability_score": reliability_score,
        "risk_level": map_supplier_risk(reliability_score)
    }