import math

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

def predict_failure(risk):
    # Convert risk_score into smoother probability
    raw_score = risk.get("risk_score", 0)

    # Center around 0.5 and scale
    probability = sigmoid((raw_score - 0.5) * 5)

    if probability > 0.7:
        prediction = "Likely to FAIL next week"
    elif probability > 0.4:
        prediction = "Unstable"
    else:
        prediction = "Stable"

    return {
        "farmer_id": risk["farmer_id"],
        "failure_probability": round(probability, 2),
        "prediction": prediction
    }