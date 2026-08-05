from app.engines.support.chain_mapping_engine import (
    validate_chain_integrity
)

from app.engines.support.chain_risk_engine import (
    compute_chain_hops,
    compute_actor_transition_risk,
    compute_dependency_risk_score,
    classify_chain_risk
)
from app.logs.decision_logger import log_decision
def calculate_chain_risk(cursor, commitment_id):
    """
    Core risk contract.

    Computes overall chain risk.
    """
    cursor.execute("""
        SELECT *
        FROM procurement_chains
        WHERE commitment_id = %s
        ORDER BY chain_position ASC
    """, (commitment_id,))

    chain_rows = cursor.fetchall()
    
    integrity = validate_chain_integrity(
        cursor,
        commitment_id
    )

    hops = compute_chain_hops(chain_rows)
    transition_risk = compute_actor_transition_risk(
        chain_rows
    )

    score = compute_dependency_risk_score(
        hops,
        transition_risk
    )

    risk_level = classify_chain_risk(score)

    cursor.execute("""
    SELECT supplier_id
    FROM supplier_commitments
    WHERE id = %s
""", (commitment_id,))

    commitment = cursor.fetchone()

    if commitment:

        log_decision(
        cursor,
        actor_id=commitment["supplier_id"],
        decision_type="CHAIN_RISK",
        reference_id=commitment_id,
        explanation=(
            f"Calculated chain risk "
            f"score {score}. "
            f"Risk level: {risk_level}."
        )
    )
    return {
        "integrity": integrity,
        "hops": hops,
        "transition_risk": transition_risk,
        "score": score,
        "risk_level": risk_level
    }