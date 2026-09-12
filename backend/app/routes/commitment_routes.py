from fastapi import APIRouter,Depends,HTTPException
from app.core.db import get_db
from app.core.dependencies import require_supplier_user,require_procurement_manager,require_procurement_viewer,require_commitment_create,require_commitment_accept,require_commitment_reject
from app.core.transactions import write_transaction
from app.schemas.commitment_schema import SupplierCommitmentCreate,SupplierCommitmentReject
from app.services.commitment_service import create_commitment,accept_commitment,reject_commitment,get_supplier_commitments,get_procurement_commitment
from app.utils.supplier_resolver import resolve_supplier_for_user

router=APIRouter(tags=["Commitments"])

@router.get("/supplier/commitment-orders")
def commitment_orders(user=Depends(require_supplier_user)):
    conn,cursor=get_db()
    try:
        supplier=resolve_supplier_for_user(cursor,user["user"]["id"])
        cursor.execute("""SELECT po.id AS purchase_order_id,po.order_number,po.order_date,po.expected_delivery_date,po.procurement_id,
                          p.title AS procurement_title,p.required_by_date,pol.id AS purchase_order_line_id,pol.quantity,pol.unit,pol.description,
                          pi.item_name,EXISTS(SELECT 1 FROM supplier_commitments sc WHERE sc.purchase_order_line_id=pol.id AND sc.status IN ('SUBMITTED','ACCEPTED')) AS has_active_commitment
                          FROM purchase_orders po JOIN procurements p ON p.id=po.procurement_id JOIN purchase_order_lines pol ON pol.purchase_order_id=po.id
                          JOIN procurement_items pi ON pi.id=pol.procurement_item_id WHERE po.supplier_id=%s AND po.status='ISSUED' AND p.status='ORDERED'
                          ORDER BY po.order_date DESC,po.id DESC,pol.id""",(supplier["id"],))
        return [dict(r) for r in cursor.fetchall()]
    finally: conn.close()

@router.post("/purchase-orders/{order_id}/commitment",status_code=201)
def submit_commitment(order_id:int,payload:SupplierCommitmentCreate,user=Depends(require_commitment_create)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            return create_commitment(cursor,user["user"]["id"],order_id,payload)
    finally: conn.close()

@router.get("/supplier/commitments")
def supplier_commitments(user=Depends(require_supplier_user)):
    conn,cursor=get_db()
    try:
        supplier=resolve_supplier_for_user(cursor,user["user"]["id"])
        return get_supplier_commitments(cursor,supplier["id"])
    finally: conn.close()

@router.get("/procurements/{procurement_id}/commitment")
def procurement_commitment(procurement_id:int,user=Depends(require_procurement_viewer)):
    conn,cursor=get_db()
    try: return get_procurement_commitment(cursor,procurement_id,user["user"]["id"])
    finally: conn.close()

@router.post("/commitments/{commitment_id}/accept")
def accept(commitment_id:int,user=Depends(require_commitment_accept)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn): return accept_commitment(cursor,commitment_id,user["user"]["id"])
    finally: conn.close()

@router.post("/commitments/{commitment_id}/reject")
def reject(commitment_id:int,payload:SupplierCommitmentReject,user=Depends(require_commitment_reject)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn): return reject_commitment(cursor,commitment_id,user["user"]["id"],payload.reason)
    finally: conn.close()
