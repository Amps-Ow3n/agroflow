from fastapi import APIRouter, Depends

from app.core.db import get_db
from app.core.dependencies import require_admin

router = APIRouter(
    prefix="/audit",
    tags=["Audit"]
)

@router.get("/")
def get_audit_logs(

    limit:int=50,
    offset:int=0,
    user=Depends(require_admin)

):

    conn,cursor=get_db()

    try:

        cursor.execute("""
SELECT *
FROM audit_logs
ORDER BY created_at DESC
LIMIT %s
OFFSET %s
        """)

        return cursor.fetchall()

    finally:

        conn.close()