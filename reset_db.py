from main import get_db
def reset_db():
    conn, cursor = get_db()

    cursor.execute("DROP TABLE IF EXISTS deliveries CASCADE")
    cursor.execute("DROP TABLE IF EXISTS commitments CASCADE")
    cursor.execute("DROP TABLE IF EXISTS farmer_supply CASCADE")
    cursor.execute("DROP TABLE IF EXISTS decision_logs CASCADE")
    cursor.execute("DROP TABLE IF EXISTS farmer_trust CASCADE")
    cursor.execute("DROP TABLE IF EXISTS farmer_risk_cache CASCADE")
    cursor.execute("DROP TABLE IF EXISTS users CASCADE")

    conn.commit()
    conn.close()

reset_db()