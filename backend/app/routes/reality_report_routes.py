from fastapi import APIRouter, Depends

from app.core.db import get_db
from app.core.dependencies import require_reality_report_for_procurement
from app.services.reality_report_service import get_reality_report

router = APIRouter(prefix="/procurements", tags=["Procurement Reality Report"])


@router.get("/{procurement_id}/reality-report")
def reality_report(
    procurement_id: int,
    user=Depends(require_reality_report_for_procurement),
):
    conn, cursor = get_db()
    try:
        return get_reality_report(cursor, procurement_id, user["user"]["id"])
    finally:
        conn.close()
