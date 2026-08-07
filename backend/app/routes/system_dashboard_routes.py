from fastapi import APIRouter, Depends
from app.core.db import get_db
from app.core.dependencies import require_admin
from app.engines.support.reliability_engine import compute_supplier_reliability

router = APIRouter(prefix="/dashboard/system", tags=["System Dashboard"])

@router.get("/overview")
def system_overview(user=Depends(require_admin)):
    conn, cursor = get_db()

    try:
        # Chain failures = verified bad reality
        cursor.execute("""
    SELECT COUNT(*) AS total
    FROM deliveries
    WHERE
        verification_status = 'REJECTED'
        OR quality_status = 'FAILED'
        OR delay_status = 'DELAYED'
""")
        chain_failures = cursor.fetchone()["total"]

        # Total supply
        cursor.execute("""
            SELECT COALESCE(SUM(qty_available), 0) AS total
            FROM supply_sources
        """)
        total_supply = cursor.fetchone()["total"]

        # Total allocated
        cursor.execute("""
            SELECT COALESCE(SUM(allocated_qty), 0) AS total
            FROM procurement_chains
        """)
        total_allocated = cursor.fetchone()["total"]

        system_utilization = (
            round((total_allocated / total_supply) * 100, 2)
            if total_supply > 0 else 0
        )

        # Bottlenecks
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM (
                SELECT
                    s.id,
                    COALESCE(SUM(pc.allocated_qty), 0) AS allocated,
                    s.qty_available
                FROM supply_sources s
                LEFT JOIN procurement_chains pc
                ON pc.source_id = s.id
                GROUP BY s.id
            ) x
            WHERE allocated >= qty_available
        """)
        source_bottlenecks = cursor.fetchone()["total"]

        return {
            "chain_failures": chain_failures,
            "system_utilization": system_utilization,
            "source_bottlenecks": source_bottlenecks
        }

    finally:
        conn.close()

@router.get("/commitment/{commitment_id}")
def get_commitment_detail(commitment_id: int, user=Depends(require_admin)):
    conn, cursor = get_db()

    try:
        # 1. Commitment core
        cursor.execute("""
            SELECT *
            FROM supplier_commitments
            WHERE id = %s
        """, (commitment_id,))
        commitment = cursor.fetchone()

        if not commitment:
            return {"error": "Commitment not found"}

        # 2. Supplier + School
        cursor.execute("""
            SELECT id, name, email, role
            FROM users
            WHERE id = %s
        """, (commitment["supplier_id"],))
        supplier = cursor.fetchone()

        cursor.execute("""
            SELECT id, name, email, role
            FROM users
            WHERE id = %s
        """, (commitment["school_id"],))
        school = cursor.fetchone()

        # 3. Deliveries (VERIFIED ONLY = truth layer)
        cursor.execute("""
           SELECT *
FROM deliveries
WHERE commitment_id = %s
ORDER BY created_at DESC
        """, (commitment_id,))
        deliveries = cursor.fetchall()

        # 4. Reliability score (single source of truth)
        reliability = compute_supplier_reliability(
            cursor,
            commitment["supplier_id"]
        )

        return {
            "commitment": commitment,
            "supplier": supplier,
            "school": school,
            "deliveries": deliveries,
            "reliability_score": reliability
        }

    finally:
        conn.close()

@router.get("/chain/{commitment_id}")
def get_chain_trace(commitment_id: int, user=Depends(require_admin)):
    conn, cursor = get_db()

    try:
        enriched = []

        cursor.execute("""
SELECT
    pc.*,
    s.*,
    COALESCE(a.allocated,0) AS allocated
FROM procurement_chains pc
         
JOIN supply_sources s
ON pc.source_id=s.id
        
LEFT JOIN (
         
    SELECT
        source_id,
        SUM(allocated_qty) AS allocated
    FROM procurement_chains
    GROUP BY source_id

) a
         
ON a.source_id=s.id

WHERE pc.commitment_id=%s

