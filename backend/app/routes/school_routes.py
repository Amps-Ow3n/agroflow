from fastapi import APIRouter
from app.core.db import get_db

router = APIRouter(tags=["Schools"])


@router.get("/schools")
def get_schools():
    conn, cursor = get_db()

    try:
        cursor.execute("""
            SELECT id, name
            FROM users
            WHERE role = 'school'
            ORDER BY name ASC
        """)

        return cursor.fetchall()

    finally:
        conn.close()