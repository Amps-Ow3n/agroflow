from fastapi import HTTPException


def require_record(
    record,
    *,
    entity_name: str,
    not_found_status: int = 404
):
    if not record:
        raise HTTPException(
            status_code=not_found_status,
            detail=f"{entity_name} not found."
        )

    return record


def require_equal(
    actual,
    expected,
    *,
    message: str,
    status_code: int = 409
):
    if actual != expected:
        raise HTTPException(
            status_code=status_code,
            detail=message
        )


def require_state(
    actual_state,
    allowed_states,
    *,
    message: str
):
    if actual_state not in allowed_states:
        raise HTTPException(
            status_code=409,
            detail=message
        )


def require_rejected_inspection(
    inspection
):
    require_record(
        inspection,
        entity_name="Inspection"
    )

    require_equal(
        inspection["result"],
        "REJECTED",
        message=(
            "Corrective action can only follow "
            "a rejected inspection."
        )
    )

    return inspection


def require_active_membership(
    membership,
    *,
    message="User does not have an active organization membership."
):
    if not membership:
        raise HTTPException(
            status_code=403,
            detail=message
        )

    return membership


def require_supplier_organization(
    organization
):
    require_record(
        organization,
        entity_name="Organization"
    )

    require_equal(
        organization["organization_type"],
        "SUPPLIER",
        message=(
            "The organization is not a supplier organization."
        )
    )

    require_equal(
        organization["status"],
        "ACTIVE",
        message=(
            "The supplier organization is not active."
        )
    )

    return organization

def require_po_line_belongs_to_po(
    po_line,
    purchase_order_id
):
    require_record(
        po_line,
        entity_name="Purchase order line"
    )

    require_equal(
        po_line["purchase_order_id"],
        purchase_order_id,
        message=(
            "The purchase order line does not belong "
            "to this purchase order."
        )
    )

    return po_line


def require_commitment_belongs_to_po_line(
    commitment,
    po_line_id
):
    require_record(
        commitment,
        entity_name="Commitment"
    )

    require_equal(
        commitment["purchase_order_line_id"],
        po_line_id,
        message=(
            "The commitment does not belong "
            "to this purchase order line."
        )
    )

    return commitment


def require_commitment_supplier_matches_po(
    commitment,
    po_supplier_id
):
    require_equal(
        commitment["supplier_id"],
        po_supplier_id,
        message=(
            "The commitment supplier does not "
            "match the purchase order supplier."
        )
    )

    return commitment


def require_delivery_belongs_to_procurement(
    delivery,
    procurement_id
):
    require_record(
        delivery,
        entity_name="Delivery"
    )

    require_equal(
        delivery["procurement_id"],
        procurement_id,
        message=(
            "The delivery does not belong "
            "to this procurement."
        )
    )

    return delivery


def require_inspection_belongs_to_delivery(
    inspection,
    delivery_id
):
    require_record(
        inspection,
        entity_name="Inspection"
    )

    require_equal(
        inspection["delivery_id"],
        delivery_id,
        message=(
            "The inspection does not belong "
            "to this delivery."
        )
    )

    return inspection


def require_corrective_action_follows_rejection(
    inspection
):
    return require_rejected_inspection(
        inspection
    )


def require_supplier_matches_organization(
    supplier,
    organization
):
    require_record(
        supplier,
        entity_name="Supplier"
    )

    require_record(
        organization,
        entity_name="Organization"
    )

    require_equal(
        supplier["organization_id"],
        organization["id"],
        message=(
            "The supplier does not belong "
            "to this organization."
        )
    )

    require_supplier_organization(
        organization
    )

    return supplier


def require_user_belongs_to_organization(
    membership,
    organization_id
):
    require_active_membership(
        membership
    )

    require_equal(
        membership["organization_id"],
        organization_id,
        message=(
            "The user does not belong "
            "to the procurement organization."
        ),
        status_code=403
    )

    return membership

def require_procurement_item_belongs_to_procurement(
    procurement_item,
    procurement_id
):
    require_record(
        procurement_item,
        entity_name="Procurement item"
    )

    require_equal(
        procurement_item["procurement_id"],
        procurement_id,
        message=(
            "The procurement item does not belong "
            "to this procurement."
        )
    )

    return procurement_item

def require_supplier_has_valid_organization(
    supplier_context
):
    if not supplier_context:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found."
        )

    if supplier_context["organization_type"] != "SUPPLIER":
        raise HTTPException(
            status_code=409,
            detail=(
                "Supplier must belong to a "
                "SUPPLIER organization."
            )
        )

    if supplier_context["organization_status"] != "ACTIVE":
        raise HTTPException(
            status_code=409,
            detail=(
                "Supplier organization is not active."
            )
        )

    return supplier_context

from decimal import Decimal, ROUND_HALF_UP


def validate_commitment_quantity(committed_quantity, available_quantity):
    """Validate that a commitment does not exceed available capacity."""
    committed = Decimal(str(committed_quantity))
    available = Decimal(str(available_quantity))

    if committed < 0:
        raise HTTPException(400, "Committed quantity cannot be negative.")
    if available < 0:
        raise HTTPException(400, "Available quantity cannot be negative.")
    if committed > available:
        raise HTTPException(409, "Committed quantity cannot exceed available capacity.")

    return True


def calculate_delivery_discrepancy(committed_quantity, received_quantity):
    """Calculate deterministic delivery shortfall/overage and variance."""
    committed = Decimal(str(committed_quantity))
    received = Decimal(str(received_quantity))

    if committed <= 0:
        raise ValueError("Committed quantity must be greater than zero.")
    if received < 0:
        raise ValueError("Received quantity cannot be negative.")

    difference = committed - received
    shortfall = max(difference, Decimal("0"))
    overage = max(-difference, Decimal("0"))
    variance_rate = (abs(difference) / committed * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return {
        "committed_quantity": committed,
        "received_quantity": received,
        "shortfall": shortfall,
        "overage": overage,
        "variance_rate": variance_rate,
    }