ORDER BY pc.chain_position
""",(commitment_id,))

        rows = cursor.fetchall()

        if not rows:
            return {
        "commitment_id": commitment_id,
        "chain_trace": []
    }
        enriched = []

        for row in rows:

            utilization = (
                round(
                    (row["allocated"] / row["qty_available"]) * 100,
                    2
                )
                if row["qty_available"] > 0
                else 0
            )

            enriched.append({

                "chain": {
                    "id": row["id"],
                    "allocated_qty": row["allocated_qty"],
                    "chain_position": row["chain_position"]
                },

                "source": row,

                "utilization": utilization

            })

        return {
            "commitment_id": commitment_id,
            "chain_trace": enriched
        }

    finally:
        conn.close()
    
@router.get("/failure-map")
def system_failure_map(
    limit: int = 20,
    offset: int = 0,
    user=Depends(require_admin)):
    conn, cursor = get_db()

    try:
        cursor.execute("""
    SELECT
        d.id AS delivery_id,
        d.commitment_id,
        d.verification_status,
        d.quality_status,
        d.delay_status,
        s.name AS supplier_name,
        sch.name AS school_name
    FROM deliveries d
    JOIN supplier_commitments sc
        ON d.commitment_id = sc.id
    JOIN users s
        ON sc.supplier_id = s.id
    JOIN users sch
        ON sc.school_id = sch.id
    WHERE
        d.verification_status = 'REJECTED'
        OR d.quality_status = 'FAILED'
        OR d.delay_status = 'DELAYED'
    ORDER BY d.id DESC
    LIMIT %s
    OFFSET %s
""", (limit, offset))

        rows = cursor.fetchall()
        results = []

        for row in rows:

            if row["verification_status"] == "REJECTED":
                failure_type = "REJECTED"
                severity = "HIGH"

            elif row["quality_status"] == "FAILED":
                failure_type = "QUALITY_FAILED"
                severity = "MEDIUM"

            elif row["delay_status"] == "DELAYED":
                failure_type = "DELAYED"
                severity = "LOW"

            else:
                failure_type = "UNKNOWN"
                severity = "UNKNOWN"

            results.append({
    "delivery_id": row["delivery_id"],
    "commitment_id": row["commitment_id"],
    "failure_type": failure_type,
    "severity": severity,
    "supplier": row["supplier_name"],
    "school": row["school_name"]
})

        return results

    finally:
        conn.close()
                
@router.get("/bottlenecks")
def system_bottlenecks(
    limit: int = 20,
    offset: int = 0,
    user=Depends(require_admin)):
    conn, cursor = get_db()

    try:
        cursor.execute("""
    SELECT
        s.id,
        s.actor_name,
        s.product,
        s.qty_available,
        COALESCE(SUM(pc.allocated_qty), 0) AS allocated
    FROM supply_sources s
    LEFT JOIN procurement_chains pc
        ON pc.source_id = s.id
    GROUP BY
        s.id,
        s.actor_name,
        s.product,
        s.qty_available
    ORDER BY s.id DESC
    LIMIT %s
    OFFSET %s
""", (limit, offset))

        rows = cursor.fetchall()

        results = []

        for row in rows:
            utilization = (
                round((row["allocated"] / row["qty_available"]) * 100, 2)
                if row["qty_available"] > 0 else 0
            )

            results.append({

    "source_id": row["id"],

    "actor_name": row["actor_name"],

    "product": row["product"],

    "available": row["qty_available"],

    "allocated": row["allocated"],

    "utilization": utilization

})

        return results

    finally:
        conn.close()

@router.get("/truth-ledger")
def get_truth_ledger(
    limit: int = 20,
    offset: int = 0,
    user=Depends(require_admin)
):

    conn,cursor=get_db()

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
    ORDER BY d.created_at DESC
    LIMIT %s
    OFFSET %s
""", (limit, offset))

        return cursor.fetchall()

    finally:
        conn.close()