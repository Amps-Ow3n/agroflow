from fastapi import HTTPException
from app.services.procurement_service import transition_procurement


def _get_procurement(cursor, procurement_id, user_id, for_update=False):
    lock = " FOR UPDATE" if for_update else ""
    cursor.execute(
        f"""SELECT p.*,o.name AS organization_name
            FROM procurements p
            JOIN organizations o ON o.id=p.organization_id
            JOIN organization_memberships om ON om.organization_id=p.organization_id
            WHERE p.id=%s AND om.user_id=%s AND om.status='ACTIVE'{lock}""",
        (procurement_id, user_id),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(404, "Procurement not found.")
    return row


def _evaluate_one(cursor, procurement, supplier_id, user_id):
    cursor.execute(
        """SELECT s.id,s.status,o.name AS supplier_name,o.status AS organization_status,
                  o.verification_status
           FROM suppliers s JOIN organizations o ON o.id=s.organization_id
           WHERE s.id=%s AND o.organization_type='SUPPLIER'""",
        (supplier_id,),
    )
    supplier = cursor.fetchone()
    if not supplier:
        return None

    cursor.execute(
        """SELECT pi.item_name FROM procurement_items pi
           WHERE pi.procurement_id=%s ORDER BY pi.id LIMIT 1""",
        (procurement["id"],),
    )
    item = cursor.fetchone()
    item_name = item["item_name"] if item else ""

    cursor.execute(
        """SELECT EXISTS(
             SELECT 1 FROM supplier_products sp
             WHERE sp.supplier_id=%s AND sp.status='ACTIVE'
               AND lower(trim(sp.product))=lower(trim(%s))
           ) AS required_item_match""",
        (supplier_id, item_name),
    )
    item_match = cursor.fetchone()["required_item_match"]

    cursor.execute(
        """SELECT observation_count,completed_commitment_count,promised_quantity,
                  accepted_quantity,fulfilment_rate,on_time_delivery_rate,
                  quantity_variance_rate,quality_acceptance_rate,status
           FROM supplier_performance_metrics WHERE supplier_id=%s""",
        (supplier_id,),
    )
    metrics = cursor.fetchone()
    if metrics:
        historical_status = metrics["status"]
        delivery_count = metrics["observation_count"]
        commitment_count = metrics["completed_commitment_count"]
    else:
        historical_status = "NO_HISTORY"
        delivery_count = 0
        commitment_count = 0

    verified = supplier["verification_status"] == "VERIFIED"
    active = supplier["status"] == "ACTIVE" and supplier["organization_status"] == "ACTIVE"
    eligible = bool(item_match and verified and active)

    if not eligible:
        reasons = []
        if not item_match: reasons.append("supplier does not list the required item")
        if not verified: reasons.append("supplier organization is not verified")
        if not active: reasons.append("supplier or supplier organization is not active")
        explanation = "Ineligible because " + "; ".join(reasons) + "."
    elif historical_status == "NO_HISTORY":
        explanation = "Eligible based on current supplier and item evidence; no historical delivery evidence is available."
    else:
        explanation = "Eligible based on current supplier and item evidence; historical indicators are shown as observations, not guarantees."

    values = {
        "procurement_id": procurement["id"],
        "supplier_id": supplier_id,
        "evaluation_status": "ELIGIBLE" if eligible else "INELIGIBLE",
        "required_item_match": bool(item_match),
        "mandatory_eligible": eligible,
        "verification_status": supplier["verification_status"],
        "capacity_status": "UNKNOWN",
        "historical_evidence_status": historical_status,
        "historical_delivery_count": delivery_count,
        "historical_commitment_count": commitment_count,
        "fulfilled_quantity": (metrics["accepted_quantity"] if metrics else 0),
        "promised_quantity": (metrics["promised_quantity"] if metrics else 0),
        "fulfilment_rate": (metrics["fulfilment_rate"] if metrics else None),
        "on_time_delivery_rate": (metrics["on_time_delivery_rate"] if metrics else None),
        "quantity_variance_rate": (metrics["quantity_variance_rate"] if metrics else None),
        "quality_acceptance_rate": (metrics["quality_acceptance_rate"] if metrics else None),
        "indicator_explanation": explanation,
    }

    cursor.execute(
        """INSERT INTO supplier_evaluations
           (procurement_id,supplier_id,evaluation_status,required_item_match,mandatory_eligible,
            verification_status,capacity_status,historical_evidence_status,historical_delivery_count,
            historical_commitment_count,fulfilled_quantity,promised_quantity,fulfilment_rate,
            on_time_delivery_rate,quantity_variance_rate,quality_acceptance_rate,indicator_explanation,evaluated_by)
           VALUES(%(procurement_id)s,%(supplier_id)s,%(evaluation_status)s,%(required_item_match)s,%(mandatory_eligible)s,
                  %(verification_status)s,%(capacity_status)s,%(historical_evidence_status)s,%(historical_delivery_count)s,
                  %(historical_commitment_count)s,%(fulfilled_quantity)s,%(promised_quantity)s,%(fulfilment_rate)s,
                  %(on_time_delivery_rate)s,%(quantity_variance_rate)s,%(quality_acceptance_rate)s,%(indicator_explanation)s,%(evaluated_by)s)
           ON CONFLICT (procurement_id,supplier_id) DO UPDATE SET
             evaluation_status=EXCLUDED.evaluation_status,required_item_match=EXCLUDED.required_item_match,
             mandatory_eligible=EXCLUDED.mandatory_eligible,verification_status=EXCLUDED.verification_status,
             capacity_status=EXCLUDED.capacity_status,historical_evidence_status=EXCLUDED.historical_evidence_status,
             historical_delivery_count=EXCLUDED.historical_delivery_count,historical_commitment_count=EXCLUDED.historical_commitment_count,
             fulfilled_quantity=EXCLUDED.fulfilled_quantity,promised_quantity=EXCLUDED.promised_quantity,
             fulfilment_rate=EXCLUDED.fulfilment_rate,on_time_delivery_rate=EXCLUDED.on_time_delivery_rate,
             quantity_variance_rate=EXCLUDED.quantity_variance_rate,quality_acceptance_rate=EXCLUDED.quality_acceptance_rate,
             indicator_explanation=EXCLUDED.indicator_explanation,evaluated_by=EXCLUDED.evaluated_by,
             evaluated_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP
           RETURNING *""",
        {**values, "evaluated_by": user_id},
    )
    return cursor.fetchone()


def get_procurement_for_evaluation(cursor, procurement_id, user_id):
    return _get_procurement(cursor, procurement_id, user_id)


def get_supplier_candidates(cursor, procurement_id, user_id):
    procurement = _get_procurement(cursor, procurement_id, user_id)
    if procurement["status"] not in {"SUBMITTED", "EVALUATION"}:
        raise HTTPException(409, "Supplier evaluation is only available for submitted or evaluation-stage procurements.")
    cursor.execute(
        """SELECT s.id,s.supplier_code,o.name AS supplier_name,o.verification_status,o.status AS organization_status,
                  se.id AS evaluation_id,se.evaluation_status,se.required_item_match,se.mandatory_eligible,
                  se.capacity_status,se.historical_evidence_status,se.historical_delivery_count,
                  se.historical_commitment_count,se.fulfilled_quantity,se.promised_quantity,se.fulfilment_rate,
                  se.on_time_delivery_rate,se.quantity_variance_rate,se.quality_acceptance_rate,se.indicator_explanation,se.evaluated_at
           FROM suppliers s JOIN organizations o ON o.id=s.organization_id
           LEFT JOIN supplier_evaluations se ON se.supplier_id=s.id AND se.procurement_id=%s
           WHERE o.organization_type='SUPPLIER' AND s.status='ACTIVE' ORDER BY se.mandatory_eligible DESC NULLS LAST,o.name""",
        (procurement_id,),
    )
    return {"procurement": procurement, "candidates": cursor.fetchall()}


def evaluate_all_suppliers(cursor, procurement_id, user_id):
    procurement = _get_procurement(cursor, procurement_id, user_id, for_update=True)
    if procurement["status"] not in {"SUBMITTED", "EVALUATION"}:
        raise HTTPException(409, "Procurement is not ready for supplier evaluation.")
    if procurement["status"] == "SUBMITTED":
        transition_procurement(cursor, procurement_id, user_id, "EVALUATION", "Supplier evaluation started.")
        procurement["status"] = "EVALUATION"
    cursor.execute("SELECT s.id FROM suppliers s JOIN organizations o ON o.id=s.organization_id WHERE s.status='ACTIVE' AND o.organization_type='SUPPLIER' ORDER BY s.id")
    evaluations = [_evaluate_one(cursor, procurement, row["id"], user_id) for row in cursor.fetchall()]
    evaluations = [e for e in evaluations if e]
    return {"procurement": procurement, "evaluations": evaluations}
