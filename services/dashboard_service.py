from psycopg2.extras import RealDictCursor
from engines.risk_engine import compute_farmer_risk_v2
from utils.delivery_utils import compute_delivery_status_with_reason
from main import (
    compute_farmer_risk_v2,
    compute_delivery_status_with_reason
)
# ==============================
# FARMER DASHBOARD ENGINE
# ==============================
def generate_farmer_dashboard(conn, farmer_id):

    try:

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # =====================================================
        # 1. SUPPLY SUMMARY
        # =====================================================
        cursor.execute("""
            SELECT
                crop,
                COALESCE(zone, '-') as zone,
                SUM(qty_max) as total_capacity
            FROM farmer_supply
            WHERE farmer_id = %s
            GROUP BY crop, zone
            ORDER BY crop
        """, (farmer_id,))

        supply_summary = cursor.fetchall()

        supply_map = {
            (s["crop"], s["zone"]): s["total_capacity"]
            for s in supply_summary
        }

        # =====================================================
        # 2. COMMITMENT SUMMARY
        # =====================================================
        cursor.execute("""
            SELECT
                id,
                crop,
                COALESCE(zone, '-') as zone,
                promised_qty,
                delivery_start,
                delivery_end,
                status
            FROM commitments
            WHERE farmer_id = %s
            ORDER BY id DESC
        """, (farmer_id,))

        commitment_rows = cursor.fetchall()

        commitment_summary = []

        total_promised = 0

        for r in commitment_rows:

            crop = r["crop"]
            zone = r["zone"]

            promised = r["promised_qty"] or 0
            capacity = supply_map.get((crop, zone), 0)

            utilization = (
                (promised / capacity) * 100
                if capacity > 0 else 0
            )

            total_promised += promised

            commitment_summary.append({
                "commitment_id": r["id"],
                "crop": crop,
                "zone": zone,
                "promised_qty": promised,
                "capacity": capacity,
                "utilization_percent": round(utilization, 2),
                "delivery_start": r["delivery_start"],
                "delivery_end": r["delivery_end"],
                "status": r["status"]
            })

        # =====================================================
        # 3. DELIVERY PERFORMANCE
        # =====================================================
        cursor.execute("""
            SELECT
                c.id as commitment_id,
                c.crop,
                COALESCE(c.zone, '-') as zone,
                c.promised_qty,

                COALESCE(SUM(d.delivered_qty), 0) as reported_qty,

                COALESCE(SUM(
                    CASE
                        WHEN d.verification_status IN ('VERIFIED', 'PARTIAL')
                        THEN d.delivered_qty
                        ELSE 0
                    END
                ), 0) as verified_qty,

                COALESCE(MAX(d.verification_status), 'PENDING')
                as verification_status

            FROM commitments c

            LEFT JOIN deliveries d
            ON d.commitment_id = c.id

            WHERE c.farmer_id = %s

            GROUP BY
                c.id,
                c.crop,
                c.zone,
                c.promised_qty

            ORDER BY c.id DESC
        """, (farmer_id,))

        delivery_rows = cursor.fetchall()

        delivery_history = []

        total_reported = 0
        total_verified = 0
        total_missed = 0

        for r in delivery_rows:

            promised = r["promised_qty"] or 0

            reported_qty = min(
                r["reported_qty"] or 0,
                promised
            )

            verified_qty = min(
                r["verified_qty"] or 0,
                promised
            )

            total_reported += reported_qty
            total_verified += verified_qty

            missed_qty = max(promised - verified_qty, 0)

            total_missed += missed_qty

            reported_status, reported_reason = \
                compute_delivery_status_with_reason(
                    reported_qty,
                    promised
                )

            verified_status, verified_reason = \
                compute_delivery_status_with_reason(
                    verified_qty,
                    promised
                )

            delivery_history.append({

                "commitment_id": r["commitment_id"],

                "crop": r["crop"],

                "zone": r["zone"],

                "promised_qty": promised,

                "verification_status": r["verification_status"],

                # --------------------------------
                # REPORTED
                # --------------------------------
                "reported_delivery": {
                    "qty": reported_qty,
                    "status": reported_status,
                    "reason": reported_reason
                },

                # --------------------------------
                # VERIFIED
                # --------------------------------
                "verified_delivery": {
                    "qty": verified_qty,
                    "status": verified_status,
                    "reason": verified_reason
                },

                # --------------------------------
                # GAP
                # --------------------------------
                "verification_gap": max(
                    reported_qty - verified_qty,
                    0
                )
            })

        # =====================================================
        # 4. TRUST SCORE
        # =====================================================
        cursor.execute("""
            SELECT score
            FROM farmer_trust
            WHERE farmer_id = %s
        """, (farmer_id,))

        trust_row = cursor.fetchone()

        trust_score = (
            trust_row["score"]
            if trust_row else 100
        )

        if trust_score >= 80:
            trust_label = "RELIABLE"

        elif trust_score >= 50:
            trust_label = "MODERATE"

        else:
            trust_label = "RISKY"

        # =====================================================
        # 5. PERFORMANCE METRICS
        # =====================================================
        reported_rate = (
            (total_reported / total_promised) * 100
            if total_promised > 0 else 0
        )

        verified_rate = (
            (total_verified / total_promised) * 100
            if total_promised > 0 else 0
        )

        # =====================================================
        # 6. RISK ENGINE
        # =====================================================
        risk_summary = compute_farmer_risk_v2(
            cursor,
            farmer_id
        )

        # =====================================================
        # 7. RISK ALERTS
        # =====================================================
        risk_alerts = []

        for explanation in risk_summary.get("explanation", []):

            risk_alerts.append({
                "message": explanation,
                "risk_level": risk_summary["risk_level"]
            })

        # =====================================================
        # FINAL RESPONSE
        # =====================================================
        return {

            # --------------------------------
            # SUPPLY
            # --------------------------------
            "supply_summary": supply_summary,

            # --------------------------------
            # COMMITMENTS
            # --------------------------------
            "commitment_summary": commitment_summary,

            # --------------------------------
            # DELIVERIES
            # --------------------------------
            "delivery_history": delivery_history,

            # --------------------------------
            # REPORTED PERFORMANCE
            # --------------------------------
            "reported_performance": {
                "completion_rate": round(reported_rate, 2),
                "total_reported_qty": total_reported
            },

            # --------------------------------
            # VERIFIED PERFORMANCE
            # --------------------------------
            "verified_performance": {
                "completion_rate": round(verified_rate, 2),
                "total_verified_qty": total_verified,
                "missed_qty": total_missed
            },

            # --------------------------------
            # TRUST
            # --------------------------------
            "trust_score": {
                "score": trust_score,
                "label": trust_label
            },

            # --------------------------------
            # RISK
            # --------------------------------
            "risk_summary": risk_summary,

            "risk_alerts": risk_alerts
        }

    except Exception as e:

        print("Error generating farmer dashboard:", e)

        return {
            "error": str(e)
        }

