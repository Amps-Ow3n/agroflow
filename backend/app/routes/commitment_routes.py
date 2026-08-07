from fastapi import APIRouter, Depends, HTTPException
from app.core.db import get_db
from app.core.dependencies import require_supplier
from app.schemas.commitment_schema import SupplierCommitmentCreate
from app.engines.feasibility_engine import evaluate_commitment_feasibility
from app.engines.feasibility_engine import (
    evaluate_commitment_payload
)
from app.engines.source_rules import (
    update_commitment_status,
    owns_commitment
)
from app.utils.audit import create_audit_log
from app.core.logger import log_error
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
SELECT id
FROM supply_sources
WHERE id=%s
AND actor_id=%s
AND is_archived=FALSE
""",(
    payload.source_id,
    user["id"]
))

        if cursor.fetchone() is None:
            raise HTTPException(
    status_code=404,
    detail="Resource not found."
)
        cursor.execute("""
SELECT id
FROM supplier_commitments
WHERE supplier_id=%s
AND demand_id=%s
AND status!='CANCELLED'
""",(
    user["id"],
    payload.demand_id
))

        if cursor.fetchone():
            raise HTTPException(
        status_code=409,
        detail="Commitment already exists"
    )
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


        create_audit_log(

    cursor,

    user["id"],

    "CREATE_COMMITMENT",

    "supplier_commitment",

    commitment["id"],

        new_data={
        "product":payload.product,
        "quantity":payload.promised_qty,
        "school_id":payload.school_id
    }

)


        conn.commit()

        return {
            "message":"Commitment created",
            "commitment_id":commitment["id"],
            "feasibility":feasibility
        }

    except Exception as e:

        conn.rollback()

        log_error(
            message="Database transaction failed",
            user_id=user["id"],
            action="DATABASE_ERROR",
            entity="supplier_commitment",
            extra={
                "exception": str(e)
            }
        )

        raise

    finally:
        conn.close()
# ==============================
# MY COMMITMENTS
# ==============================
@router.get("/supplier/commitments")
def get_supplier_commitments(
    limit: int = 20,
    offset: int = 0,
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

ORDER BY sc.created_at DESC
LIMIT %s
OFFSET %s
        """, (user["id"], limit, offset))

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
    if not owns_commitment(
    cursor,
    id,
    user["id"]
):
       raise HTTPException(
        status_code=404,
        detail="Commitment not found."
    )
    try:
        update_commitment_status(
    cursor,
    id,
    payload["status"]
)


        create_audit_log(

    cursor,

    user["id"],

    "CHANGE_COMMITMENT_STATUS",

    "supplier_commitment",

    id,

    new_data={
        "status":payload["status"]
    }

)


        conn.commit()

        return {"message": "Status updated"}

    except Exception as e:

        conn.rollback()

        log_error(
            message="Database transaction failed",
            user_id=user["id"],
            action="DATABASE_ERROR",
            entity="supplier_commitment",
            extra={
                "exception": str(e)
            }
        )

        raise

    finally:
        conn.close()