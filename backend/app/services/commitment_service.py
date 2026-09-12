from fastapi import HTTPException
from app.models.procurement_events import record_audit_event, record_procurement_event
from app.services.procurement_service import transition_procurement


def _supplier_for_user(cursor,user_id):
    cursor.execute("""SELECT s.id,s.organization_id,s.status,o.name AS supplier_name,o.status AS organization_status,o.verification_status
                      FROM suppliers s JOIN organizations o ON o.id=s.organization_id
                      JOIN organization_memberships om ON om.organization_id=s.organization_id
                      WHERE om.user_id=%s AND om.status='ACTIVE' AND o.organization_type='SUPPLIER' LIMIT 1""",(user_id,))
    row=cursor.fetchone()
    if not row: raise HTTPException(403,"The current user is not associated with an active supplier organization.")
    if row["verification_status"] != "VERIFIED": raise HTTPException(403,"The supplier organization must be verified before submitting commitments.")
    return row


def get_order_line_for_supplier(cursor, order_id, line_id, supplier_id, for_update=False):
    lock=" FOR UPDATE" if for_update else ""
    cursor.execute(f"""SELECT po.id AS purchase_order_id,po.procurement_id,po.supplier_id,po.status AS po_status,
                              pol.id AS purchase_order_line_id,pol.quantity,pol.unit,pi.id AS procurement_item_id,pi.item_name,
                              p.status AS procurement_status,p.organization_id
                       FROM purchase_orders po JOIN purchase_order_lines pol ON pol.purchase_order_id=po.id
                       JOIN procurement_items pi ON pi.id=pol.procurement_item_id JOIN procurements p ON p.id=po.procurement_id
                       WHERE po.id=%s AND pol.id=%s AND po.supplier_id=%s{lock}""",(order_id,line_id,supplier_id))
    return cursor.fetchone()


def create_commitment(cursor,user_id,order_id,payload):
    supplier=_supplier_for_user(cursor,user_id)
    line=get_order_line_for_supplier(cursor,order_id,payload.purchase_order_line_id,supplier["id"],for_update=True)
    if not line: raise HTTPException(404,"Purchase order line not found for this supplier.")
    if line["po_status"]!="ISSUED" or line["procurement_status"]!="ORDERED": raise HTTPException(409,"Only an issued purchase order for an ORDERED procurement can receive a commitment.")
    if payload.promised_qty>line["quantity"]: raise HTTPException(409,"Committed quantity cannot exceed the purchase order line quantity.")

    cursor.execute("""SELECT id FROM supplier_commitments WHERE purchase_order_line_id=%s AND supplier_id=%s
                      AND status IN ('SUBMITTED','ACCEPTED') FOR UPDATE""",(line["purchase_order_line_id"],supplier["id"]))
    if cursor.fetchone(): raise HTTPException(409,"An active commitment already exists for this purchase order line and supplier.")

    cursor.execute("""INSERT INTO supplier_commitments
        (purchase_order_id,purchase_order_line_id,supplier_id,promised_qty,delivery_start,delivery_end,status,submitted_by)
        VALUES(%s,%s,%s,%s,%s,%s,'SUBMITTED',%s) RETURNING *""",
        (order_id,line["purchase_order_line_id"],supplier["id"],payload.promised_qty,payload.delivery_start,payload.delivery_end,user_id))
    commitment=cursor.fetchone()
    record_procurement_event(cursor,line["procurement_id"],"COMMITMENT_SUBMITTED",user_id,"supplier_commitment",commitment["id"],"Supplier commitment submitted.",{"promised_qty":str(payload.promised_qty),"delivery_start":str(payload.delivery_start),"delivery_end":str(payload.delivery_end)})
    record_audit_event(cursor,line["procurement_id"],user_id,"CREATE_COMMITMENT","supplier_commitment",commitment["id"],None,{"status":"SUBMITTED","promised_qty":str(payload.promised_qty)})
    return {"created":True,"commitment_id":commitment["id"],"status":"SUBMITTED","procurement_id":line["procurement_id"]}