# ==============================
# ADMIN DASHBOARD ENGINE V2
# ==============================
def generate_admin_dashboard(conn):

    try:

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # =====================================================
        # 1. PLATFORM TOTALS
        # =====================================================
        cursor.execute("""
            SELECT
                COUNT(*) as total_commitments,
                COALESCE(SUM(promised_qty), 0) as total_promised
            FROM commitments
        """)

        totals = cursor.fetchone()

        total_commitments = totals["total_commitments"] or 0
        total_promised = totals["total_promised"] or 0

        # =====================================================
        # 2. VERIFIED DELIVERY TOTALS
        # =====================================================
        cursor.execute("""
            SELECT

                COALESCE(SUM(d.delivered_qty), 0) as total_reported,

                COALESCE(SUM(
                    CASE
                        WHEN d.verification_status IN ('VERIFIED', 'PARTIAL')
                        THEN d.delivered_qty
                        ELSE 0
                    END
                ), 0) as total_verified,

                COUNT(*) FILTER (
                    WHERE d.verification_status = 'REJECTED'
                ) as rejected_count,

                COUNT(*) FILTER (
                    WHERE d.verification_status = 'VERIFIED'
                ) as verified_count

            FROM deliveries d
        """)

        delivery_totals = cursor.fetchone()

        total_reported = delivery_totals["total_reported"] or 0
        total_verified = delivery_totals["total_verified"] or 0

        rejected_count = delivery_totals["rejected_count"] or 0
        verified_count = delivery_totals["verified_count"] or 0

        # =====================================================
        # 3. PLATFORM VERIFICATION RATE
        # =====================================================
        verification_rate = 0

        total_verifications = verified_count + rejected_count

        if total_verifications > 0:
            verification_rate = (
                verified_count / total_verifications
            ) * 100

        # =====================================================
        # 4. PLATFORM COMPLETION RATE
        # =====================================================
        completion_rate = 0

        if total_promised > 0:
            completion_rate = (
                total_verified / total_promised
            ) * 100

        # =====================================================
        # 5. FARMER RISK OVERVIEW
        # =====================================================
        cursor.execute("""
            SELECT
                frc.farmer_id,
                u.name,
                frc.risk_score,
                frc.risk_level,
                frc.explanation,
                ft.score as trust_score

            FROM farmer_risk_cache frc

            LEFT JOIN users u
            ON frc.farmer_id = u.id

            LEFT JOIN farmer_trust ft
            ON frc.farmer_id = ft.farmer_id

            ORDER BY frc.risk_score DESC
        """)

        risk_rows = cursor.fetchall()

        farmers = []

        total_risk_score = 0

        for r in risk_rows:

            risk_score = r["risk_score"] or 0
            trust_score = r["trust_score"] or 100

            total_risk_score += risk_score

            # -----------------------------
            # TRUST LABEL
            # -----------------------------
            if trust_score >= 80:
                trust_label = "HIGH"

            elif trust_score >= 50:
                trust_label = "MEDIUM"

            else:
                trust_label = "LOW"

            farmers.append({

                "farmer_id": r["farmer_id"],

                "farmer_name": r["name"],

                "risk_score": round(risk_score, 2),

                "risk_level": r["risk_level"],

                "trust_score": trust_score,

                "trust_label": trust_label,

                "risk_explanation": r["explanation"]
            })

        # =====================================================
        # 6. SYSTEM RISK OVERVIEW
        # =====================================================
        avg_platform_risk = 0

        if len(farmers) > 0:
            avg_platform_risk = (
                total_risk_score / len(farmers)
            )

        high_risk_farmers = [
            f for f in farmers
            if f["risk_level"] == "HIGH"
        ]

        # =====================================================
        # 7. VERIFICATION GAPS
        # =====================================================
        cursor.execute("""
            SELECT

                c.id as commitment_id,
                c.crop,
                c.zone,

                u.name as farmer_name,

                c.promised_qty,

                COALESCE(SUM(d.delivered_qty), 0) as reported_qty,

                COALESCE(SUM(
                    CASE
                        WHEN d.verification_status
                        IN ('VERIFIED', 'PARTIAL')
                        THEN d.delivered_qty
                        ELSE 0
                    END
                ), 0) as verified_qty

            FROM commitments c

            LEFT JOIN deliveries d
            ON c.id = d.commitment_id

            LEFT JOIN users u
            ON c.farmer_id = u.id

            GROUP BY
                c.id,
                c.crop,
                c.zone,
                u.name,
                c.promised_qty

            ORDER BY c.id DESC
        """)

        gap_rows = cursor.fetchall()

        verification_gaps = []

        for r in gap_rows:

            reported = r["reported_qty"] or 0
            verified = r["verified_qty"] or 0

            gap = max(reported - verified, 0)

            if gap > 0:

                verification_gaps.append({

                    "commitment_id": r["commitment_id"],

                    "farmer_name": r["farmer_name"],

                    "crop": r["crop"],

                    "zone": r["zone"] or "-",

                    "reported_qty": reported,

                    "verified_qty": verified,

                    "gap": gap,

                    "severity": round(
                        min(100, (gap / max(reported, 1)) * 100),
                        2
                    )
                })

        # =====================================================
        # 8. UNRELIABLE ACTORS
        # =====================================================
        unreliable_actors = []

        for f in farmers:

            reasons = []

            if f["risk_score"] >= 70:
                reasons.append("High operational risk")

            if f["trust_score"] < 50:
                reasons.append("Low trust score")

            if f["risk_level"] == "HIGH":
                reasons.append("Repeated delivery inconsistencies")

            if reasons:

                unreliable_actors.append({

                    "farmer_id": f["farmer_id"],

                    "farmer_name": f["farmer_name"],

                    "risk_score": f["risk_score"],

                    "trust_score": f["trust_score"],

                    "reasons": reasons
                })

        # =====================================================
        # 9. FINAL RESPONSE
        # =====================================================
        return {

            # -------------------------------------------------
            # SYSTEM OVERVIEW
            # -------------------------------------------------
            "system_risk_overview": {

                "total_commitments": total_commitments,

                "total_promised_qty": total_promised,

                "total_reported_qty": total_reported,

                "total_verified_qty": total_verified,

                "platform_completion_rate":
                    round(completion_rate, 2),

                "verification_rate":
                    round(verification_rate, 2),

                "average_platform_risk":
                    round(avg_platform_risk, 2),

                "high_risk_farmers":
                    len(high_risk_farmers)
            },

            # -------------------------------------------------
            # FARMER RISK TABLE
            # -------------------------------------------------
            "farmer_risk_overview": farmers,

            # -------------------------------------------------
            # VERIFICATION GAPS
            # -------------------------------------------------
            "verification_gaps": verification_gaps,

            # -------------------------------------------------
            # UNRELIABLE ACTORS
            # -------------------------------------------------
            "unreliable_actors": unreliable_actors
        }

    except Exception as e:

        print("Error generating admin dashboard:", e)

        return {
            "error": str(e)
        }
