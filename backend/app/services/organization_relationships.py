def get_active_membership(
    cursor,
    user_id,
    organization_id
):
    cursor.execute(
        """
        SELECT
            om.id,
            om.user_id,
            om.organization_id,
            om.status
        FROM organization_memberships om
        WHERE om.user_id = %s
          AND om.organization_id = %s
          AND om.status = 'ACTIVE'
        """,
        (
            user_id,
            organization_id
        )
    )

    return cursor.fetchone()


def get_supplier_with_organization(
    cursor,
    supplier_id
):
    cursor.execute(
        """
        SELECT
            s.id AS supplier_id,
            s.organization_id,

            o.id AS organization_id,
            o.name AS organization_name,
            o.organization_type,
            o.status AS organization_status

        FROM suppliers s

        JOIN organizations o
            ON o.id = s.organization_id

        WHERE s.id = %s

        FOR UPDATE
        """,
        (supplier_id,)
    )

    return cursor.fetchone()