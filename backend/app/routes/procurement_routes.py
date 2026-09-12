from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.db import get_db
from app.core.dependencies import (
    require_procurement_create, require_procurement_update,
    require_procurement_submit, require_procurement_cancel,
    require_procurement_transition, require_procurement_viewer,
)
from app.core.transactions import write_transaction
from app.schemas.procurement_schema import ProcurementCreate, ProcurementUpdate, ProcurementCancel, ProcurementTransition
from app.services.procurement_service import (
    create_procurement, update_procurement, submit_procurement,
    cancel_procurement, transition_procurement,
    get_available_procurement_transitions, get_procurement_for_user,
    get_procurement_items, get_procurement_event_history,
)

router = APIRouter(prefix="/procurements", tags=["Procurements"])


@router.post("", status_code=201)
def create(payload: ProcurementCreate, user=Depends(require_procurement_create)):
    conn, cursor = get_db()
    try:
        with write_transaction(conn):
            return create_procurement(cursor, user["user"]["id"], payload)
    finally:
        conn.close()


@router.get("")
def list_procurements(status: str | None = Query(None), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), user=Depends(require_procurement_viewer)):
    conn, cursor = get_db()
    try:
        params=[user["user"]["id"]]
        query = """
    SELECT DISTINCT
        p.id,
        p.procurement_identifier,
        p.organization_id,
        o.name AS organization_name,
        p.title,
        p.status,
        p.procurement_date,
        p.required_by_date,
        p.location,
        p.estimated_cost,
        p.procurement_method,
        p.created_at,
        p.updated_at

    FROM procurements p

    JOIN organizations o
        ON o.id = p.organization_id

    JOIN organization_memberships om
        ON om.organization_id = p.organization_id

    WHERE om.user_id = %s

      AND om.status = 'ACTIVE'

      AND o.status = 'ACTIVE'

      AND o.verification_status = 'VERIFIED'

      AND o.organization_type = 'SCHOOL'
"""
        if status:
            query += " AND p.status=%s"; params.append(status.upper())
        query += " ORDER BY p.created_at DESC,p.id DESC LIMIT %s OFFSET %s"; params.extend([limit,offset])
        cursor.execute(query,tuple(params))
        return {"procurements":[dict(r) for r in cursor.fetchall()]}
    finally:
        conn.close()


@router.get("/{procurement_id}")
def get_detail(procurement_id:int,user=Depends(require_procurement_viewer)):
    conn,cursor=get_db()
    try:
        procurement=get_procurement_for_user(cursor,procurement_id,user["user"]["id"])
        if not procurement: raise HTTPException(404,"Procurement not found.")
        items=get_procurement_items(cursor,procurement_id)
        events=get_procurement_event_history(cursor,procurement_id,user["user"]["id"])
        cursor.execute("""SELECT po.*,s.supplier_code,o.name AS supplier_name FROM purchase_orders po
                          JOIN suppliers s ON s.id=po.supplier_id JOIN organizations o ON o.id=s.organization_id
                          WHERE po.procurement_id=%s""",(procurement_id,))
        po=cursor.fetchone()
        evidence=[]
        cursor.execute("""SELECT id,event_id,document_type,document_name,original_filename,mime_type,file_size,visibility,uploaded_by,uploaded_at
                          FROM evidence_documents WHERE procurement_id=%s AND deleted_at IS NULL ORDER BY uploaded_at DESC""",(procurement_id,))
        evidence=cursor.fetchall()
        return {"procurement":dict(procurement),"items":[dict(i) for i in items],"events":[dict(e) for e in events],"purchase_order":dict(po) if po else None,"evidence":[dict(e) for e in evidence]}
    finally:
        conn.close()


@router.put("/{procurement_id}")
def update(procurement_id:int,payload:ProcurementUpdate,user=Depends(require_procurement_update)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            return update_procurement(cursor,procurement_id,user["user"]["id"],payload)
    finally: conn.close()


@router.post("/{procurement_id}/submit")
def submit(procurement_id:int,user=Depends(require_procurement_submit)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            return submit_procurement(cursor,procurement_id,user["user"]["id"])
    finally: conn.close()


@router.post("/{procurement_id}/cancel")
def cancel(procurement_id:int,payload:ProcurementCancel,user=Depends(require_procurement_cancel)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            return cancel_procurement(cursor,procurement_id,user["user"]["id"],payload.reason)
    finally: conn.close()


@router.post("/{procurement_id}/transition")
def transition(procurement_id:int,payload:ProcurementTransition,user=Depends(require_procurement_transition)):
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            return transition_procurement(cursor,procurement_id,user["user"]["id"],payload.status,payload.reason)
    finally: conn.close()


@router.get("/{procurement_id}/transitions")
def available_transitions(procurement_id:int,user=Depends(require_procurement_viewer)):
    conn,cursor=get_db()
    try:
        procurement=get_procurement_for_user(cursor,procurement_id,user["user"]["id"])
        if not procurement: raise HTTPException(404,"Procurement not found.")
        return {"status":procurement["status"],"available_transitions":get_available_procurement_transitions(procurement["status"])}
    finally: conn.close()
