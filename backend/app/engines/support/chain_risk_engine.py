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
    hops = hops or 0
    transition_risk = transition_risk or 0

    return round(
    (hops * 10) +
    (transition_risk * 20),
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
    transition_risk
):
    """
    Produces explainable chain-risk output.
    """

    score = compute_dependency_risk_score(
        hops,
        transition_risk
    )

    risk_level = classify_chain_risk(score)

    reasons = []

    if hops > 2:
        reasons.append(
            "Multiple supply allocation points increase chain complexity."
        )

    if transition_risk > 0.3:
        reasons.append(
            "Several source transitions increase dependency risk."
        )

    if not reasons:
        reasons.append(
            "No significant structural risk detected."
        )

    return {

        "score": score,

        "risk_level": risk_level,

        "reasons": reasons

    }