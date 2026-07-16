from fastapi import APIRouter, Depends
from app.core.db import get_db
from app.core.dependencies import require_supplier
from app.schemas.commitment_schema import SupplierCommitmentCreate
from app.engines.feasibility_engine import evaluate_commitment_feasibility
from app.engines.feasibility_engine import (
    evaluate_commitment_payload
)
from app.engines.source_rules import update_commitment_status
router = APIRouter(tags=["Commitments"])

# ==============================
# CREATE COMMITMENT
# ==============================
@router.post("/commitment/create")
def create_commitment(
    payload: SupplierCommitmentCreate,
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    try:

        feasibility = evaluate_commitment_payload(
            cursor,
            payload,
            user["id"]
        )

        if feasibility["status"] != "feasible":
            return {
                "message": "Commitment rejected",
                "feasibility": feasibility
            }

        cursor.execute("""
            INSERT INTO supplier_commitments(
                supplier_id,
                school_id,
                product,
                promised_qty,
                delivery_start,
                delivery_end
            )
            VALUES(%s,%s,%s,%s,%s,%s)
            RETURNING id
        """,(
            user["id"],
            payload.school_id,
            payload.product,
            payload.promised_qty,
            payload.delivery_start,
            payload.delivery_end
        ))

        commitment = cursor.fetchone()

        conn.commit()

        return {
            "message":"Commitment created",
            "commitment_id":commitment["id"],
            "feasibility":feasibility
        }

    finally:
        conn.close()
# ==============================
# MY COMMITMENTS
# ==============================
@router.get("/supplier/commitments")
def get_supplier_commitments(
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    try:
        cursor.execute("""
         SELECT
    sc.id,
    sc.product,
    sc.promised_qty,
    sc.delivery_start,
    sc.delivery_end,
    sc.created_at,

    sc.school_id,
    u.name AS school_name,

   CASE

WHEN EXISTS(
SELECT 1
FROM deliveries d
WHERE d.commitment_id=sc.id
AND d.verification_status='VERIFIED'
)

THEN 'COMPLETED'


WHEN EXISTS(
SELECT 1
FROM deliveries d
WHERE d.commitment_id=sc.id
)

THEN 'DELIVERED'

ELSE 'PENDING'

END AS status

FROM supplier_commitments sc

JOIN users u
ON u.id = sc.school_id

WHERE sc.supplier_id=%s

ORDER BY sc.created_at DESC;
        """, (user["id"],))

        return cursor.fetchall()

    finally:
        conn.close()
        
@router.patch("/commitment/{id}/status")
def change_commitment_status(
    id: int,
    payload: dict,
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    try:
        update_commitment_status(
            cursor,
            id,
            payload["status"]
        )

        conn.commit()

        return {"message": "Status updated"}

    finally:
        conn.close()