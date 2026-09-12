from fastapi import HTTPException
from app.models.procurement_events import record_audit_event, record_procurement_event


def _lock_procurement(cursor, procurement_id, user_id):
    cursor.execute(
        """SELECT p.* FROM procurements p JOIN organization_memberships om ON om.organization_id=p.organization_id
           WHERE p.id=%s AND om.user_id=%s AND om.status='ACTIVE' FOR UPDATE""",
        (procurement_id,user_id),
    )
    row=cursor.fetchone()
    if not row: raise HTTPException(404,"Procurement not found.")
    return row


def get_selection_decisions(cursor, procurement_id, user_id=None):
    if user_id is not None: _lock = _lock_procurement(cursor, procurement_id, user_id)
    cursor.execute("""SELECT d.*,u.name AS decided_by_name,o.name AS supplier_name
                      FROM supplier_selection_decisions d
                      JOIN users u ON u.id=d.decided_by
                      JOIN suppliers s ON s.id=d.supplier_id
                      JOIN organizations o ON o.id=s.organization_id
                      WHERE d.procurement_id=%s ORDER BY d.decision_sequence""",(procurement_id,))
    return cursor.fetchall()


def get_latest_selection_decision(cursor, procurement_id):
    cursor.execute("SELECT * FROM supplier_selection_decisions WHERE procurement_id=%s ORDER BY decision_sequence DESC LIMIT 1",(procurement_id,))
    return cursor.fetchone()


def get_supplier_evaluation(cursor, procurement_id, supplier_id):
    cursor.execute("SELECT * FROM supplier_evaluations WHERE procurement_id=%s AND supplier_id=%s",(procurement_id,supplier_id))
    return cursor.fetchone()


def _supplier(cursor, supplier_id):
    cursor.execute("""SELECT s.*,o.name AS supplier_name,o.status AS organization_status,o.verification_status
                      FROM suppliers s JOIN organizations o ON o.id=s.organization_id WHERE s.id=%s""",(supplier_id,))
    return cursor.fetchone()


def build_evaluation_snapshot(evaluation, procurement):
    return {k:evaluation.get(k) for k in (
        "supplier_id","evaluation_status","required_item_match","mandatory_eligible",
        "verification_status","capacity_status","historical_evidence_status",
        "historical_delivery_count","historical_commitment_count","fulfilled_quantity",
        "promised_quantity","fulfilment_rate","on_time_delivery_rate",
        "quantity_variance_rate","quality_acceptance_rate","indicator_explanation")}


def select_supplier(cursor, procurement_id, user_id, supplier_id, decision_reason):
    procurement=_lock_procurement(cursor,procurement_id,user_id)
    if procurement["status"]!="EVALUATION": raise HTTPException(409,"Supplier selection is only allowed while the procurement is in EVALUATION.")
    evaluation=get_supplier_evaluation(cursor,procurement_id,supplier_id)
    if not evaluation: raise HTTPException(404,"The selected supplier has not been evaluated for this procurement.")
    if not evaluation["mandatory_eligible"]: raise HTTPException(409,"The supplier is not eligible for human selection.")
    supplier=_supplier(cursor,supplier_id)
    if not supplier: raise HTTPException(404,"Supplier not found.")
    cursor.execute("SELECT COALESCE(MAX(decision_sequence),0)+1 AS next_sequence FROM supplier_selection_decisions WHERE procurement_id=%s",(procurement_id,))
    next_sequence=cursor.fetchone()["next_sequence"]
    cursor.execute("""INSERT INTO supplier_selection_decisions
        (procurement_id,supplier_id,decision_sequence,decision_type,decision_reason,evaluation_snapshot,decided_by)
        VALUES(%s,%s,%s,'INITIAL_SELECTION',%s,%s::jsonb,%s) RETURNING id""",
        (procurement_id,supplier_id,next_sequence,decision_reason.strip(),__import__('json').dumps(build_evaluation_snapshot(evaluation,procurement),default=str),user_id))
    decision=cursor.fetchone()
    cursor.execute("UPDATE procurements SET status='SELECTED',updated_at=CURRENT_TIMESTAMP WHERE id=%s",(procurement_id,))
    record_procurement_event(cursor,procurement_id,"SUPPLIER_SELECTED",user_id,"supplier_selection_decision",decision["id"],"Supplier selected.",{"supplier_id":supplier_id,"decision_sequence":next_sequence})
    record_audit_event(cursor,procurement_id,user_id,"SELECT_SUPPLIER","supplier_selection_decision",decision["id"],{"status":"EVALUATION"},{"status":"SELECTED","supplier_id":supplier_id})
    return {"decision_id":decision["id"],"procurement_id":procurement_id,"supplier_id":supplier_id,"decision_sequence":next_sequence,"decision_type":"INITIAL_SELECTION","status":"SELECTED"}


def reselect_supplier(cursor, procurement_id, user_id, supplier_id, decision_reason):
    procurement=_lock_procurement(cursor,procurement_id,user_id)
    if procurement["status"]!="SELECTED": raise HTTPException(409,"Controlled reselection is only allowed after a supplier has already been selected.")
    previous=get_latest_selection_decision(cursor,procurement_id)
    if not previous: raise HTTPException(409,"No previous supplier selection decision exists.")
    if previous["supplier_id"]==supplier_id: raise HTTPException(409,"The new supplier must be different from the current selected supplier.")
    evaluation=get_supplier_evaluation(cursor,procurement_id,supplier_id)
    if not evaluation: raise HTTPException(404,"The new supplier has not been evaluated for this procurement.")
    if not evaluation["mandatory_eligible"]: raise HTTPException(409,"The new supplier is not eligible for selection.")
    supplier=_supplier(cursor,supplier_id)
    if not supplier: raise HTTPException(404,"Supplier not found.")
    next_sequence=previous["decision_sequence"]+1
    cursor.execute("""INSERT INTO supplier_selection_decisions
        (procurement_id,supplier_id,decision_sequence,decision_type,decision_reason,evaluation_snapshot,supersedes_decision_id,decided_by)
        VALUES(%s,%s,%s,'RESELECTION',%s,%s::jsonb,%s,%s) RETURNING id""",
        (procurement_id,supplier_id,next_sequence,decision_reason.strip(),__import__('json').dumps(build_evaluation_snapshot(evaluation,procurement),default=str),previous["id"],user_id))
    decision=cursor.fetchone()
    record_procurement_event(cursor,procurement_id,"SUPPLIER_SELECTED",user_id,"supplier_selection_decision",decision["id"],"Supplier reselected.",{"supplier_id":supplier_id,"decision_sequence":next_sequence,"supersedes_decision_id":previous["id"]})
    record_audit_event(cursor,procurement_id,user_id,"RESELECT_SUPPLIER","supplier_selection_decision",decision["id"],{"supplier_id":previous["supplier_id"]},{"supplier_id":supplier_id})
    return {"decision_id":decision["id"],"procurement_id":procurement_id,"supplier_id":supplier_id,"decision_sequence":next_sequence,"decision_type":"RESELECTION","supersedes_decision_id":previous["id"],"status":"SELECTED"}


def get_selection_history(cursor, procurement_id, user_id):
    _lock_procurement(cursor,procurement_id,user_id)
    cursor.execute("SELECT * FROM supplier_selection_decisions WHERE procurement_id=%s ORDER BY decision_sequence",(procurement_id,))
    return cursor.fetchall()
