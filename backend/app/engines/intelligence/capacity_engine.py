from app.utils.normalizers import normalize_product


ACTIVE_COMMITMENT_STATUSES = (
    "PENDING",
    "ACCEPTED",
)


def compute_supplier_capacity(
    cursor,
    supplier_id
):
    """
    Calculates capacity for one supplier.

    Aggregation level:

        supplier + product

    Business meaning:

        available =
            total declared supply across active sources

        committed =
            total promised quantity across active commitments

        remaining =
            available - committed,
            never below zero

        shortfall =
            committed - available,
            only when commitments exceed supply
    """

    cursor.execute("""
        SELECT
            actor_id AS supplier_id,
            MAX(actor_name) AS supplier_name,
            LOWER(product) AS product,
            SUM(qty_available) AS available

        FROM supply_sources

        WHERE actor_id = %s
        AND is_archived = FALSE

        GROUP BY
            actor_id,
            LOWER(product)

        ORDER BY
            LOWER(product)
    """, (
        supplier_id,
    ))

    sources = cursor.fetchall()

    results = []

    for source in sources:

        product = normalize_product(
            source["product"]
        )

        cursor.execute("""
            SELECT
                COALESCE(
                    SUM(promised_qty),
                    0
                ) AS committed

            FROM supplier_commitments

            WHERE supplier_id = %s

            AND LOWER(product) = LOWER(%s)

            AND status IN (
                'PENDING',
                'ACCEPTED'
            )
        """, (
            supplier_id,
            product
        ))

        commitment_row = cursor.fetchone()

        committed = commitment_row["committed"]

        available = source["available"]

        remaining = max(
            available - committed,
            0
        )

        shortfall = max(
            committed - available,
            0
        )

        utilization = (
            round(
                (committed / available) * 100,
                2
            )
            if available > 0
            else 0
        )

        if shortfall > 0:

            status = "OVERCOMMITTED"

        elif utilization >= 80:

            status = "HIGH_UTILIZATION"

        else:

            status = "HEALTHY"

        results.append({

            "source_id": None,

            "supplier_id":
                source["supplier_id"],

            "supplier_name":
                source["supplier_name"],

            "product":
                product,

            "available":
                available,

            "committed":
                committed,

            "remaining":
                remaining,

            "shortfall":
                shortfall,

            "utilization":
                utilization,

            "status":
                status

        })

    return results


def compute_network_capacity(
    cursor
):
    """
    Calculates capacity across the entire supplier network.

    Returns one capacity result per:

        supplier + product
    """

    cursor.execute("""
        SELECT DISTINCT
            actor_id AS supplier_id

        FROM supply_sources

        WHERE is_archived = FALSE

        ORDER BY actor_id
    """)

    suppliers = cursor.fetchall()

    network = []

    for supplier in suppliers:

        capacity = compute_supplier_capacity(
            cursor,
            supplier["supplier_id"]
        )

        if capacity:

            network.append({

                "supplier_id":
                    supplier["supplier_id"],

                "supplier_name":
                    capacity[0]["supplier_name"],

                "capacity":
                    capacity

            })

    return network