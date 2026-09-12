from decimal import Decimal
from fastapi import HTTPException
from app.models.procurement_events import record_audit_event, record_procurement_event
from app.services.procurement_service import transition_procurement


def _load_commitment_for_school(cursor, commitment_id, user_id, for_update=False):
    lock=" FOR UPDATE" if for_update else ""
    cursor.execute(f"""SELECT sc.*,po.procurement_id,po.supplier_id AS po_supplier_id,p.status AS procurement_status,
                              p.organization_id
                       FROM supplier_commitments sc JOIN purchase_orders po ON po.id=sc.purchase_order_id
                       JOIN procurements p ON p.id=po.procurement_id
                       JOIN organization_memberships om ON om.organization_id=p.organization_id
                       WHERE sc.id=%s AND om.user_id=%s AND om.status='ACTIVE'{lock}""",(commitment_id,user_id))
    return cursor.fetchone()


def create_delivery(cursor,user_id,payload):
    cursor.execute("""SELECT po.procurement_id FROM supplier_commitments sc JOIN purchase_orders po ON po.id=sc.purchase_order_id WHERE sc.id=%s""",(payload.commitment_id,))
    ref=cursor.fetchone()
    if not ref: raise HTTPException(404,"Commitment not found.")
    cursor.execute("""SELECT p.* FROM procurements p JOIN organization_memberships om ON om.organization_id=p.organization_id
                      WHERE p.id=%s AND om.user_id=%s AND om.status='ACTIVE' FOR UPDATE""",(ref["procurement_id"],user_id))
    procurement=cursor.fetchone()
    if not procurement: raise HTTPException(404,"Commitment not found.")
    commitment=_load_commitment_for_school(cursor,payload.commitment_id,user_id,for_update=True)
    if not commitment: raise HTTPException(404,"Commitment not found.")
    if commitment["status"]!="ACCEPTED": raise HTTPException(409,"A delivery can only be recorded against an accepted commitment.")
    if commitment["procurement_status"] not in {"COMMITTED","DELIVERY","INSPECTION"}: raise HTTPException(409,"The procurement is not in a delivery stage.")

    parent_id=payload.parent_delivery_id
    if parent_id is not None:
        cursor.execute("SELECT id,commitment_id,delivery_status FROM deliveries WHERE id=%s FOR UPDATE",(parent_id,))
        parent=cursor.fetchone()
        if not parent or parent["commitment_id"]!=payload.commitment_id: raise HTTPException(400,"The replacement delivery must belong to the same commitment.")
        if parent["delivery_status"]!="REJECTED": raise HTTPException(409,"A replacement delivery can only follow a rejected delivery.")

    cursor.execute("SELECT COALESCE(MAX(delivery_sequence),0)+1 AS next_sequence FROM deliveries WHERE commitment_id=%s",(payload.commitment_id,))
    sequence=cursor.fetchone()["next_sequence"]
    cursor.execute("""INSERT INTO deliveries(commitment_id,parent_delivery_id,delivery_sequence,delivery_date,condition,notes,receiving_user_id)
                      VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *""",(payload.commitment_id,parent_id,sequence,payload.delivery_date,payload.condition,payload.notes,user_id))
    delivery=cursor.fetchone()
    seen=set()
    for line in payload.lines:
        if line.procurement_item_id in seen: raise HTTPException(400,"The same procurement item cannot appear twice in a delivery.")
        seen.add(line.procurement_item_id)
        cursor.execute("""SELECT pi.id,pi.quantity FROM procurement_items pi JOIN purchase_order_lines pol ON pol.procurement_item_id=pi.id
                          WHERE pi.id=%s AND pol.purchase_order_id=%s AND pol.id=%s""",(line.procurement_item_id,commitment["purchase_order_id"],commitment["purchase_order_line_id"]))
        item=cursor.fetchone()
        if not item: raise HTTPException(400,"A delivery line does not belong to the committed purchase order line.")
        cursor.execute("INSERT INTO delivery_lines(delivery_id,procurement_item_id,actual_quantity) VALUES(%s,%s,%s)",(delivery["id"],line.procurement_item_id,line.actual_quantity))

    if parent_id is not None:
        cursor.execute("""UPDATE corrective_actions SET status='COMPLETED',replacement_delivery_id=%s,completed_at=CURRENT_TIMESTAMP
                          WHERE inspection_id IN (SELECT id FROM inspections WHERE delivery_id=%s) AND status='OPEN'""",(delivery["id"],parent_id))
    if commitment["procurement_status"]=="COMMITTED": transition_procurement(cursor,commitment["procurement_id"],user_id,"DELIVERY","Physical delivery recorded.")
    record_procurement_event(cursor,commitment["procurement_id"],"DELIVERY_RECORDED",user_id,"delivery",delivery["id"],"Physical delivery recorded.",{"delivery_sequence":sequence,"parent_delivery_id":parent_id})
    record_audit_event(cursor,commitment["procurement_id"],user_id,"CREATE_DELIVERY","delivery",delivery["id"],None,{"delivery_status":"AWAITING_INSPECTION","delivery_sequence":sequence})
    return get_delivery(cursor,delivery["id"],user_id)


def get_delivery(cursor,delivery_id,user_id):
    cursor.execute("""SELECT d.*,sc.purchase_order_id,sc.purchase_order_line_id,sc.supplier_id,
                              po.procurement_id,p.organization_id,p.status AS procurement_status
                       FROM deliveries d JOIN supplier_commitments sc ON sc.id=d.commitment_id
                       JOIN purchase_orders po ON po.id=sc.purchase_order_id JOIN procurements p ON p.id=po.procurement_id
                       JOIN organization_memberships om ON om.organization_id=p.organization_id
                       WHERE d.id=%s AND om.user_id=%s AND om.status='ACTIVE'""",(delivery_id,user_id))
    delivery=cursor.fetchone()
    if not delivery: raise HTTPException(404,"Delivery not found.")
    cursor.execute("SELECT dl.id,dl.procurement_item_id,pi.item_name,pi.unit,dl.actual_quantity FROM delivery_lines dl JOIN procurement_items pi ON pi.id=dl.procurement_item_id WHERE dl.delivery_id=%s ORDER BY dl.id",(delivery_id,))
    result=dict(delivery); result["lines"]=[dict(r) for r in cursor.fetchall()]
    return result


def get_procurement_deliveries(cursor,procurement_id,user_id):
    cursor.execute("""SELECT d.id,d.commitment_id,d.delivery_sequence,d.delivery_date,d.condition,d.notes,d.receiving_user_id,d.delivery_status,d.created_at,d.updated_at
                       FROM deliveries d JOIN supplier_commitments sc ON sc.id=d.commitment_id JOIN purchase_orders po ON po.id=sc.purchase_order_id
                       JOIN procurements p ON p.id=po.procurement_id JOIN organization_memberships om ON om.organization_id=p.organization_id
                       WHERE po.procurement_id=%s AND om.user_id=%s AND om.status='ACTIVE' ORDER BY d.delivery_sequence,d.id""",(procurement_id,user_id))
    return [dict(r) for r in cursor.fetchall()]
