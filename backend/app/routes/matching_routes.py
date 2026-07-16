from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import require_supplier
from app.core.db import get_db
from app.engines.matching_engine import build_fulfillment_plan
from app.models.chains import insert_chain_link

router = APIRouter()

@router.get("/matching/commitment/{commitment_id}")
def preview_match(
    commitment_id: int,
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT *
        FROM supplier_commitments
        WHERE id=%s
    """, (commitment_id,))
    commitment = cursor.fetchone()

    if not commitment:
        conn.close()
        raise HTTPException(404, "Commitment not found")

    plan = build_fulfillment_plan(cursor, commitment)

    conn.close()

    return plan


@router.post("/matching/commit/{commitment_id}")
def commit_match(
    commitment_id: int,
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT *
        FROM supplier_commitments
        WHERE id=%s
    """, (commitment_id,))
    commitment = cursor.fetchone()

    if not commitment:
        conn.close()
        raise HTTPException(404, "Commitment not found")

    plan = build_fulfillment_plan(cursor, commitment)

    position = 1

    for allocation in plan["allocations"]:
        insert_chain_link(
            cursor,
            commitment_id,
            allocation["source_id"],
            allocation["allocated_qty"],
            position
        )
        position += 1

    conn.commit()
    conn.close()

    return {
        "message": "Match committed",
        "allocations": plan["allocations"]
    }