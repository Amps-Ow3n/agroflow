def compute_chain_hops(chain_rows):
    """
    MVP definition:
    One procurement chain row = one allocation hop.
    """

    return len(chain_rows or [])

def compute_actor_transition_risk(chain_rows):

    unique_sources = len(
        set(
            r["source_id"]
            for r in chain_rows
        )
    )

    if unique_sources <= 1:
        return 0.1

    if unique_sources <=3:
        return 0.3

    return 0.5

def compute_dependency_risk_score(
    hops,
    transition_risk
):
    """
    Structural dependency risk.

    A single-source, single-hop chain should not
    automatically become medium risk simply because
    it contains one allocation.

    Hops represent complexity.
    Transition risk represents dependency between
    different actors/sources.
    """

    hops = hops or 0
    transition_risk = transition_risk or 0

    if hops <= 1:
        hop_score = 0
    elif hops <= 3:
        hop_score = 10
    else:
        hop_score = 20

    transition_score = transition_risk * 20

    return round(
        hop_score + transition_score,
        2
    )

def classify_chain_risk(score):

    if score < 10:
        return "LOW"

    if score < 25:
        return "MEDIUM"

    return "HIGH"

def compute_chain_risk_summary(
    hops,
    transition_risk,
    promised_qty=None,
    allocated_qty=None,
    shortfall=None
):
    """
    Produces explainable chain-risk output.

    Risk interpretation distinguishes:
    - structural complexity
    - supply shortfall
    - dependency risk
    """

    score = compute_dependency_risk_score(
        hops,
        transition_risk
    )

    risk_level = classify_chain_risk(score)

    reasons = []

    # =====================================================
    # FULFILLMENT RISK
    # =====================================================

    if shortfall is not None and shortfall > 0:

        reasons.append(
            f"Procurement chain has a shortfall of "
            f"{shortfall} units."
        )

    # =====================================================
    # STRUCTURAL RISK
    # =====================================================

    if hops > 3:

        reasons.append(
            "Multiple allocation points increase "
            "chain complexity."
        )

    if transition_risk > 0.3:

        reasons.append(
            "Several source transitions increase "
            "dependency risk."
        )

    # =====================================================
    # POSITIVE INTERPRETATION
    # =====================================================

    if not reasons:

        if (
            shortfall is not None
            and shortfall == 0
        ):

            reasons.append(
                "Commitment is fully allocated with "
                "no significant structural chain risk."
            )

        else:

            reasons.append(
                "No significant structural risk detected."
            )

    return {
        "score": score,
        "risk_level": risk_level,
        "reasons": reasons
    }