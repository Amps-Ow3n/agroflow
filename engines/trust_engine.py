from db import get_db
# -----------------------------------
# Farmer Reliability Score Engine
# -----------------------------------
def update_farmer_trust(
    farmer_id,
    verification_status,
    confidence_score=1.0
):

    conn, cursor = get_db()

    try:

        cursor.execute("""
            SELECT score, total_deliveries
            FROM farmer_trust
            WHERE farmer_id = %s
        """, (farmer_id,))

        row = cursor.fetchone()

        # -----------------------------
        # Create initial trust profile
        # -----------------------------
        if not row:

            score = 80
            total = 0

            cursor.execute("""
                INSERT INTO farmer_trust (
                    farmer_id,
                    score,
                    total_deliveries
                )
                VALUES (%s, %s, %s)
            """, (
                farmer_id,
                score,
                total
            ))

        else:
            score = row["score"]
            total = row["total_deliveries"]

        # -----------------------------
        # TRUST UPDATE LOGIC
        # -----------------------------
        if verification_status == "VERIFIED":

            score += 1.5 * confidence_score

        elif verification_status == "PARTIAL":

            score -= 1.5 * (1 - confidence_score)

        elif verification_status == "REJECTED":

            score -= 4

        # Clamp score
        score = max(0, min(100, score))

        total += 1

        # -----------------------------
        # SAVE
        # -----------------------------
        cursor.execute("""
            UPDATE farmer_trust
            SET
                score = %s,
                total_deliveries = %s
            WHERE farmer_id = %s
        """, (
            score,
            total,
            farmer_id
        ))

        conn.commit()

    except Exception as e:

        print("Trust update error:", e)

    finally:
        conn.close()