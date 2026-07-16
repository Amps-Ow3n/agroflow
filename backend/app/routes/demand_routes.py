from fastapi import APIRouter, Depends
from app.core.db import get_db
from app.core.dependencies import require_buyer

router = APIRouter(tags=["Demands"])

# SCHOOL creates demand
@router.post("/school/demand/create")
def create_demand(payload: dict, user=Depends(require_buyer)):
    conn, cursor = get_db()

    try:
        cursor.execute("""
            INSERT INTO school_demands (
                school_id,
                product,
                quantity,
                delivery_start,
                delivery_end
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user["id"],
            payload["product"],
            payload["quantity"],
            payload["delivery_start"],
            payload["delivery_end"]
        ))

        demand = cursor.fetchone()
        conn.commit()

        return {
            "message": "Demand created",
            "demand_id": demand["id"]
        }

    finally:
        conn.close()


# SCHOOL views own demands
@router.get("/school/demands")
def get_school_demands(user=Depends(require_buyer)):
    conn, cursor = get_db()

    try:
        cursor.execute("""
            SELECT *
            FROM school_demands
            WHERE school_id = %s
            ORDER BY created_at DESC
        """, (user["id"],))

        return cursor.fetchall()

    finally:
        conn.close()

# SUPPLIER sees open demands
@router.get("/supplier/open-demands")
def get_open_demands():
    conn, cursor = get_db()

    try:
        cursor.execute("""
            SELECT d.*, u.name AS school_name
            FROM school_demands d
            JOIN users u ON d.school_id = u.id
            WHERE d.status = 'OPEN'
            ORDER BY d.created_at DESC
        """)

        return cursor.fetchall()

    finally:
        conn.close()

@router.put("/school/demand/{demand_id}")
def update_demand(
    demand_id: int,
    payload: dict,
    user=Depends(require_buyer)
):
    conn, cursor = get_db()

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
            return {
                "message": "Demand not found"
            }

        if demand["status"] != "OPEN":
            return {
                "message": "Only OPEN demands can be edited"
            }

        # -------------------------
        # STEP 2
        # Update
        # -------------------------
        cursor.execute("""
            UPDATE school_demands
            SET
                product = %s,
                quantity = %s,
                delivery_start = %s,
                delivery_end = %s
            WHERE id = %s
            AND school_id = %s
        """, (
            payload["product"],
            payload["quantity"],
            payload["delivery_start"],
            payload["delivery_end"],
            demand_id,
            user["id"]
        ))

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

    try:
        cursor.execute("""
            DELETE FROM school_demands
            WHERE id = %s
            AND school_id = %s
        """, (
            demand_id,
            user["id"]
        ))

        conn.commit()

        return {"message": "Demand deleted"}

    finally:
        conn.close()