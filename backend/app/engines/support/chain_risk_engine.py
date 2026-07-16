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