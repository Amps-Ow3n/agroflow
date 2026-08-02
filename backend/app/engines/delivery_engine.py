def compute_truth_confidence(
    verification_status,
    quality_status,
    delay_status
):
    score = 1.0

    if verification_status != "VERIFIED":
        score -= 0.4

    if quality_status == "FAILED":
        score -= 0.3

    if delay_status == "DELAYED":
        score -= 0.2

    return {

"score":
max(
0.0,
round(score,2)
),

"factors":{

"verification":
verification_status,

"quality":
quality_status,

"delay":
delay_status

}

}