def accept_commitment(cursor,commitment_id,user_id):
    cursor.execute("SELECT po.procurement_id FROM supplier_commitments sc JOIN purchase_orders po ON po.id=sc.purchase_order_id WHERE sc.id=%s",(commitment_id,))
    ref=cursor.fetchone()
    if not ref: raise HTTPException(404,"Commitment not found.")
    cursor.execute("""SELECT p.* FROM procurements p JOIN organization_memberships om ON om.organization_id=p.organization_id
                      WHERE p.id=%s AND om.user_id=%s AND om.status='ACTIVE' FOR UPDATE""",(ref["procurement_id"],user_id))
    procurement=cursor.fetchone()
    if not procurement: raise HTTPException(404,"Commitment not found.")
    cursor.execute("""SELECT sc.*,po.procurement_id,po.supplier_id AS po_supplier_id,p.status AS procurement_status
                      FROM supplier_commitments sc JOIN purchase_orders po ON po.id=sc.purchase_order_id
                      JOIN procurements p ON p.id=po.procurement_id
                      WHERE sc.id=%s AND p.id=%s FOR UPDATE""",(commitment_id,ref["procurement_id"]))
    commitment=cursor.fetchone()
    if commitment["status"]!="SUBMITTED": raise HTTPException(409,"Only submitted commitments can be accepted.")
    if commitment["procurement_status"]!="ORDERED": raise HTTPException(409,"The procurement must be ORDERED before a commitment can be accepted.")
    cursor.execute("UPDATE supplier_commitments SET status='ACCEPTED',accepted_by=%s,accepted_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=%s RETURNING *",(user_id,commitment_id))
    accepted=cursor.fetchone()
    record_procurement_event(cursor,commitment["procurement_id"],"COMMITMENT_ACCEPTED",user_id,"supplier_commitment",commitment_id,"Supplier commitment accepted.",{"promised_qty":str(accepted["promised_qty"])})
    record_audit_event(cursor,commitment["procurement_id"],user_id,"ACCEPT_COMMITMENT","supplier_commitment",commitment_id,{"status":"SUBMITTED"},{"status":"ACCEPTED"})
    cursor.execute("SELECT COUNT(*) AS accepted FROM supplier_commitments WHERE purchase_order_id=%s AND status='ACCEPTED'",(commitment["purchase_order_id"],))
    accepted_count=cursor.fetchone()["accepted"]
    cursor.execute("SELECT COUNT(*) AS lines FROM purchase_order_lines WHERE purchase_order_id=%s",(commitment["purchase_order_id"],))
    line_count=cursor.fetchone()["lines"]
    if accepted_count==line_count:
        transition_procurement(cursor,commitment["procurement_id"],user_id,"COMMITTED","All purchase order lines have accepted commitments.")
    return {"commitment":accepted,"procurement_status":"COMMITTED" if accepted_count==line_count else "ORDERED"}


def reject_commitment(cursor,commitment_id,user_id,reason):
    cursor.execute("SELECT po.procurement_id FROM supplier_commitments sc JOIN purchase_orders po ON po.id=sc.purchase_order_id WHERE sc.id=%s",(commitment_id,))
    ref=cursor.fetchone()
    if not ref: raise HTTPException(404,"Commitment not found.")
    cursor.execute("""SELECT p.id FROM procurements p JOIN organization_memberships om ON om.organization_id=p.organization_id
                      WHERE p.id=%s AND om.user_id=%s AND om.status='ACTIVE' FOR UPDATE""",(ref["procurement_id"],user_id))
    if not cursor.fetchone(): raise HTTPException(404,"Commitment not found.")
    cursor.execute("""SELECT sc.*,po.procurement_id,p.status AS procurement_status FROM supplier_commitments sc
                      JOIN purchase_orders po ON po.id=sc.purchase_order_id JOIN procurements p ON p.id=po.procurement_id
                      WHERE sc.id=%s AND p.id=%s FOR UPDATE""",(commitment_id,ref["procurement_id"]))
    commitment=cursor.fetchone()
    if commitment["status"]!="SUBMITTED": raise HTTPException(409,"Only submitted commitments can be rejected.")
    cursor.execute("UPDATE supplier_commitments SET status='REJECTED',rejected_by=%s,rejected_at=CURRENT_TIMESTAMP,rejection_reason=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s RETURNING *",(user_id,reason,commitment_id))
    rejected=cursor.fetchone()
    record_procurement_event(cursor,commitment["procurement_id"],"COMMITMENT_REJECTED",user_id,"supplier_commitment",commitment_id,"Supplier commitment rejected.",{"reason":reason})
    record_audit_event(cursor,commitment["procurement_id"],user_id,"REJECT_COMMITMENT","supplier_commitment",commitment_id,{"status":"SUBMITTED"},{"status":"REJECTED","reason":reason})
    return {"commitment":rejected,"status":"REJECTED"}


def get_supplier_commitments(cursor,supplier_id):
    cursor.execute("""SELECT sc.*,po.order_number,po.procurement_id,p.title AS procurement_title,pi.item_name,pi.unit,
                              o.name AS supplier_name
                       FROM supplier_commitments sc JOIN purchase_orders po ON po.id=sc.purchase_order_id
                       JOIN procurements p ON p.id=po.procurement_id JOIN purchase_order_lines pol ON pol.id=sc.purchase_order_line_id
                       JOIN procurement_items pi ON pi.id=pol.procurement_item_id JOIN suppliers s ON s.id=sc.supplier_id
                       JOIN organizations o ON o.id=s.organization_id
                       WHERE sc.supplier_id=%s ORDER BY sc.id DESC""",(supplier_id,))
    return [dict(r) for r in cursor.fetchall()]


def get_procurement_commitment(cursor,procurement_id,user_id):
    cursor.execute("""SELECT sc.*,po.order_number,po.procurement_id,pi.item_name,pi.unit,s.supplier_code,o.name AS supplier_name
                       FROM supplier_commitments sc JOIN purchase_orders po ON po.id=sc.purchase_order_id
                       JOIN purchase_order_lines pol ON pol.id=sc.purchase_order_line_id JOIN procurement_items pi ON pi.id=pol.procurement_item_id
                       JOIN suppliers s ON s.id=sc.supplier_id JOIN organizations o ON o.id=s.organization_id
                       JOIN procurements p ON p.id=po.procurement_id JOIN organization_memberships om ON om.organization_id=p.organization_id
                       WHERE po.procurement_id=%s AND om.user_id=%s AND om.status='ACTIVE' ORDER BY sc.id DESC""",(procurement_id,user_id))
    return [dict(r) for r in cursor.fetchall()]
