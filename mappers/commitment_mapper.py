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