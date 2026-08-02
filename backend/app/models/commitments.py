
from app.core.db import get_db

def create_commitment(
    supplier_id,
    school_id,
    product,
    promised_qty,
    delivery_start,
    delivery_end
):
    conn, cursor = get_db()

    cursor.execute("""
        INSERT INTO supplier_commitments (
            supplier_id,
            school_id,
            product,
            promised_qty,
            delivery_start,
            delivery_end
        )
        VALUES (%s,%s,%s,%s,%s,%s)
        RETURNING *
    """, (
        supplier_id,
        school_id,
        product,
        promised_qty,
        delivery_start,
        delivery_end
    ))

    commitment = cursor.fetchone()

    conn.commit()
    conn.close()

    return commitment


def get_supplier_commitments(supplier_id):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT *
        FROM supplier_commitments
        WHERE supplier_id = %s
    """, (supplier_id,))

    commitments = cursor.fetchall()

    conn.close()

    return commitments

def get_commitment_by_id(
    cursor,
    commitment_id
):
    cursor.execute("""
        SELECT *
        FROM supplier_commitments
        WHERE id = %s
    """, (
        commitment_id,
    ))

    return cursor.fetchone()