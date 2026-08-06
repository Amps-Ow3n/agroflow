from app.core.db import get_db

def create_source(
    actor_id,
    actor_type,
    actor_name,
    product,
    qty_available,
    location,
    available_from,
    available_to
):
    conn, cursor = get_db()

    cursor.execute("""
        INSERT INTO supply_sources (
            actor_id,
            actor_type,
            actor_name,
            product,
            qty_available,
            location,
            available_from,
            available_to
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
    """, (
        actor_id,
        actor_type,
        actor_name,
        product,
        qty_available,
        location,
        available_from,
        available_to
    ))

    source = cursor.fetchone()

    conn.commit()
    conn.close()

    return source

def get_actor_sources(actor_id):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT
    s.*,

    EXISTS (
        SELECT 1
        FROM procurement_chains pc
        WHERE pc.source_id = s.id
    ) AS used_in_chain

FROM supply_sources s
WHERE s.actor_id = %s
ORDER BY s.created_at DESC
    """, (actor_id,))

    sources = cursor.fetchall()

    conn.close()

    return sources

def get_source_by_id(source_id):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT *
        FROM supply_sources
        WHERE id = %s
    """, (source_id,))

    source = cursor.fetchone()

    conn.close()

    return source

def create_supply_source(
    actor_id,
    actor_type,
    actor_name,
    payload
):
    return create_source(
        actor_id,
        actor_type,
        actor_name,
        payload.product,
        payload.qty_available,
        payload.location,
        payload.available_from,
        payload.available_to
    )

def get_sources_by_actor(
    actor_id,
    limit=20,
    offset=0
):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT
            s.*,

            EXISTS (
                SELECT 1
                FROM procurement_chains pc
                WHERE pc.source_id = s.id
            ) AS used_in_chain

        FROM supply_sources s

        WHERE s.actor_id = %s

        ORDER BY s.created_at DESC

        LIMIT %s
        OFFSET %s

    """, (
        actor_id,
        limit,
        offset
    ))

    sources = cursor.fetchall()

    conn.close()

    return sources