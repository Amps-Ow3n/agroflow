from utils.validators import normalize

from utils.date_utils import (
    get_weeks_between,
    to_date
)

from db import get_db

def calculate_supply_capacity(supplies):
    """
    Returns a dict {(crop, ISO_week): weekly_capacity}
    """
    capacity = {}

    for s in supplies:
        crop = s["crop"]
        total_qty = s["qty_max"]
        start_date = to_date(s["available_from"])
        end_date = to_date(s["available_to"])

        weeks = get_weeks_between(start_date, end_date)
        if not weeks:
            continue

        weekly_capacity = total_qty / len(weeks)

        for week in weeks:
            key = (crop, week)
            capacity[key] = capacity.get(key, 0) + weekly_capacity

    return capacity

# ----------------------------
# Aggregate commitments (evenly across ISO weeks)
# ----------------------------
def calculate_commitment_load(commitments):
    """
    Returns a dict {(crop, ISO_week): weekly_committed_qty}
    """
    load = {}

    for c in commitments:
        crop = c["crop"]
        total_qty = c["promised_qty"]
        start_date = to_date(c["delivery_start"])
        end_date = to_date(c["delivery_end"])

        weeks = get_weeks_between(start_date, end_date)
        if not weeks:
            continue

        weekly_qty = total_qty / len(weeks)

        for week in weeks:
            key = (crop, week)
            load[key] = load.get(key, 0) + weekly_qty

    return load

# ----------------------------
# Feasibility check per farmer
# ----------------------------
def check_feasibility_core(farmer_id: int):
    """
    Evaluates a farmer's commitments vs supply and returns feasibility summary.
    Aggregates commitments per crop/week and compares to weekly capacity.
    """
    conn, cursor = get_db()

    try:
        # Fetch commitments
        cursor.execute("""
            SELECT crop, promised_qty, delivery_start, delivery_end
            FROM commitments
            WHERE farmer_id = %s
        """, (farmer_id,))
        commitments = [dict(row) for row in cursor.fetchall()]

        # Fetch supply
        cursor.execute("""
            SELECT crop, qty_max, available_from, available_to
            FROM farmer_supply
            WHERE farmer_id = %s
        """, (farmer_id,))
        supplies = [dict(row) for row in cursor.fetchall()]

        if not supplies:
            return {
                "farmer_id": farmer_id,
                "feasible_commitments": [],
                "over_commitments": [],
                "confidence_score": 0,
                "calculation_details": {}
            }

        # Step 1: aggregate
        load = calculate_commitment_load(commitments)
        capacity = calculate_supply_capacity(supplies)

        # Step 2: compare
        feasible = []
        overcommitted = []
        utilization_list = []
        calculation_details = {}

        for key, promised in load.items():
            crop, week = key
            available = capacity.get(key, 0)
            utilization = promised / available if available > 0 else 0
            over_ratio = max(0, (promised - available) / available) if available > 0 else 0
            utilization_list.append(utilization)

            calculation_details[str(key)] = {
    "promised": round(promised, 2),
    "capacity": round(available, 2),
    "utilization": round(utilization, 2),
    "message": (
    f"Over capacity by {round(over_ratio * 100, 1)}% — requires reduction or rescheduling"
    if over_ratio > 0
    else "Within capacity limits — operationally feasible"
)
}

            if promised > available:
                overcommitted.append({
    "crop": crop,
    "week": week,
    "promised": round(promised, 2),
    "capacity": round(available, 2),
    "over_by": round(promised - available, 2),
    "over_ratio": round(over_ratio, 2),
    "risk_signal": "LOW" if promised <= available else "HIGH",
    "message": (
    f"CRITICAL: Exceeds capacity by {round(over_ratio * 100, 1)}% — high default risk"
)
})
            else:
                feasible.append({
    "crop": crop,
    "week": week,
    "promised": round(promised, 2),
    "capacity": round(available, 2),
    "over_ratio": round(over_ratio, 2),
    "risk_signal": "LOW" if promised <= available else "HIGH",
    "message": "Within capacity"
})
        # Step 3: confidence
        if not utilization_list:
            confidence = 0
        else:
           avg_util = sum(utilization_list) / len(utilization_list)

           if avg_util <= 0.8:
              confidence = 85
           elif avg_util <= 1.0:
                confidence = 65
           else:
               confidence = max(20, 100 - (avg_util * 60))
        return {
            "farmer_id": farmer_id,
            "feasible_commitments": feasible,
            "over_commitments": overcommitted,
            "confidence_score": round(confidence, 2),
            "calculation_details": calculation_details
        }

    finally:
        conn.close() 

# -----------------------------------
# Aggregate total supply per crop + zone
# -----------------------------------
def aggregate_supply(db, farmer_id):
    """
    Compute total supply per crop and zone for a farmer.
    """
    rows = db.execute("""
        SELECT crop, zone, SUM(qty_max) as total_capacity
        FROM farmer_supply
        WHERE farmer_id = %s
        GROUP BY crop, zone
    """, (farmer_id,)).fetchall()

    supply = {}
    for row in rows:
        crop = row["crop"]
        zone = row["zone"]
        total_capacity = row["total_capacity"]
        if crop not in supply:
            supply[crop] = {}
        supply[crop][zone] = total_capacity
    return supply
# ----------------------------
# Aggregate total commitments per crop + zone
# ----------------------------
def aggregate_commitments(db, farmer_id):
    """
    Compute total commitments per crop and zone for a farmer.
    """
    rows = db.execute("""
        SELECT crop, zone, SUM(promised_qty) as total_committed
        FROM commitments
        WHERE farmer_id = %s
        GROUP BY crop, zone
    """, (farmer_id,)).fetchall()

    commitments = {}
    for row in rows:
        crop = row["crop"]
        zone = row["zone"]
        total_committed = row["total_committed"]
        if crop not in commitments:
            commitments[crop] = {}
        commitments[crop][zone] = total_committed
    return commitments

# -----------------------------------
# Delivery completion percentage
# -----------------------------------
def compute_delivery_metrics(db, farmer_id):
    rows = db.execute("""
        SELECT d.crop, d.zone, SUM(d.delivered_qty) as total_delivered
        FROM deliveries d
        JOIN commitments c ON d.commitment_id = c.id
        WHERE c.farmer_id = %s
        GROUP BY d.crop, d.zone
    """, (farmer_id,)).fetchall()

    result = []

    for r in rows:
        crop = normalize(r["crop"])
        zone = normalize(r["zone"])

        result.append({
            "crop": crop,
            "zone": zone,
            "total_delivered": r["total_delivered"]
        })

    return result

# -----------------------------------
# Missed deliveries count
# -----------------------------------
def count_missed(deliveries):
    return sum(
        1 for d in deliveries 
        if d["status"] in ["FAILED", "MISSED"]
    )
