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
from fastapi import HTTPException
from app.core.exceptions import AgroFlowException

from app.utils.audit import (
    create_audit_log
)
from app.core.logger import log_error
router = APIRouter()

@router.post("/source/register")
def register_source(
    payload: SupplySourceCreate,
    user=Depends(require_source_actor)
):
    # Prevent impossible availability window
    if payload.available_from > payload.available_to:
        raise HTTPException(
        status_code=400,
        detail="available_from cannot be after available_to"
    )
    conn, cursor = get_db()

    try:
        db_user = get_user_by_id(user["id"])
        cursor.execute("""
SELECT id
FROM supply_sources
WHERE actor_id=%s
AND product=%s
AND location=%s
AND available_from=%s
AND available_to=%s
AND is_archived=FALSE
""",(
    user["id"],
    payload.product,
    payload.location,
    payload.available_from,
    payload.available_to
))

        if cursor.fetchone():
            raise HTTPException(
        status_code=409,
        detail="Duplicate supply source"
    )
        payload.product = payload.product.strip().lower()

        source_id = create_supply_source(
    actor_id=user["id"],
    actor_type=payload.actor_type,  
    actor_name=db_user["name"],
    payload=payload
)

        create_audit_log(

    cursor,

    user["id"],

    "CREATE_SOURCE",

    "supply_source",

    source_id,

    old_data=None,

    new_data={
        "product": payload.product,
        "quantity": payload.qty_available,
        "location": payload.location
    }

)       
        conn.commit()

        return {
            "message": "Source registered",
            "source_id": source_id
        }

    except Exception as e:

        conn.rollback()

        log_error(
            message="Database transaction failed",
            user_id=user["id"],
            action="DATABASE_ERROR",
            entity="supply_source",
            extra={
                "exception": str(e)
            }
        )

        raise

    finally:
        conn.close()

@router.get("/source/my-sources")
def my_sources(
    limit: int = 20,
    offset: int = 0,
    user=Depends(require_source_actor)):
    return get_sources_by_actor(user["id"],
    limit,
    offset
    )

@router.put("/source/{source_id}")
def update_source(
    source_id: int,
    payload: SupplySourceCreate,
    user=Depends(require_source_actor)
):
    conn, cursor = get_db()

    if not owns_source(
    cursor,
    source_id,
    user["id"]
):
       raise HTTPException(
        status_code=404,
        detail="Supply source not found."
    )
    try:
        if not can_edit_source(
    cursor,
    source_id,
    user["id"]
):

           raise AgroFlowException(
        "You cannot edit this supply source",
        403,
        "SOURCE_EDIT_DENIED"
    )
        if (
            payload.available_from
            and
            payload.available_to
            and
            payload.available_from > payload.available_to
):
            raise HTTPException(
        status_code=400,
        detail="Invalid availability period"
    )
        cursor.execute("""
SELECT *
FROM supply_sources
WHERE id=%s
""",(source_id,))

        old_source = cursor.fetchone()
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

        create_audit_log(

    cursor,

    user["id"],

    "UPDATE_SOURCE",

    "supply_source",

    source_id,

    old_data=dict(old_source),

    new_data={
        "product": payload.product,
        "quantity": payload.qty_available,
        "location": payload.location
    }

)

        conn.commit()

        return {"message": "Source updated"}

    except Exception as e:

        conn.rollback()

        log_error(
            message="Database transaction failed",
            user_id=user["id"],
            action="DATABASE_ERROR",
            entity="supply_source",
            extra={
                "exception": str(e)
            }
        )

        raise

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

            raise AgroFlowException(
        "Supply source not found",
        404,
        "SOURCE_NOT_FOUND"
    )

        # ------------------------
        # Was this source ever used?
        # ------------------------
        if was_source_used(cursor, source_id):

            archive_source(
    cursor,
    source_id,
    user["id"]
)


            create_audit_log(

    cursor,

    user["id"],

    "ARCHIVE_SOURCE",

    "supply_source",

    source_id

)


            conn.commit()

            return {
    "message":"Supply source archived"
}

        # ------------------------
        # Never used -> hard delete
        # ------------------------
        cursor.execute("""
SELECT *
FROM supply_sources
WHERE id=%s
""",(source_id,))

        deleted_source = cursor.fetchone()
        cursor.execute("""
            DELETE FROM supply_sources
            WHERE id=%s
            AND actor_id=%s
        """, (
            source_id,
            user["id"]
        )) 
        create_audit_log(

    cursor,

    user["id"],

    "DELETE_SOURCE",

    "supply_source",

    source_id,

    old_data=dict(deleted_source)

)

        conn.commit()

        return {
    "message":"Supply source deleted"
}

    except Exception as e:

        conn.rollback()

        log_error(
            message="Database transaction failed",
            user_id=user["id"],
            action="DATABASE_ERROR",
            entity="supply_source",
            extra={
                "exception": str(e)
            }
        )

        raise

    finally:
        conn.close()

@router.get("/supplier/bottlenecks")
def supplier_bottlenecks(
    limit: int = 20,
    offset: int = 0,
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