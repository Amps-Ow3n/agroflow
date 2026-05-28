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