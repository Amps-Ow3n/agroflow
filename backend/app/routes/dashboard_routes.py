from fastapi import APIRouter, Depends

from app.core.db import get_db
from app.core.dependencies import require_organization_dashboard_view
from app.services.dashboard_service import get_organization_dashboard

router = APIRouter(prefix="/organizations", tags=["Organization Dashboards"])


@router.get("/{organization_id}/dashboard")
def organization_dashboard(
    organization_id: int,
    user=Depends(require_organization_dashboard_view),
):
    conn, cursor = get_db()
    try:
        return get_organization_dashboard(cursor, organization_id)
    finally:
        conn.close()
