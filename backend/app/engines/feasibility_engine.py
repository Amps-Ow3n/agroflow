from app.engines.support.quantity_feasibility_engine import (
    compute_total_available,
    evaluate_feasibility,
    compute_allocated_elsewhere
)

from app.engines.support.time_feasibility_engine import (
    evaluate_time_feasibility
)
from app.logs.decision_logger import log_decision
# ==========================
# POST-SAVE CHECK (existing commitments)
# ==========================
def evaluate_commitment_feasibility(cursor, commitment_id):

    cursor.execute("""
        SELECT *
        FROM supplier_commitments
        WHERE id = %s
    """, (commitment_id,))

    commitment = cursor.fetchone()

    if not commitment:
        raise Exception("Commitment not found")


    total_available = compute_total_available(
        cursor,
        commitment["supplier_id"],
        commitment["product"]
    )


    allocated_elsewhere = compute_allocated_elsewhere(
        cursor,
        commitment["supplier_id"],
        commitment["product"]
    )

    quantity = evaluate_feasibility(
    commitment["promised_qty"],
    total_available,
    allocated_elsewhere
)

    log_decision(

    cursor,

    actor_id=commitment["supplier_id"],

    decision_type="FEASIBILITY_CHECK",

    reference_id=commitment_id,

    explanation=(
        f"Available={total_available}, "
        f"Allocated={allocated_elsewhere}, "
        f"Requested={commitment['promised_qty']}, "
        f"Status={quantity['status']}."
    )

)
    return {
        "quantity": quantity,
        "status": quantity["status"]
    }
# ==========================
# PRE-SAVE CHECK (payload validation)
# ==========================
def evaluate_commitment_payload(
    cursor,
    payload,
    supplier_id
):

    normalized_product = payload.product.lower()


    total_available = compute_total_available(
        cursor,
        supplier_id,
        normalized_product
    )

    allocated_elsewhere = compute_allocated_elsewhere(
    cursor,
    supplier_id,
    payload.product
)

    quantity = evaluate_feasibility(
        payload.promised_qty,
        total_available,
        allocated_elsewhere
    )


    quantity["requested_qty"] = payload.promised_qty

    cursor.execute("""
        SELECT *
        FROM supply_sources
        WHERE actor_id = %s
        AND LOWER(product) = %s
        AND is_archived = FALSE
    """,
    (
        supplier_id,
        normalized_product
    ))

    sources = cursor.fetchall()

    timing = evaluate_time_feasibility(
        sources,
        payload.delivery_start,
        payload.delivery_end,
        payload.promised_qty
    )

    decision_type = (
    "COMMITMENT_ACCEPTED"
    if quantity["feasible"]
    and timing["time_feasible"]
    else "COMMITMENT_REJECTED"
)

    log_decision(

    cursor,

    actor_id=supplier_id,

    decision_type=decision_type,

    reference_id=payload.source_id,

    explanation=(
        f"Available={total_available}, "
        f"Allocated={allocated_elsewhere}, "
        f"Requested={payload.promised_qty}, "
        f"Time feasible={timing['time_feasible']}."
    )

)

    return {

    "quantity": quantity,

    "timing": timing,

    "status": (
        "feasible"
        if quantity["feasible"]
        and timing["time_feasible"]
        else "infeasible"
    )

}