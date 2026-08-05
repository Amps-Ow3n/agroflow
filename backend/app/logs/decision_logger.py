from datetime import datetime
from app.core.logger import log_info

def log_decision(
    cursor,
    actor_id,
    decision_type,
    reference_id,
    explanation
):
    """
    Stores explainable decision trail.
    """
    log_info(

    message="Decision recorded",

    user_id=actor_id,

    action=decision_type,

    entity="decision",

    extra={
        "reference_id": reference_id,
        "explanation": explanation
    }

)
    cursor.execute("""
        INSERT INTO decision_logs (
            actor_id,
            decision_type,
            reference_id,
            explanation,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (
        actor_id,
        decision_type,
        reference_id,
        explanation,
        datetime.utcnow()
    ))