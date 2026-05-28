def map_to_intelligence(trust_row=None, risk_row=None, prediction=None):
    """
    Unifies distributed intelligence into one conceptual object
    """

    trust_score = trust_row["score"] if trust_row else 100
    risk_score = risk_row["risk_score"] if risk_row else 0
    risk_level = risk_row["risk_level"] if risk_row else "LOW"

    return {
        "actor_id": trust_row["farmer_id"] if trust_row else None,

        "trust": {
            "score": trust_score,
            "deliveries": trust_row["total_deliveries"] if trust_row else 0
        },

        "risk": {
            "score": risk_score,
            "level": risk_level
        },

        "prediction": prediction or {},

        # unified system view (IMPORTANT FOR DASHBOARDS)
        "system_health": (
            "STABLE" if risk_score < 0.3 else
            "UNSTABLE" if risk_score < 0.6 else
            "CRITICAL"
        )
    }