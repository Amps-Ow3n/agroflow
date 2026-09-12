from fastapi import APIRouter,Depends
from app.core.db import get_db
from app.core.dependencies import require_delivery_create,require_delivery_view,require_delivery_inspect,require_corrective_action_create
from app.core.transactions import write_transaction
from app.schemas.delivery_schema import DeliveryCreate,InspectionCreate,CorrectiveActionCreate
from app.services.delivery_service import create_delivery,get_delivery,get_procurement_deliveries
from app.services.inspection_service import inspect_delivery,create_corrective_action,get_delivery_history,get_procurement_inspection_history

router=APIRouter(prefix="/deliveries",tags=["Deliveries"])

@router.get("/procurement/{procurement_id}")
def procurement_deliveries(procurement_id:int,user=Depends(require_delivery_view)):
    conn,cursor=get_db()
    try: return get_procurement_deliveries(cursor,procurement_id,user["user"]["id"])
    finally: conn.close()

@router.get("/procurement/{procurement_id}/inspection-history")
def inspection_history(procurement_id:int,user=Depends(require_delivery_view)):
    conn,cursor=get_db()
    try: return get_procurement_inspection_history(cursor,procurement_id,user["user"]["id"])
    finally: conn.close()

@router.post("",status_code=201)
def record_delivery(payload:DeliveryCreate,user=Depends(require_delivery_create)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn): return create_delivery(cursor,user["user"]["id"],payload)
    finally: conn.close()

@router.get("/{delivery_id}")
def delivery_detail(delivery_id:int,user=Depends(require_delivery_view)):
    conn,cursor=get_db()
    try: return get_delivery(cursor,delivery_id,user["user"]["id"])
    finally: conn.close()

@router.post("/{delivery_id}/inspect")
def inspect(delivery_id:int,payload:InspectionCreate,user=Depends(require_delivery_inspect)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn): return inspect_delivery(cursor,delivery_id,user["user"]["id"],payload)
    finally: conn.close()

@router.post("/{inspection_id}/corrective-action")
def corrective_action(inspection_id:int,payload:CorrectiveActionCreate,user=Depends(require_corrective_action_create)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn): return create_corrective_action(cursor,inspection_id,user["user"]["id"],payload)
    finally: conn.close()

@router.get("/{delivery_id}/history")
def history(delivery_id:int,user=Depends(require_delivery_view)):
    conn,cursor=get_db()
    try: return get_delivery_history(cursor,delivery_id,user["user"]["id"])
    finally: conn.close()
