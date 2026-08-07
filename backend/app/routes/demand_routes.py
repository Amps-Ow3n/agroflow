from fastapi import APIRouter, Depends, HTTPException
from app.core.db import get_db
from app.core.dependencies import require_buyer
from app.core.dependencies import require_supplier
from app.core.exceptions import AgroFlowException
from app.engines.source_rules import owns_demand
from app.utils.audit import create_audit_log
from app.core.logger import log_error
from app.schemas.demand_schema import DemandCreate
from app.schemas.demand_schema import DemandUpdate

router = APIRouter(tags=["Demands"])

# SCHOOL creates demand
@router.post("/school/demand/create")
def create_demand(payload: DemandCreate, user=Depends(require_buyer)):
    if payload.delivery_start > payload.delivery_end:
        raise HTTPException(
        status_code=400,
        detail="Delivery start cannot be after delivery end"
    )

    conn, cursor = get_db()

    try:
        cursor.execute("""
SELECT id
FROM school_demands
WHERE school_id=%s
AND product=%s
AND location=%s
AND delivery_start=%s
AND delivery_end=%s
AND status='OPEN'
""",(
user["id"],
payload.product,
payload.location,
payload.delivery_start,
payload.delivery_end
))
        if cursor.fetchone():
            raise HTTPException(
        status_code=409,
        detail="Duplicate demand"
    )
    
        cursor.execute("""
            INSERT INTO school_demands (
    school_id,
    product,
    quantity,
    location,
    delivery_start,
    delivery_end
)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user["id"],
            payload.product,
            payload.quantity,
            payload.location,
            payload.delivery_start,
            payload.delivery_end
        ))

        demand = cursor.fetchone()

        create_audit_log(

    cursor,

    user["id"],

    "CREATE_DEMAND",

    "school_demand",

    demand["id"],

    new_data={
        "product":payload.product,
        "quantity":payload.quantity,
        "location":payload.location
    }

)

        conn.commit()

        return {
            "message": "Demand created",
            "demand_id": demand["id"]
        }

    except Exception as e:

        conn.rollback()

        log_error(
        message="Database transaction failed",
        user_id=user["id"],
        action="DATABASE_ERROR",
        entity="school_demand",
        extra={
            "exception": str(e)
        }
    )

        raise

    finally:
        conn.close()


# SCHOOL views own demands
@router.get("/school/demands")
def get_school_demands(
    limit: int = 20,
    offset: int = 0,
    user=Depends(require_buyer)):
    conn, cursor = get_db()

    try:
        cursor.execute("""
            SELECT *
            FROM school_demands
            WHERE school_id = %s
            ORDER BY created_at DESC
            LIMIT %s
OFFSET %s
        """, (user["id"], limit, offset))

        return cursor.fetchall()

    finally:
        conn.close()

# SUPPLIER sees open demands
@router.get("/supplier/open-demands")
def get_open_demands(
    limit: int = 20,
    offset: int = 0,
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    try:
        cursor.execute("""
            SELECT d.*, u.name AS school_name
            FROM school_demands d
            JOIN users u ON d.school_id = u.id
            WHERE d.status = 'OPEN'
            ORDER BY d.created_at DESC
            LIMIT %s
OFFSET %s
        """, (limit, offset))

        return cursor.fetchall()

    finally:
        conn.close()

@router.put("/school/demand/{demand_id}")
def update_demand(
    demand_id: int,
    payload: DemandUpdate,
    user=Depends(require_buyer)
):
    conn, cursor = get_db()

    if not owns_demand(
    cursor,
    demand_id,
    user["id"]
):
       raise HTTPException(
        status_code=404,
        detail="Demand not found."
    )
    try:

        # -------------------------
        # STEP 1
        # Check ownership + state
        # -------------------------
        cursor.execute("""
            SELECT status
            FROM school_demands
            WHERE id = %s
            AND school_id = %s
        """, (
            demand_id,
            user["id"]
        ))

        demand = cursor.fetchone()

        if not demand:

            raise AgroFlowException(
        "Demand not found",
        404,
        "DEMAND_NOT_FOUND"
    )

        if demand["status"]!="OPEN":

            raise AgroFlowException(
        "Only open demands can be edited",
        409,
        "DEMAND_LOCKED"
    )

        # -------------------------
        # STEP 2
        # Update
        # -------------------------
        if payload.delivery_start > payload.delivery_end:
            raise HTTPException(
        status_code=400,
        detail="Invalid delivery window"
    )
        cursor.execute("""
            UPDATE school_demands
            SET
                product = %s,
                quantity = %s,
                location = %s,
                delivery_start = %s,
                delivery_end = %s
            WHERE id = %s
            AND school_id = %s
        """, (
            payload.product,
            payload.quantity,
            payload.location,
            payload.delivery_start,
            payload.delivery_end,
            demand_id,
            user["id"]
        ))

        create_audit_log(

    cursor,

    user["id"],

    "UPDATE_DEMAND",

    "school_demand",

    demand_id,

    new_data=payload.model_dump(mode="json")

)
        conn.commit()

        return {
            "message": "Demand updated"
        }

    finally:
        conn.close()
        
@router.delete("/school/demand/{demand_id}")
def delete_demand(
    demand_id: int,
    user=Depends(require_buyer)
):
    conn, cursor = get_db()
    if not owns_demand(
    cursor,
    demand_id,
    user["id"]
):
       raise HTTPException(
        status_code=404,
        detail="Demand not found."
    )
    try:
        cursor.execute("""
            DELETE FROM school_demands
            WHERE id = %s
            AND school_id = %s
        """, (
            demand_id,
            user["id"]
        ))

        create_audit_log(

    cursor,

    user["id"],

    "DELETE_DEMAND",

    "school_demand",

    demand_id

)
        conn.commit()

        return {"message": "Demand deleted"}

    finally:
        conn.close()