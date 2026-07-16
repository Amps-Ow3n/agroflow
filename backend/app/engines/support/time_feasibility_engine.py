from app.utils.date_utils import is_within_window

def evaluate_time_feasibility(
    sources,
    delivery_start,
    delivery_end,
    promised_qty
):
    valid_quantity = 0
    valid_sources = []

    for source in sources:

        if is_within_window(
            source["available_from"],
            source["available_to"],
            delivery_start,
            delivery_end
        ):

            valid_sources.append(source)
            valid_quantity += source["qty_available"]

    if valid_quantity >= promised_qty:
        return {
            "time_feasible": True,
            "valid_sources_count": len(valid_sources),
            "available_qty": valid_quantity,
            "time_status": "ON_TIME"
        }

    return {
        "time_feasible": False,
        "valid_sources_count": len(valid_sources),
        "available_qty": valid_quantity,
        "time_status": "TIME_OR_CAPACITY_CONFLICT"
    }

def detect_late_chain_risk(
    sources,
    delivery_end
):
    conflicts = [
        s["id"]
        for s in sources
        if s["available_to"] > delivery_end
    ]

    return {
        "late_chain_risk": len(conflicts) > 0,
        "risk_score": len(conflicts),
        "conflicts": conflicts
    }