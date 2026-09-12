from fastapi import APIRouter, Depends
from app.core.db import get_db
from app.core.dependencies import require_procurement_manager, require_procurement_viewer
from app.core.transactions import write_transaction
from app.schemas.supplier_selection_schema import SupplierSelectionCreate,SupplierReselectionCreate
from app.services.supplier_selection_service import select_supplier,reselect_supplier,get_selection_history

router=APIRouter(prefix="/procurements",tags=["Supplier Selection"])

@router.post("/{procurement_id}/selection")
def create_supplier_selection(procurement_id:int,payload:SupplierSelectionCreate,user=Depends(require_procurement_manager)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            return select_supplier(cursor,procurement_id,user["user"]["id"],payload.supplier_id,payload.decision_reason)
    finally: conn.close()

@router.post("/{procurement_id}/reselection")
def create_supplier_reselection(procurement_id:int,payload:SupplierReselectionCreate,user=Depends(require_procurement_manager)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            return reselect_supplier(cursor,procurement_id,user["user"]["id"],payload.supplier_id,payload.decision_reason)
    finally: conn.close()

@router.get("/{procurement_id}/selection-history")
def selection_history(procurement_id:int,user=Depends(require_procurement_viewer)):
    conn,cursor=get_db()
    try:
        return {"selections":[dict(r) for r in get_selection_history(cursor,procurement_id,user["user"]["id"])]}
    finally: conn.close()
