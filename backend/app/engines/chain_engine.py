from app.engines.feasibility_engine import (
    evaluate_commitment_feasibility
)

from app.engines.matching_engine import (
    build_fulfillment_plan
)

from app.engines.risk_engine import (
    calculate_chain_risk
)

from app.models.commitments import (
    get_commitment_by_id
)

from app.models.chains import (
    insert_chain_link
)

from app.logs.decision_logger import log_decision
def build_procurement_chain(cursor, commitment_id):

    commitment = get_commitment_by_id(
    cursor,
    commitment_id
)
    
    if not commitment:
        raise Exception("Commitment not found")
    # Rebuild is idempotent:
# one commitment should have exactly one current allocation chain.
    cursor.execute("""
    DELETE
    FROM procurement_chains
    WHERE commitment_id = %s
""", (commitment_id,))

    feasibility = evaluate_commitment_feasibility(cursor, commitment_id)

    plan = build_fulfillment_plan(cursor, commitment)

    allocations = plan["allocations"]

    total_allocated = 0
    position = 1

    # ALWAYS create chain (even partial)
    for allocation in allocations:
        insert_chain_link(
            cursor,
            commitment_id,
            allocation["source_id"],
            allocation["allocated_qty"],
            position
        )
        total_allocated += allocation["allocated_qty"]
        position += 1

    promised = commitment["promised_qty"]
    shortfall = max(0, promised - total_allocated)

    risk = calculate_chain_risk(cursor, commitment_id)

    # CLASSIFY RESULT
    if shortfall == 0:
        status = "FULLY_FULFILLED"
    elif total_allocated == 0:
        status = "FAILED"
    else:
        status = "PARTIALLY_FULFILLED"

    log_decision(
    cursor,
    actor_id=commitment["supplier_id"],
    decision_type="CHAIN_BUILT",
    reference_id=commitment_id,
    explanation=(
        f"Built procurement chain using "
        f"{len(allocations)} source(s). "
        f"Allocated {total_allocated} of "
        f"{promised} units."
    )
)
    if status != "FULLY_FULFILLED":

        log_decision(
        cursor,
        actor_id=commitment["supplier_id"],
        decision_type="CHAIN_FAILED",
        reference_id=commitment_id,
        explanation=(
            f"Allocated {total_allocated} of "
            f"{promised}. "
            f"Shortfall {shortfall}."
        )
    )
    return {
        "status": status,
        "commitment_id": commitment_id,
        "allocated_qty": total_allocated,
        "promised_qty": promised,
        "shortfall": shortfall,
        "feasibility": feasibility,
        "plan": plan,
        "risk": risk
    }