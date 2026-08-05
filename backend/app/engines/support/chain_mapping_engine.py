from app.utils.validators import validate_required

def check_source_exists(cursor, source_id):
    validate_required(source_id, "source_id")

    cursor.execute("""
        SELECT 1
        FROM supply_sources
        WHERE id = %s
    """, (source_id,))

    return cursor.fetchone() is not None


def check_duplicate_source_usage(
    cursor,
    source_id,
    commitment_id=None
):
    if commitment_id:
        cursor.execute("""
            SELECT 1
            FROM procurement_chains
            WHERE source_id = %s
            AND commitment_id = %s
        """, (source_id, commitment_id))
    else:
        cursor.execute("""
            SELECT 1
            FROM procurement_chains
            WHERE source_id = %s
        """, (source_id,))

    return cursor.fetchone() is not None


def validate_chain_integrity(
    cursor,
    commitment_id
):
    validate_required(commitment_id, "commitment_id")

    cursor.execute("""
        SELECT source_id, allocated_qty
        FROM procurement_chains
        WHERE commitment_id = %s
    """, (commitment_id,))

    rows = cursor.fetchall()

    if not rows:
        return {
            "valid": False,
            "unique_sources": 0,
            "total_allocations": 0
        }

    unique_sources = len(
        set(r["source_id"] for r in rows)
    )

    total_allocations = sum(
        r["allocated_qty"] or 0
        for r in rows
    )

    return {
        "valid": unique_sources == len(rows),
        "unique_sources": unique_sources,
        "total_allocations": total_allocations
    }