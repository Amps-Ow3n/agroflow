# backend/app/services/system_dashboard_service.py

from app.utils.status_mapper import CHAIN_FAILURE_STATUSES


def generate_system_dashboard(cursor):
    """
    System-wide procurement intelligence dashboard.
    """

    # TOTAL SUPPLY
    cursor.execute("""
        SELECT COALESCE(SUM(qty_available), 0) AS total_supply
        FROM supply_sources
    """)
    total_supply = cursor.fetchone()["total_supply"]

    # TOTAL COMMITTED
    cursor.execute("""
        SELECT COALESCE(SUM(promised_qty), 0) AS total_committed
        FROM supplier_commitments
    """)
    total_committed = cursor.fetchone()["total_committed"]

    # CHAIN FAILURES
    cursor.execute("""
        SELECT COUNT(*) AS failures
        FROM supplier_commitments
        WHERE status = ANY(%s)
    """, (CHAIN_FAILURE_STATUSES,))

    chain_failures = cursor.fetchone()["failures"]

    # SOURCE UTILIZATION
    cursor.execute("""
        SELECT
            s.id,
            s.qty_available,
            COALESCE(SUM(pc.allocated_qty), 0) AS allocated
        FROM supply_sources s
        LEFT JOIN procurement_chains pc
            ON pc.source_id = s.id
        GROUP BY s.id
    """)

    rows = cursor.fetchall()

    bottlenecks = []
    total_allocated = 0

    for row in rows:
        allocated = row["allocated"]
        available = row["qty_available"]

        total_allocated += allocated

        utilization = (
            (allocated / available) * 100
            if available > 0 else 0
        )

        if utilization >= 80:
            bottlenecks.append({
                "source_id": row["id"],
                "utilization": round(utilization, 2)
            })

    system_utilization = (
        round((total_allocated / total_supply) * 100, 2)
        if total_supply > 0 else 0
    )

    overcommitment = max(
        total_committed - total_supply,
        0
    )

    return {
        "total_supply": total_supply,
        "total_committed": total_committed,
        "chain_failures": chain_failures,
        "overcommitment": overcommitment,
        "source_bottlenecks": bottlenecks,
        "system_utilization": system_utilization
    }