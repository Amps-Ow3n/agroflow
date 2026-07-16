from app.core.db import get_db

def create_user(name, email, password, role):
    conn, cursor = get_db()

    cursor.execute("""
        INSERT INTO users (name, email, password, role)
        VALUES (%s, %s, %s, %s)
        RETURNING id, name, email, role
    """, (name, email, password, role))

    user = cursor.fetchone()

    conn.commit()
    conn.close()

    return user


def get_user_by_email(email):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT * FROM users
        WHERE email = %s
    """, (email,))

    user = cursor.fetchone()

    conn.close()

    return user

def get_user_by_id(user_id):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT id, name, email, role
        FROM users
        WHERE id = %s
    """, (user_id,))

    user = cursor.fetchone()

    conn.close()

    return user