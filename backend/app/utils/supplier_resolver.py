from fastapi import HTTPException

from app.models.suppliers import (
    get_supplier_by_user,
    get_supplier_by_id
)


def resolve_supplier_for_user(cursor, user_id):

    supplier = get_supplier_by_user(
        cursor,
        user_id
    )

    if not supplier:

        raise HTTPException(
            status_code=403,
            detail=(
                "The current user is not associated "
                "with an active supplier organization."
            )
        )

    return supplier


def resolve_supplier(cursor, supplier_id):

    supplier = get_supplier_by_id(
        cursor,
        supplier_id
    )

    if not supplier:

        raise HTTPException(
            status_code=404,
            detail="Supplier not found."
        )

    return supplier