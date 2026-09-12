import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings
from fastapi import HTTPException

def get_db():
    db_url = settings.DATABASE_URL

    if not db_url:
        raise HTTPException(
            status_code=500,
            detail="Database configuration error"
        )
    conn = psycopg2.connect(
        db_url,
        connect_timeout=10
    )

    cursor = conn.cursor(cursor_factory=RealDictCursor)

    return conn, cursor