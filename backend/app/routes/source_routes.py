from fastapi import APIRouter, Depends
from app.core.dependencies import require_source_actor
from app.schemas.supply_schema import SupplySourceCreate
from app.models.supply import (
    create_supply_source,
    get_sources_by_actor
)
from app.engines.source_rules import (
    can_edit_source,
    owns_source,
    was_source_used,
    archive_source
)
from app.models.users import get_user_by_id
from app.core.db import get_db
from app.core.dependencies import require_supplier

router = APIRouter()

@router.post("/source/register")
def register_source(
    payload: SupplySourceCreate,
    user=Depends(require_source_actor)
):
    conn, cursor = get_db()

    try:
        db_user = get_user_by_id(user["id"])

        source_id = create_supply_source(
            actor_id=user["id"],
            actor_type=payload.actor_type,   # IMPORTANT FIX (explained below)
            actor_name=db_user["name"],
            payload=payload
        )

        return {
            "message": "Source registered",
            "source_id": source_id
        }

    finally:
        conn.close()

@router.get("/source/my-sources")
def my_sources(user=Depends(require_source_actor)):
    return get_sources_by_actor(user["id"])

@router.put("/source/{source_id}")
def update_source(
    source_id: int,
    payload: SupplySourceCreate,
    user=Depends(require_source_actor)
):
    conn, cursor = get_db()

    try:
        if not can_edit_source(cursor, source_id, user["id"]):
            return {"message": "Edit not allowed"}

        cursor.execute("""
            UPDATE supply_sources
            SET product=%s,
                qty_available=%s,
                location=%s,
                available_from=%s,
                available_to=%s
            WHERE id=%s AND actor_id=%s
        """, (
            payload.product,
            payload.qty_available,
            payload.location,
            payload.available_from,
            payload.available_to,
            source_id,
            user["id"]
        ))

        conn.commit()

        return {"message": "Source updated"}

    finally:
        conn.close()

@router.delete("/source/{source_id}")
def delete_source(
    source_id: int,
    user=Depends(require_source_actor)
):
    conn, cursor = get_db()

    try:

        if not owns_source(
            cursor,
            source_id,
            user["id"]
        ):
            return {
                "message": "Source not found"
            }

        # ------------------------
        # Was this source ever used?
        # ------------------------
        if was_source_used(cursor, source_id):

            archive_source(
                cursor,
                source_id,
                user["id"]
            )

            conn.commit()

            return {
                "message": "Source archived"
            }

        # ------------------------
        # Never used -> hard delete
        # ------------------------
        cursor.execute("""
            DELETE FROM supply_sources
            WHERE id=%s
            AND actor_id=%s
        """, (
            source_id,
            user["id"]
        ))

        conn.commit()

        return {
            "message": "Source deleted"
        }

    finally:
        conn.close()

@router.get("/supplier/bottlenecks")
def supplier_bottlenecks(
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    try:

        cursor.execute("""
            SELECT
                s.id,
                s.actor_name,
                s.product,
                s.qty_available,

                COALESCE(
                    SUM(pc.allocated_qty),
                    0
                ) AS allocated

            FROM supply_sources s

            LEFT JOIN procurement_chains pc
            ON pc.source_id = s.id

            WHERE s.actor_id = %s

            GROUP BY
                s.id,
                s.actor_name,
                s.product,
                s.qty_available

            ORDER BY s.product
        """, (user["id"],))

        rows = cursor.fetchall()

        results = []

        for row in rows:

            available = row["qty_available"]
            allocated = row["allocated"]

            utilization = (
                round((allocated / available) * 100, 2)
                if available > 0
                else 0
            )

            results.append({
                "source_id": row["id"],
                "actor_name": row["actor_name"],
                "product": row["product"],
                "available": available,
                "allocated": allocated,
                "utilization": utilization
            })

        return results

    finally:
        conn.close()