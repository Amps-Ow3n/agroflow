from fastapi import HTTPException


def validate_verified_delivery(
    verification_status,
    received_qty,
    quality_status,
    delay_status
):
    """
    Delivery truth invariant.

    A VERIFIED delivery must contain
    complete truth information.
    """

    if verification_status == "VERIFIED":

        if received_qty is None:
            raise HTTPException(
                status_code=400,
                detail="Verified delivery requires received quantity"
            )

        if quality_status is None:
            raise HTTPException(
                status_code=400,
                detail="Verified delivery requires quality status"
            )

        if delay_status is None:
            raise HTTPException(
                status_code=400,
                detail="Verified delivery requires delay status"
            )

    if received_qty is not None and received_qty < 0:
        raise HTTPException(
            status_code=400,
            detail="Received quantity cannot be negative"
        )

    return True