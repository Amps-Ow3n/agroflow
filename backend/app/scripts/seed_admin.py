from app.core.db import get_db
from app.core.auth import hash_password

def seed_admin():
    conn, cursor = get_db()

    email = "admin@agroflow.com"

    cursor.execute("""
        SELECT * FROM users
        WHERE email = %s
    """, (email,))
    
    existing = cursor.fetchone()

    if existing:
        print("Admin already exists")
        conn.close()
        return

    cursor.execute("""
        INSERT INTO users (
            name,
            email,
            password,
            role
        )
        VALUES (%s, %s, %s, %s)
    """, (
        "System Admin",
        email,
        hash_password("admin123"),
        "admin"
    ))

    conn.commit()
    conn.close()

    print("Admin seeded successfully")


if __name__ == "__main__":
    seed_admin()