from fastapi import HTTPException
from app.models.procurement_events import record_audit_event, record_procurement_event
from app.services.procurement_service import transition_procurement, get_procurement_for_user


def _delivery_for_school(cursor,delivery_id,user_id,for_update=False):
    lock=" FOR UPDATE" if for_update else ""
    cursor.execute(f"""SELECT d.*,sc.purchase_order_id,sc.purchase_order_line_id,sc.supplier_id,sc.promised_qty,
                              po.procurement_id,p.status AS procurement_status,p.organization_id
                       FROM deliveries d JOIN supplier_commitments sc ON sc.id=d.commitment_id
                       JOIN purchase_orders po ON po.id=sc.purchase_order_id JOIN procurements p ON p.id=po.procurement_id
                       JOIN organization_memberships om ON om.organization_id=p.organization_id
                       WHERE d.id=%s AND om.user_id=%s AND om.status='ACTIVE'{lock}""",(delivery_id,user_id))
    return cursor.fetchone()


def _all_deliveries_accepted_for_procurement(cursor,procurement_id):
    """Return True when every recorded delivery for the procurement has been accepted.

    Quantity discrepancies are evidence of fulfilment variance, not by themselves a
    failed inspection. A procurement can therefore reach ACCEPTED after all deliveries
    have been inspected and accepted even when the verified quantity is below the
    promised quantity. The discrepancy remains visible to the reality report and
    dashboard.
    """
    cursor.execute("""
        SELECT
            COUNT(d.id) AS delivery_count,
            COUNT(*) FILTER (
                WHERE d.delivery_status = 'ACCEPTED'
                  AND i.result = 'ACCEPTED'
            ) AS accepted_delivery_count
        FROM purchase_orders po
        JOIN supplier_commitments sc ON sc.purchase_order_id = po.id
        JOIN deliveries d ON d.commitment_id = sc.id
        LEFT JOIN inspections i ON i.delivery_id = d.id
        WHERE po.procurement_id = %s
          AND d.delivery_status <> 'REJECTED'
    """, (procurement_id,))
    row = cursor.fetchone() or {}
    delivery_count = row.get("delivery_count", 0)
    accepted_delivery_count = row.get("accepted_delivery_count", 0)
    return delivery_count > 0 and delivery_count == accepted_delivery_count

