def get_allocated_quantity(
    cursor,
    source_id
):

    cursor.execute("""

        SELECT

            COALESCE(
                SUM(allocated_qty),
                0
            ) AS allocated

        FROM procurement_chains

        WHERE source_id=%s

    """, (
        source_id,
    ))

    return cursor.fetchone()["allocated"]