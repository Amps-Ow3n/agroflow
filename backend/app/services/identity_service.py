from app.core.db import get_db


def get_user_identity(user_id: int):

    conn, cursor = get_db()

    try:

        cursor.execute(
            """
            SELECT
                u.id,
                u.name AS full_name,
                u.email,
                u.status,
                u.is_system_admin,
                u.created_at
            FROM users u
            WHERE u.id = %s
            """,
            (user_id,),
        )

        user = cursor.fetchone()

        if not user:
            return None

        cursor.execute(
            """
            SELECT
                m.id AS membership_id,
                m.status AS membership_status,

                o.id AS organization_id,
                o.name AS organization_name,
                o.organization_type,
                o.status AS organization_status,
                o.verification_status

            FROM organization_memberships m

            JOIN organizations o
                ON o.id = m.organization_id

            WHERE m.user_id = %s

            ORDER BY m.id
            """,
            (user_id,),
        )

        membership_rows = cursor.fetchall()

        memberships = []

        for row in membership_rows:

            cursor.execute(
                """
                SELECT
                    r.code,
                    r.name

                FROM membership_responsibilities mr

                JOIN responsibilities r
                    ON r.id = mr.responsibility_id

                WHERE mr.membership_id = %s

                ORDER BY r.code
                """,
                (row["membership_id"],),
            )

            responsibilities = cursor.fetchall()

            memberships.append(
                {
                    "id": row["membership_id"],

                    "status": row["membership_status"],

                    "organization": {
                        "id": row["organization_id"],
                        "name": row["organization_name"],
                        "organization_type": row[
                            "organization_type"
                        ],
                        "status": row[
                            "organization_status"
                        ],
                        "verification_status": row[
                            "verification_status"
                        ],
                    },

                    "responsibilities": responsibilities,
                }
            )

        return {
            "user": {
                "id": user["id"],
                "full_name": user["full_name"],
                "email": user["email"],
                "status": user["status"],
                "is_system_admin": user[
                    "is_system_admin"
                ],
                "created_at": user["created_at"],
            },

            "memberships": memberships,
        }

    finally:

        conn.close()