from psycopg2.extras import RealDictCursor


def get_supplier_by_id(cursor, supplier_id):
    cursor.execute(
        """
        SELECT
            s.id,
            s.organization_id,
            s.status,
            s.supplier_code,
            s.created_at,
            s.updated_at,

            o.name AS organization_name,
            o.organization_type,
            o.verification_status,
            o.registration_number,
            o.address,
            o.phone,
            o.email

        FROM suppliers s

        JOIN organizations o
            ON o.id = s.organization_id

        WHERE s.id = %s
        """,
        (supplier_id,)
    )

    return cursor.fetchone()


def get_supplier_by_user(cursor, user_id):

    cursor.execute(
        """
        SELECT
            s.id,
            s.organization_id,
            s.status,
            s.supplier_code,

            o.name AS organization_name,
            o.verification_status

        FROM suppliers s

        JOIN organization_memberships om
            ON om.organization_id = s.organization_id

        JOIN organizations o
            ON o.id = s.organization_id

        WHERE om.user_id = %s

        AND om.status = 'ACTIVE'

        AND o.organization_type = 'SUPPLIER'

        AND s.status = 'ACTIVE'

        ORDER BY s.id

        LIMIT 1
        """,
        (user_id,)
    )

    return cursor.fetchone()


def get_supplier_capabilities(cursor, supplier_id):

    cursor.execute(
        """
        SELECT
            id,
            capability,
            status,
            created_at,
            updated_at

        FROM supplier_capabilities

        WHERE supplier_id = %s

        ORDER BY capability
        """,
        (supplier_id,)
    )

    return cursor.fetchall()


def get_supplier_products(cursor, supplier_id):

    cursor.execute(
        """
        SELECT
            id,
            product,
            status,
            created_at,
            updated_at

        FROM supplier_products

        WHERE supplier_id = %s

        ORDER BY product
        """,
        (supplier_id,)
    )

    return cursor.fetchall()


def get_supplier_contacts(cursor, supplier_id):

    cursor.execute(
        """
        SELECT
            id,
            contact_name,
            phone,
            email,
            role,
            is_primary,
            status,
            created_at,
            updated_at

        FROM supplier_contacts

        WHERE supplier_id = %s

        ORDER BY is_primary DESC, contact_name
        """,
        (supplier_id,)
    )

    return cursor.fetchall()