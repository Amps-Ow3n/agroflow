def compute_delivery_reliability(
    cursor,
    supplier_id
):
    """
    Calculates observed delivery reliability.

    Important:

    A LOW_SAMPLE result is an early signal.

    It is not strong statistical evidence.
    """

    cursor.execute("""
        SELECT

            d.received_qty,
            d.delivered_qty,
            d.delay_status,
            d.quality_status

        FROM deliveries d

        JOIN supplier_commitments c
            ON d.commitment_id = c.id

        WHERE c.supplier_id = %s

    """, (
        supplier_id,
    ))

    deliveries = cursor.fetchall()

    if not deliveries:

        return {

            "score": 0,

            "confidence":
                "NO_DATA",

            "risk":
                "UNKNOWN",

            "delivery_count":
                0,

            "fulfilled":
                0,

            "delayed":
                0,

            "quality_failures":
                0,

            "confidence_message":
                "No verified delivery history is available."

        }

    total = len(deliveries)

    fulfilled = 0

    delayed = 0

    failed_quality = 0

    for delivery in deliveries:

        received = (
            delivery["received_qty"]
            or 0
        )

        delivered = (
            delivery["delivered_qty"]
            or 0
        )

        if received >= delivered:

            fulfilled += 1

        if delivery["delay_status"] == "DELAYED":

            delayed += 1

        if delivery["quality_status"] == "FAILED":

            failed_quality += 1

    fulfillment_rate = (
        fulfilled / total
    )

    delay_rate = (
        delayed / total
    )

    quality_failure_rate = (
        failed_quality / total
    )

    score = (

        (fulfillment_rate * 100)

        -

        (delay_rate * 20)

        -

        (quality_failure_rate * 30)

    )

    score = max(

        0,

        min(

            100,

            round(score, 2)

        )

    )

    if total < 3:
        score = min(
    score,
    70
)
        confidence = "LOW_SAMPLE"

        confidence_message = (

            f"Only {total} delivery "

            f"observation(s) are available. "

            "This is an early warning based "

            "on limited evidence."

        )

    else:

        confidence = "STABLE"

        confidence_message = (

            f"{total} delivery observations "

            "are available for this supplier."

        )

    if score >= 80:

        risk = "LOW"

    elif score >= 60:

        risk = "MEDIUM"

    else:

        risk = "HIGH"

    return {

        "score":
            score,

        "confidence":
            confidence,

        "risk":
            risk,

        "delivery_count":
            total,

        "fulfilled":
            fulfilled,

        "delayed":
            delayed,

        "quality_failures":
            failed_quality,

        "confidence_message":
            confidence_message

    }


def compute_supplier_ranking(
    cursor
):

    """
    Returns suppliers ranked by observed reliability.

    Supplier identity is resolved by the backend.
    """

    cursor.execute("""
        SELECT DISTINCT

            c.supplier_id,

            u.name AS supplier_name

        FROM supplier_commitments c

        JOIN users u
            ON u.id = c.supplier_id

        ORDER BY c.supplier_id

    """)

    suppliers = cursor.fetchall()

    rankings = []

    for supplier in suppliers:

        reliability = compute_delivery_reliability(

            cursor,

            supplier["supplier_id"]

        )

        rankings.append({

            "supplier_id":
                supplier["supplier_id"],

            "supplier_name":
                supplier["supplier_name"],

            "reliability":
                reliability

        })

    rankings.sort(

        key=lambda x:
        x["reliability"]["score"],

        reverse=True

    )

    return rankings