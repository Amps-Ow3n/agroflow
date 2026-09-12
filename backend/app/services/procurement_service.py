from fastapi import HTTPException

from app.models.procurement_events import (
    STATUS_EVENT_MAP,
    record_audit_event,
    record_procurement_event,
)

VALID_TRANSITIONS = {
    "DRAFT": {"SUBMITTED", "CANCELLED"},
    "SUBMITTED": {"EVALUATION", "CANCELLED"},
    "EVALUATION": {"SELECTED"},
    "SELECTED": {"ORDERED"},
    "ORDERED": {"COMMITTED"},
    "COMMITTED": {"DELIVERY"},
    "DELIVERY": {"INSPECTION"},
    "INSPECTION": {"ACCEPTED"},
    "ACCEPTED": {"COMPLETED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def get_active_school_organization(cursor, user_id):
    cursor.execute(
        """
        SELECT o.id,o.name,o.organization_type,o.status,o.verification_status
        FROM organization_memberships om
        JOIN organizations o ON o.id=om.organization_id
        WHERE om.user_id=%s AND om.status='ACTIVE'
          AND o.organization_type='SCHOOL' AND o.status='ACTIVE' AND o.verification_status='VERIFIED'
        ORDER BY o.id
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    if not rows:
        raise HTTPException(403, "Your account is not associated with a verified active school organization.")
    if len(rows) > 1:
        raise HTTPException(409, "Multiple active school organizations were found. Select an organization before continuing.")
    return rows[0]


def user_belongs_to_organization(cursor, user_id, organization_id):
    cursor.execute(
        """SELECT 1 FROM organization_memberships om
           JOIN organizations o ON o.id=om.organization_id
           WHERE om.user_id=%s AND om.organization_id=%s
             AND om.status='ACTIVE' AND o.status='ACTIVE'""",
        (user_id, organization_id),
    )
    return cursor.fetchone() is not None

def get_procurement_for_user(
    cursor,
    procurement_id,
    user_id,
    for_update=False,
):

    lock = " FOR UPDATE" if for_update else ""

    cursor.execute(
        f"""
        SELECT
            p.*,
            o.name AS organization_name,
            u.name AS created_by_name,
            ru.name AS requesting_user_name

        FROM procurements p

        JOIN organizations o
            ON o.id = p.organization_id

        JOIN organization_memberships om
            ON om.organization_id = p.organization_id

        JOIN users u
            ON u.id = p.created_by

        JOIN users ru
            ON ru.id = p.requesting_user_id

        WHERE p.id = %s

          AND om.user_id = %s

          AND om.status = 'ACTIVE'

          AND o.status = 'ACTIVE'

          AND o.verification_status = 'VERIFIED'

          AND o.organization_type = 'SCHOOL'

        {lock}
        """,
        (
            procurement_id,
            user_id,
        ),
    )

    return cursor.fetchone()

def get_procurement_items(cursor, procurement_id):
    cursor.execute(
        """SELECT id,item_name,description,quantity,unit,created_at,updated_at
           FROM procurement_items WHERE procurement_id=%s ORDER BY id""",
        (procurement_id,),
    )
    return cursor.fetchall()


def create_procurement(cursor, user_id, payload):
    organization = get_active_school_organization(cursor, user_id)
    if not user_belongs_to_organization(cursor, user_id, organization["id"]):
        raise HTTPException(403, "You do not belong to the school organization.")

    cursor.execute(
        """INSERT INTO procurements
           (organization_id,created_by,requesting_user_id,title,description,status,
            procurement_date,required_by_date,location,specifications,quality_requirements,
            estimated_cost,procurement_method,notes,requesting_department)
           VALUES (%s,%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING id""",
        (organization["id"],user_id,user_id,payload.title,payload.description,
         payload.procurement_date,payload.required_by_date,payload.location,
         payload.specifications,payload.quality_requirements,payload.estimated_cost,
         payload.procurement_method,payload.notes,payload.requesting_department),
    )
    row = cursor.fetchone()
    procurement_id = row["id"]
    identifier = f"PROC-{procurement_id:06d}"
    cursor.execute("UPDATE procurements SET procurement_identifier=%s WHERE id=%s", (identifier, procurement_id))
    cursor.execute(
        """INSERT INTO procurement_items(procurement_id,item_name,description,quantity,unit)
           VALUES(%s,%s,%s,%s,%s) RETURNING id""",
        (procurement_id,payload.item_name,payload.item_description,payload.quantity,payload.unit),
    )
    record_procurement_event(cursor, procurement_id, "REQUIREMENT_CREATED", user_id,
                             entity_id=procurement_id, description="Procurement requirement created.")
    record_audit_event(cursor, procurement_id, user_id, "CREATE_PROCUREMENT", "procurement",
                       procurement_id, new_state={"status":"DRAFT","procurement_identifier":identifier})
    return {"id": procurement_id, "procurement_identifier": identifier, "organization_id": organization["id"]}


def update_procurement(cursor, procurement_id, user_id, payload):
    procurement = get_procurement_for_user(cursor, procurement_id, user_id, for_update=True)
    if not procurement:
        raise HTTPException(404, "Procurement not found.")
    if procurement["status"] != "DRAFT":
        raise HTTPException(409, "Only draft procurements can be edited.")

    cursor.execute(
        """UPDATE procurements SET title=%s,description=%s,procurement_date=%s,
           required_by_date=%s,location=%s,specifications=%s,quality_requirements=%s,
           estimated_cost=%s,procurement_method=%s,notes=%s,requesting_department=%s,
           updated_at=CURRENT_TIMESTAMP WHERE id=%s""",
        (payload.title,payload.description,payload.procurement_date,payload.required_by_date,
         payload.location,payload.specifications,payload.quality_requirements,payload.estimated_cost,
         payload.procurement_method,payload.notes,payload.requesting_department,procurement_id),
    )
    cursor.execute(
        """UPDATE procurement_items SET item_name=%s,description=%s,quantity=%s,unit=%s,
           updated_at=CURRENT_TIMESTAMP WHERE procurement_id=%s""",
        (payload.item_name,payload.item_description,payload.quantity,payload.unit,procurement_id),
    )
    record_procurement_event(cursor, procurement_id, "REQUIREMENT_UPDATED", user_id,
                             entity_id=procurement_id, description="Draft procurement requirement updated.")
    record_audit_event(cursor, procurement_id, user_id, "UPDATE_PROCUREMENT", "procurement",
                       procurement_id, previous_state={"status":"DRAFT"}, new_state={"status":"DRAFT"})
    return {"procurement_id": procurement_id, "status":"DRAFT"}


def transition_procurement(cursor, procurement_id, user_id, target_status, reason=None):
    procurement = get_procurement_for_user(cursor, procurement_id, user_id, for_update=True)
    if not procurement:
        raise HTTPException(404, "Procurement not found.")
    current = procurement["status"]
    if target_status not in VALID_TRANSITIONS.get(current, set()):
        raise HTTPException(409, f"Invalid procurement transition: {current} → {target_status}.")

    cursor.execute(
        "UPDATE procurements SET status=%s,submitted_at=CASE WHEN %s='SUBMITTED' THEN CURRENT_TIMESTAMP ELSE submitted_at END,cancelled_at=CASE WHEN %s='CANCELLED' THEN CURRENT_TIMESTAMP ELSE cancelled_at END,cancellation_reason=CASE WHEN %s='CANCELLED' THEN %s ELSE cancellation_reason END,updated_at=CURRENT_TIMESTAMP WHERE id=%s",
        (target_status,target_status,target_status,target_status,reason,procurement_id),
    )
    event_type = STATUS_EVENT_MAP.get(target_status, "PROCUREMENT_STATUS_CHANGED")
    event = record_procurement_event(cursor, procurement_id, event_type, user_id,
                                     entity_id=procurement_id,
                                     description=reason or f"{current} → {target_status}",
                                     metadata={"from_status":current,"to_status":target_status,"reason":reason})
    audit = record_audit_event(cursor, procurement_id, user_id, "TRANSITION_PROCUREMENT", "procurement",
                               procurement_id, previous_state={"status":current},
                               new_state={"status":target_status,"reason":reason})
    return {"procurement_id":procurement_id,"from_status":current,"to_status":target_status,
            "event_id":event["id"],"audit_event_id":audit["id"]}


def submit_procurement(cursor, procurement_id, user_id):
    procurement = get_procurement_for_user(cursor, procurement_id, user_id, for_update=False)
    if not procurement:
        raise HTTPException(404, "Procurement not found.")
    if not procurement["title"] or not procurement["required_by_date"] or not procurement["location"] or not procurement["procurement_method"]:
        raise HTTPException(400, "Procurement is missing required information.")
    if not get_procurement_items(cursor, procurement_id):
        raise HTTPException(409, "A procurement must contain at least one item.")
    return transition_procurement(cursor, procurement_id, user_id, "SUBMITTED")


def cancel_procurement(cursor, procurement_id, user_id, reason):
    return transition_procurement(cursor, procurement_id, user_id, "CANCELLED", reason)


def enter_supplier_evaluation(cursor, procurement_id, user_id):
    return transition_procurement(cursor, procurement_id, user_id, "EVALUATION", "Supplier evaluation started.")


def get_available_procurement_transitions(status):
    return sorted(VALID_TRANSITIONS.get(status, set()))


def get_procurement_event_history(cursor, procurement_id, user_id):
    procurement = get_procurement_for_user(cursor, procurement_id, user_id)
    if not procurement:
        raise HTTPException(404, "Procurement not found.")
    cursor.execute(
        """SELECT id,event_type,title,description,actor_id,entity_type,entity_id,occurred_at,metadata
           FROM procurement_events WHERE procurement_id=%s ORDER BY occurred_at,id""",
        (procurement_id,),
    )
    return cursor.fetchall()
