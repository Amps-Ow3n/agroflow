def can_edit_source(cursor, source_id, actor_id):
    cursor.execute("""
        SELECT id
        FROM supply_sources
        WHERE id = %s AND actor_id = %s
    """, (source_id, actor_id))

    source = cursor.fetchone()
    return source is not None

def was_source_used(cursor, source_id):

    cursor.execute("""

        SELECT 1

        FROM procurement_chains

        WHERE source_id=%s

        LIMIT 1

    """,(source_id,))

    return cursor.fetchone() is not None

def owns_source(cursor, source_id, actor_id):

    cursor.execute("""

        SELECT id

        FROM supply_sources

        WHERE id=%s

        AND actor_id=%s

    """,(source_id,actor_id))

    return cursor.fetchone() is not None

def archive_source(cursor, source_id, actor_id):
    cursor.execute("""
        UPDATE supply_sources
        SET is_archived = TRUE
        WHERE id = %s AND actor_id = %s
    """, (source_id, actor_id))

def update_commitment_status(cursor, commitment_id, new_status):
    cursor.execute("""
        SELECT status
        FROM supplier_commitments
        WHERE id = %s
    """, (commitment_id,))

    current = cursor.fetchone()["status"]

    allowed = {
        "PENDING": ["ACCEPTED", "CANCELLED"],
        "ACCEPTED": ["COMPLETED", "CANCELLED"],
    }

    if new_status not in allowed.get(current, []):
        raise Exception("Invalid state transition")

    cursor.execute("""
        UPDATE supplier_commitments
        SET status = %s
        WHERE id = %s
    """, (new_status, commitment_id))

def can_edit_demand(status):
    return status == "OPEN"

def update_demand(cursor, demand_id, payload):
    cursor.execute("""
        SELECT status
        FROM school_demands
        WHERE id = %s
    """, (demand_id,))

    status = cursor.fetchone()["status"]

    if status != "OPEN":
        raise Exception("Cannot edit non-OPEN demand")
    
