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
    Computes structural procurement-chain risk.

    IMPORTANT:
    This engine evaluates chain structure and dependency.
    It does NOT determine supply feasibility or timing feasibility.

    Feasibility belongs to the feasibility engine.
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

    # -------------------------------------------------
    # EXPLAIN STRUCTURAL CHAIN RISK
    # -------------------------------------------------

    reasons = []

    if hops == 0:
        reasons.append(
            "No allocation hops are currently recorded."
        )

    elif hops == 1:
        reasons.append(
            "Fulfillment currently depends on one supply source."
        )

    else:
        reasons.append(
            f"Fulfillment uses {hops} supply allocation points."
        )

    if transition_risk > 0.3:
        reasons.append(
            "Multiple source transitions increase dependency risk."
        )

    elif transition_risk > 0.1:
        reasons.append(
            "More than one supply source introduces moderate "
            "dependency complexity."
        )

    else:
        reasons.append(
            "The chain has low source-transition complexity."
        )

    # -------------------------------------------------
    # SYSTEM INTERPRETATION
    # -------------------------------------------------

    if risk_level == "LOW":

        interpretation = (
            "The fulfillment chain has low structural complexity "
            "and limited dependency risk."
        )

    elif risk_level == "MEDIUM":

        interpretation = (
            "The fulfillment chain has moderate structural "
            "dependency risk. Monitor source allocation and "
            "additional supply transitions."
        )

    else:

        interpretation = (
            "The fulfillment chain has high structural dependency "
            "risk because multiple allocation points or source "
            "transitions increase coordination complexity."
        )

    # -------------------------------------------------
    # DECISION LOG
    # -------------------------------------------------

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
                f"Calculated structural chain risk. "
                f"Hops={hops}, "
                f"transition_risk={transition_risk}, "
                f"score={score}, "
                f"risk_level={risk_level}."
            )
        )

    return {
        "integrity": integrity,
        "hops": hops,
        "transition_risk": transition_risk,
        "score": score,
        "risk_level": risk_level,
        "reasons": reasons,
        "interpretation": interpretation
    }