# backend/app/services/school_dashboard_service.py

from app.engines.support.reliability_engine import compute_supplier_reliability
from app.utils.status_mapper import VERIFIED_DELIVERY_STATUSES


def generate_school_dashboard(cursor, school_id: int):
    """
    School truth dashboard.
    Tracks verified procurement reality.
    """

    # -----------------------------------
    # EXPECTED
    # -----------------------------------
    cursor.execute("""
        SELECT COALESCE(SUM(promised_qty), 0) AS total
        FROM supplier_commitments
        WHERE school_id = %s
    """, (school_id,))

    expected_total = cursor.fetchone()["total"]

    # -----------------------------------
    # RECEIVED (VERIFIED ONLY)
    # -----------------------------------
    cursor.execute("""
        SELECT COALESCE(SUM(d.received_qty), 0) AS total
        FROM deliveries d
        JOIN supplier_commitments c
            ON d.commitment_id = c.id
        WHERE c.school_id = %s
        AND d.verification_status = ANY(%s)
    """, (school_id, VERIFIED_DELIVERY_STATUSES))

    received_total = cursor.fetchone()["total"]

    # -----------------------------------
    # DELAYS
    # -----------------------------------
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM deliveries d
        JOIN supplier_commitments c
            ON d.commitment_id = c.id
        WHERE c.school_id = %s
        AND d.delay_status = 'DELAYED'
    """, (school_id,))

    delay_count = cursor.fetchone()["total"]

    # -----------------------------------
    # QUALITY FAILURES
    # -----------------------------------
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM deliveries d
        JOIN supplier_commitments c
            ON d.commitment_id = c.id
        WHERE c.school_id = %s
        AND d.quality_status = 'FAILED'
    """, (school_id,))

    quality_failures = cursor.fetchone()["total"]

    # -----------------------------------
    # SUPPLIER TRUST
    # -----------------------------------
    cursor.execute("""
        SELECT DISTINCT supplier_id
        FROM supplier_commitments
        WHERE school_id = %s
    """, (school_id,))

    suppliers = cursor.fetchall()

    scores = [
        compute_supplier_reliability(cursor, s["supplier_id"])
        for s in suppliers
    ]

    supplier_trust_avg = (
        round(sum(scores) / len(scores), 2)
        if scores else 0
    )

    return {
        "expected_total": expected_total,
        "received_total": received_total,
        "delay_count": delay_count,
        "quality_failures": quality_failures,
        "supplier_trust_avg": supplier_trust_avg
    }