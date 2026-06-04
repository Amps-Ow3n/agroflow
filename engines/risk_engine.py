from datetime import datetime

from db import get_db

from engines.delivery_engine import (
    compute_confidence_score
)
from utils.date_utils import (
    to_date,
    to_datetime
)
def get_farmer_history(cursor, farmer_id):
    cursor.execute("""
        SELECT d.delivered_qty, d.status, d.week_start, d.week_end,
               c.promised_qty
        FROM deliveries d
        JOIN commitments c ON d.commitment_id = c.id
        WHERE c.farmer_id = %s
    """, (farmer_id,))
    
    return [dict(r) for r in cursor.fetchall()]

# -----------------------------
# Compute consistency
# -----------------------------
def compute_consistency(deliveries):
    if not deliveries:
        return 0
    
    completed = sum(1 for d in deliveries if d["status"] == "COMPLETED")
    return completed / len(deliveries)

# -----------------------------
# Compute overcommitment frequency
# -----------------------------
def compute_overcommitment(cursor, farmer_id):
    # Total promised
    cursor.execute("""
        SELECT SUM(promised_qty) as total_promised
        FROM commitments
        WHERE farmer_id = %s
    """, (farmer_id,))
    promised = cursor.fetchone()["total_promised"] or 0

    # Total supply capacity
    cursor.execute("""
        SELECT SUM(qty_max) as total_supply
        FROM farmer_supply
        WHERE farmer_id = %s
    """, (farmer_id,))
    supply = cursor.fetchone()["total_supply"] or 0

    if supply <= 0:
        return 0

    overcommitment_ratio = max(0, (promised - supply) / supply) if supply > 0 else 0
    overcommitment_ratio = min(overcommitment_ratio, 1.0)  # <-- NEW cap
    return round(overcommitment_ratio, 2)
# -----------------------------
# Compute trend (last vs previous)
# -----------------------------
def compute_trend(deliveries):
    if len(deliveries) < 4:
        return 0.5  # neutral
    
    deliveries = sorted(deliveries, key=lambda x: x["week_start"])
    
    mid = len(deliveries) // 2
    first_half = deliveries[:mid]
    second_half = deliveries[mid:]
    
    def avg_completion(ds):
        return sum(1 for d in ds if d["status"] == "COMPLETED") / len(ds)
    
    return avg_completion(second_half) - avg_completion(first_half)

def build_risk_explanation(overcommitment_risk,
                           verification_risk,
                           mismatch_risk,
                           inconsistency_risk,
                           risk_score):

    explanation = []

    # -----------------------------
    # OVERCOMMITMENT
    # -----------------------------
    if overcommitment_risk > 0.2:
        explanation.append(
            "Farmer has committed more supply than available capacity."
        )
    elif overcommitment_risk > 0:
        explanation.append(
            "Mild overcommitment detected between supply and commitments."
        )

    # -----------------------------
    # VERIFICATION
    # -----------------------------
    if verification_risk > 0.3:
        explanation.append(
            "High rejection rate from buyer verification."
        )
    elif verification_risk > 0:
        explanation.append(
            "Some deliveries have been rejected by buyer."
        )

    # -----------------------------
    # MISMATCH
    # -----------------------------
    if mismatch_risk > 0.3:
        explanation.append(
            "Large gap between reported and verified deliveries."
        )
    elif mismatch_risk > 0:
        explanation.append(
            "Minor mismatch between reported and verified quantities."
        )

    # -----------------------------
    # INCONSISTENCY
    # -----------------------------
    if inconsistency_risk > 0.3:
        explanation.append(
            "Delivery quantities are highly inconsistent over time."
        )
    elif inconsistency_risk > 0:
        explanation.append(
            "Some variation in delivery consistency detected."
        )

    # -----------------------------
    # GLOBAL SUMMARY
    # -----------------------------
    if not explanation:
        if risk_score < 30:
            explanation.append("Farmer shows stable and reliable performance.")
        elif risk_score < 70:
            explanation.append("Moderate risk detected in farmer performance.")
        else:
            explanation.append("High risk farmer with multiple performance issues.")

    return explanation

