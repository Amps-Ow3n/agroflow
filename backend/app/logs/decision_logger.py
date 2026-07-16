# backend/app/logs/decision_logger.py

from datetime import datetime


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