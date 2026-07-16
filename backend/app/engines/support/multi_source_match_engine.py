from app.utils.validators import validate_positive_quantity
from app.utils.normalizers import normalize_product

def generate_candidate_sources(
    cursor,
    product,
    supplier_id,
    delivery_start,
    delivery_end
):
    normalized_product = normalize_product(product)

    cursor.execute("""
        SELECT *
        FROM supply_sources
        WHERE LOWER(product)=%s

        AND actor_id=%s

        AND qty_available>0

        AND is_archived=FALSE

        AND available_from <= %s

        AND available_to >= %s

        ORDER BY available_from ASC
    """,
    (
        normalized_product,
    supplier_id,
    delivery_start,
    delivery_end
    ))

    return cursor.fetchall()

def build_fulfillment_plan(
    cursor,
    commitment
):
    # Step 1 — validate commitment quantity
    validate_positive_quantity(
        commitment["promised_qty"]
    )

    # Step 2 — normalize product
    product = normalize_product(
        commitment["product"]
    )

    required = commitment["promised_qty"]

    # Step 3 — fetch usable sources
    sources = generate_candidate_sources(
    cursor,
    product,
    commitment["supplier_id"],
    commitment["delivery_start"],
    commitment["delivery_end"]
)

    allocations = []
    remaining = required
    total_allocated = 0

    # Step 4 — allocate across multiple sources
    for source in sources:
        if remaining <= 0:
            break

        allocated = min(
            source["qty_available"],
            remaining
        )

        allocations.append({
            "source_id": source["id"],
            "source_name": source["actor_name"],
            "source_type": source["actor_type"],
            "allocated_qty": allocated,
            "available_qty": source["qty_available"]
        })

        total_allocated += allocated
        remaining -= allocated

    # Step 5 — return intelligent plan
    return {
        "commitment_id": commitment["id"],
        "allocations": allocations,
        "allocated_qty": total_allocated,
        "promised_qty": required,
        "feasible": remaining == 0,
        "remaining": remaining
    }