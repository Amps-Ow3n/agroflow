from fastapi import HTTPException
from app.models.procurement_events import record_audit_event, record_procurement_event
from app.services.procurement_service import transition_procurement


def _delivery_for_school(cursor,delivery_id,user_id,for_update=False):
    lock=" FOR UPDATE" if for_update else ""
    cursor.execute(f"""SELECT d.*,sc.purchase_order_id,sc.purchase_order_line_id,sc.supplier_id,sc.promised_qty,
                              po.procurement_id,p.status AS procurement_status,p.organization_id
                       FROM deliveries d JOIN supplier_commitments sc ON sc.id=d.commitment_id
                       JOIN purchase_orders po ON po.id=sc.purchase_order_id JOIN procurements p ON p.id=po.procurement_id
                       JOIN organization_memberships om ON om.organization_id=p.organization_id
                       WHERE d.id=%s AND om.user_id=%s AND om.status='ACTIVE'{lock}""",(delivery_id,user_id))
    return cursor.fetchone()


def _accepted_quantity_for_procurement(cursor,procurement_id):
    cursor.execute("""SELECT pol.id,pol.quantity,COALESCE(SUM(CASE WHEN d.delivery_status='ACCEPTED' THEN dl.actual_quantity ELSE 0 END),0) AS accepted
                       FROM purchase_orders po JOIN purchase_order_lines pol ON pol.purchase_order_id=po.id
                       LEFT JOIN supplier_commitments sc ON sc.purchase_order_line_id=pol.id
                       LEFT JOIN deliveries d ON d.commitment_id=sc.id
                       LEFT JOIN delivery_lines dl ON dl.delivery_id=d.id AND dl.procurement_item_id=pol.procurement_item_id
                       WHERE po.procurement_id=%s GROUP BY pol.id,pol.quantity""",(procurement_id,))
    rows=cursor.fetchall()
    return bool(rows) and all(row["accepted"] >= row["quantity"] for row in rows)


