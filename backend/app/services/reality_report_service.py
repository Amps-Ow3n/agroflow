from decimal import Decimal
from fastapi import HTTPException

from app.services.procurement_service import get_procurement_for_user, get_procurement_items
from app.services.supplier_performance_service import get_supplier_performance


def _number(value):
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _pct(numerator, denominator):
    denominator = _number(denominator)
    if denominator <= 0:
        return None
    return (_number(numerator) / denominator * Decimal("100")).quantize(Decimal("0.01"))


def _finding(message, severity="INFO"):
    return {"severity": severity, "message": message}


def get_reality_report(cursor, procurement_id, user_id):
    procurement = get_procurement_for_user(cursor, procurement_id, user_id)
    if not procurement:
        raise HTTPException(404, "Procurement not found.")

    items = get_procurement_items(cursor, procurement_id)

    cursor.execute(
        """
        SELECT
            d.id,
            d.supplier_id,
            d.decision_type,
            d.decision_reason,
            d.decision_sequence,
            d.decided_by,
            d.decided_at,
            s.supplier_code,
            o.name AS supplier_name
        FROM supplier_selection_decisions d
        JOIN suppliers s ON s.id = d.supplier_id
        JOIN organizations o ON o.id = s.organization_id
        WHERE d.procurement_id = %s
        ORDER BY d.decision_sequence DESC
        LIMIT 1
        """,
        (procurement_id,),
    )
    selection = cursor.fetchone()

    cursor.execute(
        """
        SELECT
            se.*,
            s.supplier_code,
            o.name AS supplier_name,
            u.name AS evaluated_by_name
        FROM supplier_evaluations se
        JOIN suppliers s ON s.id = se.supplier_id
        JOIN organizations o ON o.id = s.organization_id
        JOIN users u ON u.id = se.evaluated_by
        WHERE se.procurement_id = %s
        ORDER BY se.evaluated_at DESC, se.id DESC
        """,
        (procurement_id,),
    )
    evaluations = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            po.id,
            po.order_number,
            po.order_date,
            po.expected_delivery_date,
            po.currency,
            po.status,
            po.supplier_id,
            s.supplier_code,
            o.name AS supplier_name,
            u.name AS created_by_name
        FROM purchase_orders po
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN organizations o ON o.id = s.organization_id
        JOIN users u ON u.id = po.created_by
        WHERE po.procurement_id = %s
        LIMIT 1
        """,
        (procurement_id,),
    )
    purchase_order = cursor.fetchone()

    order_lines = []
    if purchase_order:
        cursor.execute(
            """
            SELECT
                pol.id,
                pol.procurement_item_id,
                pol.quantity,
                pol.unit,
                pol.unit_price,
                pol.line_total,
                pi.item_name,
                pi.description
            FROM purchase_order_lines pol
            JOIN procurement_items pi ON pi.id = pol.procurement_item_id
            WHERE pol.purchase_order_id = %s
            ORDER BY pol.id
            """,
            (purchase_order["id"],),
        )
        order_lines = cursor.fetchall()

    commitments = []
    if purchase_order:
        cursor.execute(
            """
            SELECT
                sc.id,
                sc.purchase_order_line_id,
                sc.supplier_id,
                sc.promised_qty,
                sc.delivery_start,
                sc.delivery_end,
                sc.status,
                sc.submitted_at,
                sc.accepted_at,
                s.supplier_code,
                o.name AS supplier_name
            FROM supplier_commitments sc
            JOIN suppliers s ON s.id = sc.supplier_id
            JOIN organizations o ON o.id = s.organization_id
            WHERE sc.purchase_order_id = %s
            ORDER BY sc.purchase_order_line_id, sc.id
            """,
            (purchase_order["id"],),
        )
        commitments = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            d.id,
            d.commitment_id,
            d.delivery_sequence,
            d.delivery_date,
            d.condition,
            d.notes,
            d.delivery_status,
            d.receiving_user_id,
            u.name AS receiving_user_name
        FROM deliveries d
        JOIN supplier_commitments sc ON sc.id = d.commitment_id
        JOIN purchase_orders po ON po.id = sc.purchase_order_id
        JOIN users u ON u.id = d.receiving_user_id
        WHERE po.procurement_id = %s
        ORDER BY d.delivery_date, d.delivery_sequence, d.id
        """,
        (procurement_id,),
    )
    deliveries = cursor.fetchall()

    delivery_ids = [row["id"] for row in deliveries]
    delivery_lines = []
    inspections = []
    if delivery_ids:
        cursor.execute(
            """
            SELECT
                dl.delivery_id,
                dl.procurement_item_id,
                dl.actual_quantity,
                pi.item_name,
                pi.unit
            FROM delivery_lines dl
            JOIN procurement_items pi ON pi.id = dl.procurement_item_id
            WHERE dl.delivery_id = ANY(%s)
            ORDER BY dl.delivery_id, dl.id
            """,
            (delivery_ids,),
        )
        delivery_lines = cursor.fetchall()

        cursor.execute(
            """
            SELECT
                i.id,
                i.delivery_id,
                i.result,
                i.received_qty,
                i.quality_status,
                i.delay_status,
                i.rejection_reason,
                i.notes,
                i.inspected_by,
                i.inspected_at,
                u.name AS inspected_by_name
            FROM inspections i
            JOIN users u ON u.id = i.inspected_by
            WHERE i.delivery_id = ANY(%s)
            ORDER BY i.inspected_at, i.id
            """,
            (delivery_ids,),
        )
        inspections = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            id,
            event_id,
            document_type,
            document_name,
            original_filename,
            mime_type,
            file_size,
            visibility,
            uploaded_by,
            uploaded_at
        FROM evidence_documents
        WHERE procurement_id = %s
          AND deleted_at IS NULL
        ORDER BY uploaded_at, id
        """,
        (procurement_id,),
    )
    evidence = cursor.fetchall()

    supplier_id = selection["supplier_id"] if selection else (purchase_order["supplier_id"] if purchase_order else None)
    historical = None
    if supplier_id:
        # Reality Report history must be derived from completed cycles that
        # occurred before the procurement currently being reported. Do not
        # depend on a persisted performance snapshot, because snapshots can
        # be stale or absent while the underlying procurement evidence exists.
        historical = get_supplier_performance(
            cursor,
            supplier_id,
            exclude_procurement_id=procurement_id,
        )

    promised_by_line = {}
    for commitment in commitments:
        if commitment["status"] != "ACCEPTED":
            continue
        line_id = commitment["purchase_order_line_id"]
        promised_by_line[line_id] = promised_by_line.get(line_id, Decimal("0")) + _number(commitment["promised_qty"])

    delivered_by_item = {}
    for line in delivery_lines:
        item_id = line["procurement_item_id"]
        delivered_by_item[item_id] = delivered_by_item.get(item_id, Decimal("0")) + _number(line["actual_quantity"])

    verified_by_item = {}
    inspection_by_delivery = {row["delivery_id"]: row for row in inspections}
    for inspection in inspections:
        if inspection["result"] != "ACCEPTED":
            continue
        delivery_id = inspection["delivery_id"]
        for line in delivery_lines:
            if line["delivery_id"] == delivery_id:
                item_id = line["procurement_item_id"]
                # The inspection's received quantity is the verified quantity for the delivery.
                # When a delivery contains multiple items, preserve the delivery-line facts and
                # expose the inspection quantity at delivery level instead of inventing a split.
                verified_by_item.setdefault(item_id, Decimal("0"))

    total_promised = sum(promised_by_line.values(), Decimal("0"))
    total_delivered = sum(delivered_by_item.values(), Decimal("0"))
    total_verified = sum(
        (_number(i["received_qty"]) for i in inspections if i["result"] == "ACCEPTED"),
        Decimal("0"),
    )

    line_results = []
    for line in order_lines:
        promised = promised_by_line.get(line["id"], Decimal("0"))
        actual = delivered_by_item.get(line["procurement_item_id"], Decimal("0"))
        variance = None
        if promised > 0:
            variance = ((abs(promised - actual) / promised) * Decimal("100")).quantize(Decimal("0.01"))
        line_results.append({
            "purchase_order_line_id": line["id"],
            "item_name": line["item_name"],
            "required_quantity": _number(next((i["quantity"] for i in items if i["id"] == line["procurement_item_id"]), 0)),
            "ordered_quantity": _number(line["quantity"]),
            "promised_quantity": promised,
            "delivered_quantity": actual,
            "variance_rate": variance,
            "shortfall": max(promised - actual, Decimal("0")),
            "overage": max(actual - promised, Decimal("0")),
            "unit": line["unit"],
        })

    findings = []
    if not selection:
        findings.append(_finding("No supplier selection decision is recorded.", "WARNING"))
    if not purchase_order:
        findings.append(_finding("No purchase order is recorded yet.", "WARNING"))
    if commitments and total_promised < sum(_number(i["quantity"]) for i in items):
        findings.append(_finding("The accepted supplier promise is below the required quantity.", "WARNING"))
    if total_promised > 0 and total_delivered != total_promised:
        findings.append(_finding(
            f"Delivered quantity differs from accepted commitments by {abs(total_promised - total_delivered)} units.",
            "WARNING",
        ))
    if any(i["result"] == "REJECTED" for i in inspections):
        findings.append(_finding("At least one delivery was rejected during inspection.", "CRITICAL"))
    if any(i["delay_status"] == "DELAYED" for i in inspections):
        findings.append(_finding("At least one delivery was recorded as delayed.", "WARNING"))
    if any(i["quality_status"] == "FAILED" for i in inspections):
        findings.append(_finding("At least one inspection recorded failed quality.", "CRITICAL"))
    if not evidence:
        findings.append(_finding("No procurement-level evidence document is attached.", "WARNING"))
    if historical and historical["status"] == "NO_HISTORY":
        findings.append(_finding("The selected supplier has no historical performance evidence.", "INFO"))

    next_time = []
    if any(i["delay_status"] == "DELAYED" for i in inspections):
        next_time.append("Review the supplier's delivery window and contingency plan before the next cycle.")
    if total_promised > 0 and total_delivered != total_promised:
        next_time.append("Use the observed fulfilment variance when setting the next commitment and buffer.")
    if any(i["quality_status"] == "FAILED" or i["result"] == "REJECTED" for i in inspections):
        next_time.append("Strengthen receiving-quality requirements and require corrective evidence before reuse.")
    if historical and historical["status"] == "NO_HISTORY":
        next_time.append("Treat supplier reliability as insufficiently evidenced until more completed cycles exist.")
    if not next_time:
        next_time.append("Continue collecting verified delivery and inspection evidence for future comparison.")

    return {
        "procurement": dict(procurement),
        "requirement": {
            "items": [dict(row) for row in items],
            "title": procurement["title"],
            "description": procurement.get("description"),
            "required_by_date": procurement.get("required_by_date"),
            "location": procurement.get("location"),
            "procurement_method": procurement.get("procurement_method"),
        },
        "selection": dict(selection) if selection else None,
        "evaluations": [dict(row) for row in evaluations],
        "purchase_order": dict(purchase_order) if purchase_order else None,
        "commitments": [dict(row) for row in commitments],
        "deliveries": [dict(row) for row in deliveries],
        "inspections": [dict(row) for row in inspections],
        "evidence": [dict(row) for row in evidence],
        "historical_supplier_performance": dict(historical) if historical else None,
        "fulfilment": {
            "required_quantity": sum((_number(i["quantity"]) for i in items), Decimal("0")),
            "promised_quantity": total_promised,
            "delivered_quantity": total_delivered,
            "verified_accepted_quantity": total_verified,
            "promised_fulfilment_rate": _pct(total_promised, sum((_number(i["quantity"]) for i in items), Decimal("0"))),
            "delivery_vs_promise_rate": _pct(total_delivered, total_promised),
            "verified_vs_promise_rate": _pct(total_verified, total_promised),
            "line_results": line_results,
        },
        "quality": {
            "inspection_count": len(inspections),
            "accepted_count": sum(1 for i in inspections if i["result"] == "ACCEPTED"),
            "rejected_count": sum(1 for i in inspections if i["result"] == "REJECTED"),
            "failed_quality_count": sum(1 for i in inspections if i["quality_status"] == "FAILED"),
            "delayed_count": sum(1 for i in inspections if i["delay_status"] == "DELAYED"),
        },
        "evidence_summary": {
            "count": len(evidence),
            "document_types": sorted({row["document_type"] for row in evidence}),
        },
        "findings": findings,
        "what_should_be_considered_next_time": next_time,
        "report_completeness": {
            "selection_recorded": selection is not None,
            "order_recorded": purchase_order is not None,
            "commitment_recorded": bool(commitments),
            "delivery_recorded": bool(deliveries),
            "inspection_recorded": bool(inspections),
            "evidence_recorded": bool(evidence),
            "procurement_completed": procurement["status"] == "COMPLETED",
        },
    }
