from app.utils.validators import validate_required

def compute_delivery_ratio(
    promised,
    delivered
):
    if promised == 0:
        return 0

    return delivered / promised

def compute_delay_penalty(deliveries):
    late = sum(
        1
        for d in deliveries
        if d["delay_status"] == "DELAYED"
    )

    return late * 0.1

def compute_quality_penalty(deliveries):
    failed = sum(
        1
        for d in deliveries
        if d["quality_status"] == "FAILED"
    )

    return failed * 0.15

def aggregate_reliability_score(
    ratio,
    delay_penalty,
    quality_penalty
):
    score = (
        (ratio * 100)
        - (delay_penalty * 100)
        - (quality_penalty * 100)
    )

    return max(
        0,
        min(100, round(score, 2))
    )

def compute_supplier_reliability(
    cursor,
    supplier_id
):
    validate_required(supplier_id, "supplier_id")

    cursor.execute("""
        SELECT id, promised_qty
        FROM supplier_commitments
        WHERE supplier_id = %s
    """, (supplier_id,))

    commitments = cursor.fetchall()

    scores = []

    for c in commitments:
        cursor.execute("""
            SELECT *
            FROM deliveries
            WHERE commitment_id = %s
        """, (c["id"],))

        deliveries = cursor.fetchall()

        delivered = sum(
    (d.get("received_qty") or 0)
    for d in deliveries
)

        ratio = compute_delivery_ratio(
            c["promised_qty"],
            delivered
        )

        delay_penalty = compute_delay_penalty(deliveries)

        quality_penalty = compute_quality_penalty(deliveries)

        score = aggregate_reliability_score(
            ratio,
            delay_penalty,
            quality_penalty
        )

        scores.append(score)

    if len(scores) < 3:
       return {
        "score": round(sum(scores) / len(scores), 2) if scores else 0,
        "confidence": "low_sample_warning"
    }
    return {
    "score": round(sum(scores) / len(scores), 2),
    "confidence": "stable"
}