from fastapi import APIRouter, Depends
from app.core.db import get_db
from app.core.dependencies import require_supplier_evaluation, require_procurement_viewer
from app.core.transactions import write_transaction
from app.services.procurement_service import enter_supplier_evaluation
from app.services.supplier_evaluation_service import get_supplier_candidates,evaluate_all_suppliers

router=APIRouter(prefix="/procurements",tags=["Supplier Evaluation"])

@router.post("/{procurement_id}/enter-evaluation")
def enter_evaluation(procurement_id:int,user=Depends(require_supplier_evaluation)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            return enter_supplier_evaluation(cursor,procurement_id,user["user"]["id"])
    finally: conn.close()

@router.post("/{procurement_id}/supplier-evaluation")
def evaluate_suppliers(procurement_id:int,user=Depends(require_supplier_evaluation)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            result=evaluate_all_suppliers(cursor,procurement_id,user["user"]["id"])
            return {"procurement":dict(result["procurement"]),"evaluations":[dict(e) for e in result["evaluations"]]}
    finally: conn.close()

@router.get("/{procurement_id}/supplier-candidates")
def candidates(procurement_id:int,user=Depends(require_procurement_viewer)):
    conn,cursor=get_db()
    try:
        result=get_supplier_candidates(cursor,procurement_id,user["user"]["id"])
        return {"procurement":dict(result["procurement"]),"candidates":[dict(r) for r in result["candidates"]]}
    finally: conn.close()