def inspect_delivery(cursor, delivery_id, user_id, payload):
    """
    Complete a delivery inspection and, when appropriate, advance the
    procurement lifecycle.

    Lifecycle:
        DELIVERY
            -> INSPECTION
            -> ACCEPTED

    The inspection itself is the authoritative point at which an accepted
    delivery can cause the procurement to become ACCEPTED.

    Quantity variance does NOT prevent acceptance. A delivery may be accepted
    with a shortfall; the shortfall remains visible to the discrepancy and
    reality-report layers.
    """

    # ------------------------------------------------------------
    # 1. Resolve the procurement belonging to this delivery
    # ------------------------------------------------------------

    cursor.execute(
        """
        SELECT
            po.procurement_id
        FROM deliveries d
        JOIN supplier_commitments sc
            ON sc.id = d.commitment_id
        JOIN purchase_orders po
            ON po.id = sc.purchase_order_id
        WHERE d.id = %s
        """,
        (delivery_id,),
    )

    ref = cursor.fetchone()

    if not ref:
        raise HTTPException(404, "Delivery not found.")

    procurement_id = ref["procurement_id"]

    # ------------------------------------------------------------
    # 2. Lock the procurement and verify school membership
    # ------------------------------------------------------------

    cursor.execute(
        """
        SELECT
            p.*
        FROM procurements p
        JOIN organization_memberships om
            ON om.organization_id = p.organization_id
        JOIN organizations o
            ON o.id = p.organization_id
        WHERE p.id = %s
          AND om.user_id = %s
          AND om.status = 'ACTIVE'
          AND o.status = 'ACTIVE'
          AND o.verification_status = 'VERIFIED'
        FOR UPDATE
        """,
        (procurement_id, user_id),
    )

    procurement = cursor.fetchone()

    if not procurement:
        raise HTTPException(404, "Delivery not found.")

    # ------------------------------------------------------------
    # 3. Lock the delivery
    # ------------------------------------------------------------

    delivery = _delivery_for_school(
        cursor,
        delivery_id,
        user_id,
        for_update=True,
    )

    if not delivery:
        raise HTTPException(404, "Delivery not found.")

    if delivery["delivery_status"] != "AWAITING_INSPECTION":
        raise HTTPException(
            409,
            "Only deliveries awaiting inspection can be inspected.",
        )

    # ------------------------------------------------------------
    # 4. Prevent duplicate inspection
    # ------------------------------------------------------------

    cursor.execute(
        """
        SELECT id
        FROM inspections
        WHERE delivery_id = %s
        """,
        (delivery_id,),
    )

    if cursor.fetchone():
        raise HTTPException(
            409,
            "This delivery has already been inspected.",
        )

    # ------------------------------------------------------------
    # 5. Calculate the physical quantity recorded on delivery
    # ------------------------------------------------------------

    cursor.execute(
        """
        SELECT COALESCE(SUM(actual_quantity), 0) AS actual
        FROM delivery_lines
        WHERE delivery_id = %s
        """,
        (delivery_id,),
    )

    actual = cursor.fetchone()["actual"]

    if payload.received_qty > actual:
        raise HTTPException(
            409,
            "Received quantity cannot exceed the actual quantity recorded on the delivery lines.",
        )

    # ------------------------------------------------------------
    # 6. Persist inspection
    # ------------------------------------------------------------

    cursor.execute(
        """
        INSERT INTO inspections (
            delivery_id,
            result,
            received_qty,
            quality_status,
            delay_status,
            rejection_reason,
            notes,
            inspected_by
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        RETURNING *
        """,
        (
            delivery_id,
            payload.result,
            payload.received_qty,
            payload.quality_status,
            payload.delay_status,
            payload.rejection_reason,
            payload.notes,
            user_id,
        ),
    )

    inspection = cursor.fetchone()

    # ------------------------------------------------------------
    # 7. Persist delivery inspection result
    # ------------------------------------------------------------

    cursor.execute(
        """
        UPDATE deliveries
        SET
            delivery_status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
        """,
        (
            payload.result,
            delivery_id,
        ),
    )

    updated_delivery = cursor.fetchone()

    # ------------------------------------------------------------
    # 8. Record inspection events
    # ------------------------------------------------------------

    event = (
        "GOODS_ACCEPTED"
        if payload.result == "ACCEPTED"
        else "GOODS_REJECTED"
    )

    record_procurement_event(
        cursor,
        procurement_id,
        event,
        user_id,
        "inspection",
        inspection["id"],
        "Inspection completed.",
        {
            "result": payload.result,
        },
    )

    record_audit_event(
        cursor,
        procurement_id,
        user_id,
        "INSPECT_DELIVERY",
        "inspection",
        inspection["id"],
        {
            "delivery_status": "AWAITING_INSPECTION",
        },
        {
            "delivery_status": payload.result,
            "result": payload.result,
        },
    )

    # ------------------------------------------------------------
    # 9. Re-read the procurement AFTER inspection persistence
    # ------------------------------------------------------------

    cursor.execute(
        """
        SELECT
            p.id,
            p.status,
            p.organization_id
        FROM procurements p
        JOIN organization_memberships om
            ON om.organization_id = p.organization_id
        JOIN organizations o
            ON o.id = p.organization_id
        WHERE p.id = %s
          AND om.user_id = %s
          AND om.status = 'ACTIVE'
          AND o.status = 'ACTIVE'
          AND o.verification_status = 'VERIFIED'
        FOR UPDATE
        """,
        (procurement_id, user_id),
    )

    current_procurement = cursor.fetchone()

    if not current_procurement:
        raise HTTPException(
            404,
            "Procurement could not be reloaded after inspection.",
        )

    current_status = current_procurement["status"]

    # ------------------------------------------------------------
    # 10. Move DELIVERY -> INSPECTION if necessary
    # ------------------------------------------------------------

    procurement_transition = None

    if (
        payload.result == "ACCEPTED"
        and current_status == "DELIVERY"
    ):
        procurement_transition = transition_procurement(
            cursor,
            procurement_id,
            user_id,
            "INSPECTION",
            "Delivery entered inspection.",
        )

        current_status = "INSPECTION"

    # ------------------------------------------------------------
    # 11. Check whether every delivery is accepted
    # ------------------------------------------------------------

    all_deliveries_accepted = False

    if (
        payload.result == "ACCEPTED"
        and current_status == "INSPECTION"
    ):
        all_deliveries_accepted = (
            _all_deliveries_accepted_for_procurement(
                cursor,
                procurement_id,
            )
        )

    # ------------------------------------------------------------
    # 12. INSPECTION -> ACCEPTED
    # ------------------------------------------------------------

    if (
        payload.result == "ACCEPTED"
        and current_status == "INSPECTION"
        and all_deliveries_accepted
    ):
        procurement_transition = transition_procurement(
            cursor,
            procurement_id,
            user_id,
            "ACCEPTED",
            (
                "All recorded deliveries have been inspected and accepted; "
                "any quantity variance remains recorded as a discrepancy."
            ),
        )

        # --------------------------------------------------------
        # 13. HARD VERIFY THE RESULT INSIDE THE SAME TRANSACTION
        # --------------------------------------------------------
        #
        # This is intentional.
        #
        # If transition_procurement() claims to have transitioned the
        # procurement, immediately verify the persisted row.
        # --------------------------------------------------------

        cursor.execute(
            """
            SELECT status
            FROM procurements
            WHERE id = %s
            FOR UPDATE
            """,
            (procurement_id,),
        )

        verified = cursor.fetchone()

        if not verified or verified["status"] != "ACCEPTED":
            raise HTTPException(
                500,
                "Inspection was recorded, but the procurement could not be advanced to ACCEPTED.",
            )

    return {
        "inspection": inspection,
        "delivery": updated_delivery,
        "procurement_transition": procurement_transition,
    }

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
