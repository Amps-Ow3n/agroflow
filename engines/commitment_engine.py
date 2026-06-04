# =====================================================
# COMMITMENT ENGINE
# Extracted from main.py
# NO behavior changes
# =====================================================

from datetime import datetime

# =====================================================
# COMPUTE OVERCOMMIT RISK
# =====================================================
def compute_overcommit_risk(
    promised_qty,
    available_capacity
):
    """
    Preserves current soft-constraint behavior.

    Returns:
        over_amount
        over_ratio
        risk_level
    """

    available_capacity = max(
        available_capacity,
        0
    )

    if promised_qty <= available_capacity:

        return {
            "over_amount": 0,
            "over_ratio": 0,
            "risk_level": "LOW"
        }

    over_amount = (
        promised_qty
        - available_capacity
    )

    over_ratio = (
        over_amount / available_capacity
        if available_capacity > 0
        else 1
    )

    if over_ratio < 0.2:
        level = "MEDIUM"
    else:
        level = "HIGH"

    return {
        "over_amount": round(
            over_amount,
            2
        ),
        "over_ratio": round(
            over_ratio,
            2
        ),
        "risk_level": level
    }


# =====================================================
# INSERT DECISION LOG
# =====================================================
def insert_commitment_decision(
    cursor,
    farmer_id,
    crop,
    week,
    over_amount,
    explanation
):

    cursor.execute("""
        INSERT INTO decision_logs(
            farmer_id,
            crop,
            week,
            over_amount,
            explanation
        )
        VALUES(
            %s,
            %s,
            %s,
            %s,
            %s
        )
    """, (
        farmer_id,
        crop,
        week,
        over_amount,
        explanation
    ))


# =====================================================
# FEASIBILITY WRAPPER
# =====================================================
def compute_feasibility(
    farmer_id,
    feasibility_function
):
    """
    Thin wrapper only.

    Keeps existing behavior
    while allowing future engine replacement.
    """

    return feasibility_function(
        farmer_id
    )