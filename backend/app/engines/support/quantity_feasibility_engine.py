from app.utils.validators import validate_positive_quantity
from app.utils.normalizers import normalize_product

# ==========================
# PHYSICAL INVENTORY
# ==========================
def compute_total_available(
    cursor,
    supplier_id,
    product
):

    product = normalize_product(product)

    cursor.execute("""
        SELECT COALESCE(
            SUM(qty_available),
            0
        ) AS total
        FROM supply_sources
        WHERE actor_id=%s
        AND LOWER(product)=LOWER(%s)
        AND is_archived=FALSE
    """,
    (
        supplier_id,
        product
    ))

    result = cursor.fetchone()

    return result["total"]



# ==========================
# EXISTING PROMISES
# ==========================
def compute_allocated_elsewhere(
    cursor,
    supplier_id,
    product
):

    product = normalize_product(product)

    cursor.execute("""
        SELECT COALESCE(
            SUM(promised_qty),
            0
        ) AS allocated
        FROM supplier_commitments
        WHERE supplier_id=%s
        AND LOWER(product)=LOWER(%s)
        AND status IN (
            'PENDING',
            'ACCEPTED'
        )
    """,
    (
        supplier_id,
        product
    ))

    result = cursor.fetchone()

    return result["allocated"]



# ==========================
# FEASIBILITY DECISION
# ==========================
def evaluate_feasibility(
    requested_qty,
    total_available,
    allocated_elsewhere
):

    validate_positive_quantity(
        requested_qty
    )


    remaining_capacity = (
        total_available -
        allocated_elsewhere
    )


    if remaining_capacity >= requested_qty:

        return {

            "feasible": True,

            "status": "FEASIBLE",

            "available_capacity":
                remaining_capacity,

            "shortfall":0,

            "message":
            "Supply capacity covers commitment"

        }


    return {

        "feasible":False,

        "status":"SHORTFALL",

        "available_capacity":
            remaining_capacity,

        "shortfall":
            requested_qty - remaining_capacity,

        "message":
        "Insufficient unallocated supply"

    }