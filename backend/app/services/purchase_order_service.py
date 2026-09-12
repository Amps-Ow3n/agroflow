from decimal import Decimal
from fastapi import HTTPException

from app.models.procurement_events import record_audit_event
from app.services.procurement_service import transition_procurement


def create_purchase_order(cursor, procurement_id, user_id, payload):
    cursor.execute(
        """SELECT p.* FROM procurements p JOIN organization_memberships om ON om.organization_id=p.organization_id
           WHERE p.id=%s AND om.user_id=%s AND om.status='ACTIVE' FOR UPDATE""",
        (procurement_id,user_id),
    )
    procurement=cursor.fetchone()
    if not procurement: raise HTTPException(404,"Procurement not found.")
    if procurement["status"]!="SELECTED": raise HTTPException(409,"A purchase order can only be created for a SELECTED procurement.")

    cursor.execute("""SELECT d.supplier_id,s.supplier_code,o.name AS supplier_name
                      FROM supplier_selection_decisions d
                      JOIN suppliers s ON s.id=d.supplier_id
                      JOIN organizations o ON o.id=s.organization_id
                      WHERE d.procurement_id=%s ORDER BY d.decision_sequence DESC LIMIT 1""",(procurement_id,))
    selected=cursor.fetchone()
    if not selected: raise HTTPException(409,"A supplier must be selected before creating a purchase order.")

    cursor.execute("SELECT id,item_name,quantity,unit FROM procurement_items WHERE procurement_id=%s ORDER BY id",(procurement_id,))
    items=cursor.fetchall()
    item_map={i["id"]:i for i in items}
    if not items: raise HTTPException(409,"The procurement has no items that can be ordered.")
    seen=set()
    for line in payload.lines:
        if line.procurement_item_id not in item_map: raise HTTPException(400,"One or more order lines do not belong to this procurement.")
        if line.procurement_item_id in seen: raise HTTPException(400,"The same procurement item cannot appear twice in an order.")
        seen.add(line.procurement_item_id)
        if Decimal(line.quantity)>Decimal(item_map[line.procurement_item_id]["quantity"]):
            raise HTTPException(409,f"Ordered quantity for {item_map[line.procurement_item_id]['item_name']} cannot exceed the required quantity.")
    if seen != set(item_map): raise HTTPException(400,"Every procurement item must appear exactly once in the purchase order.")

    cursor.execute("""INSERT INTO purchase_orders
        (procurement_id,supplier_id,order_number,order_date,expected_delivery_date,notes,status,created_by)
        VALUES(%s,%s,CONCAT('PO-',TO_CHAR(CURRENT_DATE,'YYYY'),'-',LPAD(nextval('purchase_order_number_seq')::text,6,'0')),
               CURRENT_DATE,%s,%s,'ISSUED',%s) RETURNING id,order_number""",
        (procurement_id,selected["supplier_id"],payload.expected_delivery_date,payload.notes,user_id))
    po=cursor.fetchone()
    for line in payload.lines:
        item=item_map[line.procurement_item_id]
        total=(Decimal(line.quantity)*Decimal(line.unit_price)) if line.unit_price is not None else None
        cursor.execute("""INSERT INTO purchase_order_lines
            (purchase_order_id,procurement_item_id,description,quantity,unit,unit_price,line_total)
            VALUES(%s,%s,%s,%s,%s,%s,%s)""",
            (po["id"],item["id"],line.description,line.quantity,item["unit"],line.unit_price,total))

    transition_procurement(cursor,procurement_id,user_id,"ORDERED","Purchase order created.")
    record_audit_event(cursor,procurement_id,user_id,"CREATE_PURCHASE_ORDER","purchase_order",po["id"],{"procurement_status":"SELECTED"},{"procurement_status":"ORDERED","supplier_id":selected["supplier_id"],"order_number":po["order_number"]})
    return {"id":po["id"],"order_number":po["order_number"],"supplier_id":selected["supplier_id"],"supplier_name":selected["supplier_name"]}
