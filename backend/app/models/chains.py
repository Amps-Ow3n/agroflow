from app.core.db import get_db

def create_chain_link(
    commitment_id,
    source_id,
    allocated_qty,
    chain_position
):
    conn, cursor = get_db()

    cursor.execute("""
        INSERT INTO procurement_chains (
            commitment_id,
            source_id,
            allocated_qty,
            chain_position
        )
        VALUES (%s,%s,%s,%s)
        RETURNING *
    """, (
        commitment_id,
        source_id,
        allocated_qty,
        chain_position
    ))

    chain = cursor.fetchone()

    conn.commit()
    conn.close()

    return chain

def get_commitment_chain(commitment_id):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT *
        FROM procurement_chains
        WHERE commitment_id = %s
        ORDER BY chain_position ASC
    """, (commitment_id,))

    chain = cursor.fetchall()

    conn.close()

    return chain

def insert_chain_link(
    cursor,
    commitment_id,
    source_id,
    allocated_qty,
    chain_position
):
    cursor.execute("""
        INSERT INTO procurement_chains (
            commitment_id,
            source_id,
            allocated_qty,
            chain_position
        )
        VALUES (%s,%s,%s,%s)
        RETURNING *
    """, (
        commitment_id,
        source_id,
        allocated_qty,
        chain_position
    ))

    return cursor.fetchone()