import json


def create_audit_log(
    cursor,
    user_id,
    action,
    entity_type,
    entity_id=None,
    old_data=None,
    new_data=None
):

    cursor.execute(
        """
        INSERT INTO audit_logs
        (
            user_id,
            action,
            entity_type,
            entity_id,
            old_data,
            new_data
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )

        """,
        (
            user_id,
            action,
            entity_type,
            entity_id,

            json.dumps(old_data)
            if old_data
            else None,

            json.dumps(new_data)
            if new_data
            else None
        )
    )