from app.core.exceptions import AgroFlowException

UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"
CHECK_VIOLATION = "23514"
NOT_NULL_VIOLATION = "23502"
SERIALIZATION_FAILURE = "40001"
DEADLOCK_DETECTED = "40P01"


def translate_database_error(exc):
    code = getattr(exc, "pgcode", None)
    constraint = getattr(getattr(exc, "diag", None), "constraint_name", None)

    if code in {SERIALIZATION_FAILURE, DEADLOCK_DETECTED}:
        return AgroFlowException(
            "This operation conflicted with another request. Please retry the operation.",
            409,
            "CONCURRENT_OPERATION",
        )

    if code == UNIQUE_VIOLATION:
        messages = {
            "uq_active_commitment_per_po_line_supplier": "An active commitment already exists for this purchase order line and supplier.",
            "selection_unique_sequence": "This procurement selection sequence already exists.",
            "deliveries_unique_sequence": "This delivery sequence already exists for the commitment.",
            "inspections_one_per_delivery": "This delivery has already been inspected.",
            "purchase_orders_one_per_procurement": "A purchase order already exists for this procurement.",
            "users_email_key": "A user with this email already exists.",
        }
        return AgroFlowException(
            messages.get(constraint, "The operation conflicts with an existing record."),
            409,
            "RESOURCE_CONFLICT",
        )

    if code == FOREIGN_KEY_VIOLATION:
        return AgroFlowException(
            "The operation references a record that does not exist or cannot be changed.",
            409,
            "INVALID_RELATIONSHIP",
        )

    if code == CHECK_VIOLATION:
        return AgroFlowException(
            "The operation violates a business rule.",
            409,
            "BUSINESS_RULE_VIOLATION",
        )

    if code == NOT_NULL_VIOLATION:
        return AgroFlowException(
            "Required information is missing.",
            400,
            "REQUIRED_FIELD_MISSING",
        )

    return None


def raise_translated_database_error(exc):
    translated = translate_database_error(exc)
    if translated is not None:
        raise translated from exc
    raise exc
