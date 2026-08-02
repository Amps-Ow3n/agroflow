from fastapi import HTTPException


def owns_commitment(
    cursor,
    commitment_id,
    user_id
):
    cursor.execute("""
        SELECT id
        FROM supplier_commitments
        WHERE id=%s
        AND supplier_id=%s
    """, (
        commitment_id,
        user_id
    ))

    return cursor.fetchone() is not None

def owns_delivery(
    cursor,
    delivery_id,
    supplier_id
):
    cursor.execute("""
        SELECT d.id

        FROM deliveries d

        JOIN supplier_commitments c

        ON d.commitment_id=c.id

        WHERE d.id=%s

        AND c.supplier_id=%s
    """, (
        delivery_id,
        supplier_id
    ))

    return cursor.fetchone() is not None

def owns_demand(
    cursor,
    demand_id,
    school_id
):
    cursor.execute("""
        SELECT id

        FROM school_demands

        WHERE id=%s

        AND school_id=%s
    """, (
        demand_id,
        school_id
    ))

    return cursor.fetchone() is not None