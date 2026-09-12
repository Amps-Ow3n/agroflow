import json

EVENT_TITLES = {
    "REQUIREMENT_CREATED": "Requirement Created",
    "REQUIREMENT_UPDATED": "Requirement Updated",
    "REQUIREMENT_SUBMITTED": "Requirement Submitted",
    "EVALUATION_STARTED": "Supplier Evaluation Started",
    "SUPPLIER_SELECTED": "Supplier Selected",
    "PURCHASE_ORDER_CREATED": "Purchase Order Created",
    "COMMITMENT_SUBMITTED": "Supplier Commitment Submitted",
    "COMMITMENT_ACCEPTED": "Supplier Commitment Accepted",
    "COMMITMENT_REJECTED": "Supplier Commitment Rejected",
    "DELIVERY_RECORDED": "Delivery Recorded",
    "INSPECTION_COMPLETED": "Inspection Completed",
    "GOODS_ACCEPTED": "Goods Accepted",
    "GOODS_REJECTED": "Goods Rejected",
    "PROCUREMENT_COMPLETED": "Procurement Completed",
    "PROCUREMENT_CANCELLED": "Procurement Cancelled",
    "PROCUREMENT_STATUS_CHANGED": "Procurement Status Changed",
    "EVIDENCE_ATTACHED": "Evidence Attached",
}

STATUS_EVENT_MAP = {
    "SUBMITTED": "REQUIREMENT_SUBMITTED",
    "EVALUATION": "EVALUATION_STARTED",
    "SELECTED": "SUPPLIER_SELECTED",
    "ORDERED": "PURCHASE_ORDER_CREATED",
    "COMMITTED": "COMMITMENT_ACCEPTED",
    "DELIVERY": "DELIVERY_RECORDED",
    "INSPECTION": "INSPECTION_COMPLETED",
    "ACCEPTED": "GOODS_ACCEPTED",
    "COMPLETED": "PROCUREMENT_COMPLETED",
    "CANCELLED": "PROCUREMENT_CANCELLED",
}


def _json(value):
    return json.dumps(value, default=str) if value is not None else None


def record_procurement_event(cursor, procurement_id, event_type, actor_id,
                             entity_type="procurement", entity_id=None,
                             description=None, metadata=None, occurred_at=None):
    cursor.execute(
        """
        INSERT INTO procurement_events
        (procurement_id,event_type,title,description,actor_id,entity_type,entity_id,occurred_at,metadata)
        VALUES (%s,%s,%s,%s,%s,%s,%s,COALESCE(%s,CURRENT_TIMESTAMP),%s)
        RETURNING *
        """,
        (procurement_id, event_type, EVENT_TITLES.get(event_type, event_type.replace("_", " ").title()),
         description, actor_id, entity_type, entity_id, occurred_at, _json(metadata)),
    )
    return cursor.fetchone()


def record_audit_event(cursor, procurement_id, actor_id, action, entity_type,
                       entity_id=None, previous_state=None, new_state=None, metadata=None):
    cursor.execute(
        """
        INSERT INTO audit_events
        (procurement_id,actor_id,action,entity_type,entity_id,previous_state,new_state,metadata)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (procurement_id, actor_id, action, entity_type, entity_id,
         _json(previous_state), _json(new_state), _json(metadata)),
    )
    return cursor.fetchone()


def resolve_procurement_id(cursor, entity_type, entity_id):
    queries = {
        "procurement": ("SELECT id FROM procurements WHERE id=%s", (entity_id,)),
        "purchase_order": ("SELECT procurement_id AS id FROM purchase_orders WHERE id=%s", (entity_id,)),
        "supplier_commitment": (
            """SELECT po.procurement_id AS id FROM supplier_commitments sc
               JOIN purchase_orders po ON po.id=sc.purchase_order_id WHERE sc.id=%s""", (entity_id,)),
        "delivery": (
            """SELECT po.procurement_id AS id FROM deliveries d
               JOIN supplier_commitments sc ON sc.id=d.commitment_id
               JOIN purchase_orders po ON po.id=sc.purchase_order_id WHERE d.id=%s""", (entity_id,)),
        "inspection": (
            """SELECT po.procurement_id AS id FROM inspections i
               JOIN deliveries d ON d.id=i.delivery_id
               JOIN supplier_commitments sc ON sc.id=d.commitment_id
               JOIN purchase_orders po ON po.id=sc.purchase_order_id WHERE i.id=%s""", (entity_id,)),
        "supplier_selection_decision": ("SELECT procurement_id AS id FROM supplier_selection_decisions WHERE id=%s", (entity_id,)),
        "evidence_document": ("SELECT procurement_id AS id FROM evidence_documents WHERE id=%s", (entity_id,)),
    }
    query = queries.get(entity_type)
    if not query:
        return None
    cursor.execute(*query)
    row = cursor.fetchone()
    return row["id"] if row else None
