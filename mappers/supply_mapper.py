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