def compute_time_risk_trend(deliveries):
    if len(deliveries) < 3:
        return []

    deliveries = sorted(deliveries, key=lambda x: x["week_start"])

    trend_series = []

    for d in deliveries:
        promised = d["promised_qty"] or 0
        delivered = d["delivered_qty"] or 0

        if promised == 0:
            risk = 1
        else:
            risk = 1 - (delivered / promised)

        trend_series.append({
            "week": d["week_start"],
            "risk": round(risk, 2)
        })

    return trend_series

def generate_intervention(risk, all_results=None):
    actions = []

    level = risk.get("risk_level")
    delivery_rate = risk.get("delivery_rate", 1)
    overcommitment = risk.get("overcommitment", 0)
    trend = risk.get("trend", 0)

    # -----------------------------
    # Base actions
    # -----------------------------
    if level == "HIGH":
        actions.append("Reduce commitments immediately")
        actions.append("Flag farmer for manual review")

    if overcommitment > 0.3:
        actions.append("Rebalance committed quantities")

    if delivery_rate < 0.7:
        actions.append("Reallocate demand to reliable farmers")

    if trend < 0:
        actions.append("Investigate performance decline")

    # -----------------------------
    # AUTO REALLOCATION ENGINE (FIXED)
    # -----------------------------
    reallocation_targets = []

    if all_results and level == "HIGH":
        for r in all_results:
            other = r["risk"]

            if (
                other.get("risk_level") == "LOW"
                and other.get("delivery_rate", 0) > 0.8
                and other.get("consistency", 0) > 0.7
                and other.get("farmer_id") != risk.get("farmer_id")
            ):
                reallocation_targets.append({
                    "farmer_id": other["farmer_id"],
                    "score": other["delivery_rate"]
                })

        # Sort best candidates
        reallocation_targets = sorted(
            reallocation_targets,
            key=lambda x: x["score"],
            reverse=True
        )

        top_targets = [t["farmer_id"] for t in reallocation_targets[:3]]

        if top_targets:
            actions.append(f"Shift demand to farmers {top_targets}")

    # fallback
    if not actions:
        actions.append("No immediate action required")

    return {
        "farmer_id": risk.get("farmer_id"),
        "actions": actions
    }

def compute_farmer_risk_v2(cursor, farmer_id):

    # -----------------------------
    # 1. OVERCOMMITMENT RISK
    # -----------------------------
    cursor.execute("""
        SELECT
            COALESCE(SUM(c.promised_qty),0) as promised,
            COALESCE(SUM(s.qty_max),0) as capacity
        FROM commitments c
        JOIN farmer_supply s
        ON c.farmer_id = s.farmer_id
        AND c.crop = s.crop
        AND c.zone = s.zone
        WHERE c.farmer_id = %s
    """, (farmer_id,))

    row = cursor.fetchone()
    promised = row["promised"]
    capacity = row["capacity"]

    overcommitment_risk = (
        (promised - capacity) / capacity
        if capacity > 0 and promised > capacity else 0
    )

    # -----------------------------
    # 2. VERIFICATION RISK
    # -----------------------------
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN verification_status = 'VERIFIED' THEN 1 ELSE 0 END) as verified,
            SUM(CASE WHEN verification_status = 'REJECTED' THEN 1 ELSE 0 END) as rejected
        FROM deliveries d
        JOIN commitments c ON d.commitment_id = c.id
        WHERE c.farmer_id = %s
    """, (farmer_id,))

    v = cursor.fetchone()
    total = v["total"] or 0
    verified = v["verified"] or 0
    rejected = v["rejected"] or 0

    verification_rate = (verified / total) if total > 0 else 0
    rejection_rate = (rejected / total) if total > 0 else 0
    verification_risk = rejection_rate
    # -----------------------------
    # 3. MISMATCH RISK (reported vs verified)
    # -----------------------------
    cursor.execute("""
        SELECT
            COALESCE(SUM(d.delivered_qty),0) as reported,
            COALESCE(SUM(
                CASE
                    WHEN d.verification_status = 'VERIFIED'
                    THEN d.delivered_qty
                    ELSE 0
                END
            ),0) as verified_qty
        FROM deliveries d
        JOIN commitments c ON d.commitment_id = c.id
        WHERE c.farmer_id = %s
    """, (farmer_id,))

    m = cursor.fetchone()

    reported = m["reported"] or 0
    verified_qty = m["verified_qty"] or 0

    mismatch_risk = (
        (reported - verified_qty) / reported
        if reported > 0 else 0
    )

    # -----------------------------
    # 4. DELIVERY INCONSISTENCY
    # -----------------------------
    cursor.execute("""
        SELECT delivered_qty
        FROM deliveries d
        JOIN commitments c ON d.commitment_id = c.id
        WHERE c.farmer_id = %s
    """, (farmer_id,))

    rows = cursor.fetchall()
    values = [r["delivered_qty"] for r in rows if r["delivered_qty"] is not None]

    if len(values) > 1:
        avg = sum(values) / len(values)
        variance = sum((x - avg) ** 2 for x in values) / len(values)
        inconsistency_risk = min(1, variance / (avg ** 2 + 1))
    else:
        inconsistency_risk = 0

    # -----------------------------
    # FINAL RISK SCORE (0 - 100)
    # -----------------------------
    risk_score = (
        overcommitment_risk * 35 +
        verification_risk * 25 +
        mismatch_risk * 25 +
        inconsistency_risk * 15
    ) * 100

    risk_score = max(0, min(100, risk_score))

    if risk_score < 30:
        risk_level = "LOW"
    elif risk_score < 70:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"
    
    explanation = build_risk_explanation(
    overcommitment_risk,
    verification_risk,
    mismatch_risk,
    inconsistency_risk,
    risk_score
)
    cursor.execute("""