def inspect_delivery(cursor,delivery_id,user_id,payload):
    cursor.execute("""SELECT po.procurement_id FROM deliveries d JOIN supplier_commitments sc ON sc.id=d.commitment_id
                      JOIN purchase_orders po ON po.id=sc.purchase_order_id WHERE d.id=%s""",(delivery_id,))
    ref=cursor.fetchone()
    if not ref: raise HTTPException(404,"Delivery not found.")
    cursor.execute("""SELECT p.* FROM procurements p JOIN organization_memberships om ON om.organization_id=p.organization_id
                      WHERE p.id=%s AND om.user_id=%s AND om.status='ACTIVE' FOR UPDATE""",(ref["procurement_id"],user_id))
    procurement=cursor.fetchone()
    if not procurement: raise HTTPException(404,"Delivery not found.")
    delivery=_delivery_for_school(cursor,delivery_id,user_id,for_update=True)
    if not delivery: raise HTTPException(404,"Delivery not found.")
    if delivery["delivery_status"]!="AWAITING_INSPECTION": raise HTTPException(409,"Only deliveries awaiting inspection can be inspected.")
    cursor.execute("SELECT id FROM inspections WHERE delivery_id=%s",(delivery_id,))
    if cursor.fetchone(): raise HTTPException(409,"This delivery has already been inspected.")
    cursor.execute("SELECT COALESCE(SUM(actual_quantity),0) AS actual FROM delivery_lines WHERE delivery_id=%s",(delivery_id,))
    actual=cursor.fetchone()["actual"]
    if payload.received_qty>actual: raise HTTPException(409,"Received quantity cannot exceed the actual quantity recorded on the delivery lines.")
    cursor.execute("""INSERT INTO inspections(delivery_id,result,received_qty,quality_status,delay_status,rejection_reason,notes,inspected_by)
                      VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",(delivery_id,payload.result,payload.received_qty,payload.quality_status,payload.delay_status,payload.rejection_reason,payload.notes,user_id))
    inspection=cursor.fetchone()
    cursor.execute("UPDATE deliveries SET delivery_status=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s RETURNING *",(payload.result,delivery_id))
    updated=cursor.fetchone()
    event="GOODS_ACCEPTED" if payload.result=="ACCEPTED" else "GOODS_REJECTED"
    record_procurement_event(cursor,delivery["procurement_id"],event,user_id,"inspection",inspection["id"],"Inspection completed.",{"result":payload.result})
    record_audit_event(cursor,delivery["procurement_id"],user_id,"INSPECT_DELIVERY","inspection",inspection["id"],{"delivery_status":"AWAITING_INSPECTION"},{"delivery_status":payload.result,"result":payload.result})
    transition=None
    if payload.result=="ACCEPTED":
        if procurement["status"]=="DELIVERY": transition=transition_procurement(cursor,delivery["procurement_id"],user_id,"INSPECTION","Delivery entered inspection.")
        if _accepted_quantity_for_procurement(cursor,delivery["procurement_id"]):
            current="INSPECTION" if transition else procurement["status"]
            if current=="INSPECTION": transition=transition_procurement(cursor,delivery["procurement_id"],user_id,"ACCEPTED","All ordered quantities have been accepted.")
    return {"inspection":inspection,"delivery":updated,"procurement_transition":transition}


def create_corrective_action(cursor,inspection_id,user_id,payload):
    cursor.execute("""SELECT i.*,d.commitment_id,d.delivery_status,po.procurement_id,p.organization_id
                      FROM inspections i JOIN deliveries d ON d.id=i.delivery_id JOIN supplier_commitments sc ON sc.id=d.commitment_id
                      JOIN purchase_orders po ON po.id=sc.purchase_order_id JOIN procurements p ON p.id=po.procurement_id
                      JOIN organization_memberships om ON om.organization_id=p.organization_id
                      WHERE i.id=%s AND om.user_id=%s AND om.status='ACTIVE' FOR UPDATE""",(inspection_id,user_id))
    inspection=cursor.fetchone()
    if not inspection: raise HTTPException(404,"Inspection not found.")
    if inspection["result"]!="REJECTED" or inspection["delivery_status"]!="REJECTED": raise HTTPException(409,"Corrective action can only follow a rejected inspection.")
    cursor.execute("SELECT id FROM corrective_actions WHERE inspection_id=%s",(inspection_id,))
    if cursor.fetchone(): raise HTTPException(409,"A corrective action already exists for this inspection.")
    cursor.execute("INSERT INTO corrective_actions(inspection_id,description,status,created_by) VALUES(%s,%s,'OPEN',%s) RETURNING *",(inspection_id,payload.description,user_id))
    action=cursor.fetchone()
    record_procurement_event(cursor,inspection["procurement_id"],"GOODS_REJECTED",user_id,"corrective_action",action["id"],"Corrective action opened after rejected inspection.")
    record_audit_event(cursor,inspection["procurement_id"],user_id,"CREATE_CORRECTIVE_ACTION","corrective_action",action["id"],None,{"status":"OPEN","inspection_id":inspection_id})
    return {"corrective_action":action,"replacement_delivery_id":None}


def get_delivery_history(cursor,delivery_id,user_id):
    delivery=_delivery_for_school(cursor,delivery_id,user_id)
    if not delivery: raise HTTPException(404,"Delivery not found.")
    cursor.execute("""SELECT i.*,u.name AS inspected_by_name FROM inspections i JOIN users u ON u.id=i.inspected_by WHERE i.delivery_id=%s""",(delivery_id,))
    inspection=cursor.fetchone()
    cursor.execute("SELECT * FROM corrective_actions WHERE inspection_id=%s",(inspection["id"] if inspection else -1,))
    action=cursor.fetchone()
    return {"delivery":delivery,"inspection":inspection,"corrective_action":action}


def get_procurement_inspection_history(cursor,procurement_id,user_id):
    cursor.execute("""SELECT d.id AS delivery_id,d.commitment_id,d.delivery_sequence,d.delivery_date,d.condition,d.delivery_status,
                              i.id AS inspection_id,i.result,i.received_qty,i.quality_status,i.delay_status,i.rejection_reason,i.notes,i.inspected_by,i.inspected_at
                       FROM deliveries d JOIN supplier_commitments sc ON sc.id=d.commitment_id JOIN purchase_orders po ON po.id=sc.purchase_order_id
                       JOIN procurements p ON p.id=po.procurement_id JOIN organization_memberships om ON om.organization_id=p.organization_id
                       LEFT JOIN inspections i ON i.delivery_id=d.id
                       WHERE po.procurement_id=%s AND om.user_id=%s AND om.status='ACTIVE' ORDER BY d.delivery_sequence,d.id""",(procurement_id,user_id))
    return [dict(r) for r in cursor.fetchall()]
