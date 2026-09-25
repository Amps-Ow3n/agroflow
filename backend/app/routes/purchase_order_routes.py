from fastapi import APIRouter, Depends, HTTPException
from app.core.db import get_db
from app.core.dependencies import (
    require_purchase_order_create,
    require_purchase_order_view_by_procurement,
)
from app.core.transactions import write_transaction
from app.schemas.procurement_schema import PurchaseOrderCreate
from app.services.purchase_order_service import create_purchase_order

router=APIRouter(prefix="/purchase-orders",tags=["Purchase Orders"])

@router.post("/procurements/{procurement_id}",status_code=201)
def create_order(procurement_id:int,payload:PurchaseOrderCreate,user=Depends(require_purchase_order_create)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            result=create_purchase_order(cursor,procurement_id,user["user"]["id"],payload)
        return {"message":"Purchase order created.","purchase_order":result,"procurement_status":"ORDERED"}
    finally: conn.close()

@router.get("/procurements/{procurement_id}")
def get_order(procurement_id:int,user=Depends(require_purchase_order_view_by_procurement)):
    conn,cursor=get_db()
    try:
        cursor.execute("""SELECT po.*,s.supplier_code,o.name AS supplier_name,creator.name AS created_by_name
                          FROM purchase_orders po JOIN procurements p ON p.id=po.procurement_id
                          JOIN organization_memberships om ON om.organization_id=p.organization_id
                          JOIN suppliers s ON s.id=po.supplier_id JOIN organizations o ON o.id=s.organization_id
                          JOIN users creator ON creator.id=po.created_by
                          WHERE po.procurement_id=%s AND om.user_id=%s AND om.status='ACTIVE'""",(procurement_id,user["user"]["id"]))
        po=cursor.fetchone()
        if not po: raise HTTPException(404,"Purchase order not found.")
        cursor.execute("""SELECT pol.*,pi.item_name FROM purchase_order_lines pol JOIN procurement_items pi ON pi.id=pol.procurement_item_id
                          WHERE pol.purchase_order_id=%s ORDER BY pol.id""",(po["id"],))
        return {"purchase_order":dict(po),"lines":[dict(r) for r in cursor.fetchall()]}
    finally: conn.close()
