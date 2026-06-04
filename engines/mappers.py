from datetime import date

def map_to_supply(row):
    """
    Converts farmer_supply DB row → Capability domain object
    """

    if not row:
        return None

    return {
        "capability_id": row["id"],
        "actor_id": row["farmer_id"],
        "crop": row["crop"],
        "quantity_range": {
            "min": row["qty_min"],
            "max": row["qty_max"]
        },
        "zone": row["zone"],
        "availability_window": {
            "from": row["available_from"],
            "to": row["available_to"]
        },
        "last_updated": row.get("last_updated")
    }

def map_to_commitment(row):
    """
    Converts commitments DB row → Obligation domain object
    """

    if not row:
        return None

    promised_qty = row["promised_qty"]

    return {
        "obligation_id": row["id"],
        "actor_id": row["farmer_id"],
        "crop": row["crop"],
        "promised_quantity": promised_qty,
        "zone": row["zone"],
        "delivery_window": {
            "start": row["delivery_start"],
            "end": row["delivery_end"]
        },
        "status": row["status"],
        "created_at": row["created_at"],
        "last_updated": row["last_updated"],

        # IMPORTANT derived field (safe, no side effects)
        "pressure_flag": "HIGH" if promised_qty > 0 else "LOW"
    }

from datetime import date

def map_to_delivery(row):
    """
    Converts deliveries DB row → Execution domain object
    """

    if not row:
        return None

    delivered = row.get("delivered_qty") or 0
    promised = row.get("weekly_promised_qty") or 0

    fulfillment_ratio = (
        delivered / promised if promised > 0 else 0
    )

    if fulfillment_ratio >= 1:
        execution_state = "COMPLETED"
    elif fulfillment_ratio >= 0.5:
        execution_state = "PARTIAL"
    elif fulfillment_ratio > 0:
        execution_state = "LOW"
    else:
        execution_state = "FAILED"

    return {
        "execution_id": row["id"],
        "obligation_id": row["commitment_id"],
        "delivered_qty": delivered,
        "promised_qty": promised,
        "week_window": {
            "start": row["week_start"],
            "end": row["week_end"]
        },
        "status": row["status"],
        "logged_at": row["logged_at"],

        # derived semantics (SAFE)
        "fulfillment_ratio": round(fulfillment_ratio, 2),
        "execution_state": execution_state
    }

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