INSERT INTO farmer_risk_cache (
    farmer_id,
    risk_score,
    risk_level,
    explanation,
    last_updated
)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (farmer_id)
DO UPDATE SET
    risk_score = EXCLUDED.risk_score,
    risk_level = EXCLUDED.risk_level,
    explanation = EXCLUDED.explanation,
    last_updated = EXCLUDED.last_updated
""", (
    farmer_id,
    round(risk_score, 2),
    risk_level,
    "\n".join(explanation),
    datetime.now()
))
    return {
    "risk_score": round(risk_score, 2),
    "risk_level": risk_level,

    "explanation": explanation,

    "breakdown": {
        "verification_risk": round(verification_risk * 100, 2),
        "mismatch_risk": round(mismatch_risk * 100, 2),
        "overcommitment_risk": round(overcommitment_risk * 100, 2),
        "inconsistency_risk": round(inconsistency_risk * 100, 2)
    }
}

def recompute_all_risks():
    conn, cursor = get_db()

    try:
        # 1. Clear old logs
        cursor.execute("DELETE FROM decision_logs")

        # 2. Get all farmers
        cursor.execute("SELECT id FROM users WHERE role = 'farmer'")
        farmers = cursor.fetchall()

        for f in farmers:
            farmer_id = f["id"]

            #STEP A: Compute + cache risk
            compute_farmer_risk_v2(cursor, farmer_id)

            #STEP B: System-level overcommit logging
            cursor.execute("""
    SELECT COALESCE(SUM(qty_max),0) AS total_supply
    FROM farmer_supply
    WHERE farmer_id = %s
""", (farmer_id,))

            row = cursor.fetchone()
            total_supply = row["total_supply"] or 0
            cursor.execute("""
                SELECT crop, COALESCE(SUM(promised_qty),0) AS total
                FROM commitments
                WHERE farmer_id = %s
                GROUP BY crop
            """, (farmer_id,))
            rows = cursor.fetchall()

            for r in rows:
                crop = r["crop"]
                promised = r["total"]

                over = max(0, promised - total_supply)

                if total_supply > 0:
                    over_ratio = round(over / total_supply, 2)
                else:
                    over_ratio = 0

                if over > 0:
                    cursor.execute("""
                        INSERT INTO decision_logs
                        (farmer_id, crop, week, over_amount, explanation)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        farmer_id,
                        crop,
                        datetime.now().date().isoformat(),
                        over,
                        f"{crop} overcommitted by {int(over)} units ({int(over_ratio*100)}% beyond capacity)"
                    ))

        conn.commit()

    finally:
        conn.close()