from fastapi import APIRouter,Depends
from app.core.db import get_db
from app.core.dependencies import require_procurement_viewer
from app.services.procurement_event_service import get_procurement_timeline,get_procurement_audit

router=APIRouter(prefix="/procurements",tags=["Procurement Timeline & Audit"])

@router.get("/{procurement_id}/timeline")
def timeline(procurement_id:int,user=Depends(require_procurement_viewer)):
    conn,cursor=get_db()
    try: return {"events":get_procurement_timeline(cursor,procurement_id,user["user"]["id"])}
    finally: conn.close()

@router.get("/{procurement_id}/audit")
def audit(procurement_id:int,user=Depends(require_procurement_viewer)):
    conn,cursor=get_db()
    try: return {"events":get_procurement_audit(cursor,procurement_id,user["user"]["id"])}
    finally: conn.close()
