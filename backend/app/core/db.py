import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

def get_db():
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        raise Exception("DATABASE_URL not set")

    conn = psycopg2.connect(
        db_url,
        connect_timeout=10
    )

    cursor = conn.cursor(cursor_factory=RealDictCursor)

    return conn, cursor