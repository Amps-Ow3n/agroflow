from app.engines.support.chain_mapping_engine import (
    validate_chain_integrity
)

from app.engines.support.chain_risk_engine import (
    compute_chain_hops,
    compute_actor_transition_risk,
    compute_dependency_risk_score,
    classify_chain_risk
)


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
    
    print("Commitment:", commitment_id)
    print("Rows returned:", len(chain_rows))
    print(chain_rows)
    integrity = validate_chain_integrity(
        cursor,
        commitment_id
    )

    hops = compute_chain_hops(chain_rows)
    print("Computed hops:", hops)
    transition_risk = compute_actor_transition_risk(
        chain_rows
    )

    score = compute_dependency_risk_score(
        hops,
        transition_risk
    )

    risk_level = classify_chain_risk(score)

    return {
        "integrity": integrity,
        "hops": hops,
        "transition_risk": transition_risk,
        "score": score,
        "risk_level": risk_level
    }