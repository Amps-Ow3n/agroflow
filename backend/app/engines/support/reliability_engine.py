from app.engines.intelligence.delivery_reliability_engine import (
    compute_delivery_reliability
)

def compute_supplier_reliability(
    cursor,
    supplier_id
):
    """
    Compatibility wrapper.

    Older dashboard code still calls this
    function.

    Actual reliability mathematics lives in:

        intelligence.delivery_reliability_engine
    """

    result = compute_delivery_reliability(
        cursor,
        supplier_id
    )

    return {

        "score": result["score"],

        "confidence": result["confidence"]

    }