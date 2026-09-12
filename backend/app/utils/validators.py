# backend/app/utils/validators.py


def validate_positive_quantity(quantity):
    if quantity <= 0:
        raise ValueError(
            "Quantity must be greater than zero"
        )


def validate_required(value, field_name):
    if not value:
        raise ValueError(
            f"{field_name} is required"
        )


def validate_chain_allocation(
    total_allocated,
    promised_qty
):
    if total_allocated > promised_qty:
        raise ValueError(
            "Chain allocation exceeds commitment quantity"
        )