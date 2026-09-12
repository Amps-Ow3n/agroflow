from fastapi import HTTPException


def get_purchase_order_line_context(
    cursor,
    purchase_order_line_id
):
    cursor.execute(
        """
        SELECT
            pol.id AS purchase_order_line_id,

            pol.purchase_order_id,
            pol.procurement_item_id,
            pol.quantity AS ordered_quantity,

            po.procurement_id,
            po.supplier_id,
            po.status AS purchase_order_status,

            p.organization_id,
            p.status AS procurement_status,
            p.required_by_date

        FROM purchase_order_lines pol

        JOIN purchase_orders po
            ON po.id = pol.purchase_order_id

        JOIN procurements p
            ON p.id = po.procurement_id

        WHERE pol.id = %s

        FOR UPDATE
        """,
        (purchase_order_line_id,)
    )

    return cursor.fetchone()


def get_commitment_context(
    cursor,
    commitment_id
):
    cursor.execute(
        """
        SELECT
            c.id AS commitment_id,
            c.purchase_order_id,
            c.purchase_order_line_id,
            c.supplier_id,

            pol.purchase_order_id
                AS line_purchase_order_id,

            po.procurement_id,
            po.supplier_id
                AS purchase_order_supplier_id,

            p.organization_id,
            p.status AS procurement_status,
            po.status AS purchase_order_status

        FROM supplier_commitments c

        JOIN purchase_order_lines pol
            ON pol.id = c.purchase_order_line_id

        JOIN purchase_orders po
            ON po.id = c.purchase_order_id

        JOIN procurements p
            ON p.id = po.procurement_id

        WHERE c.id = %s

        FOR UPDATE
        """,
        (commitment_id,)
    )

    return cursor.fetchone()


def get_delivery_context(
    cursor,
    delivery_id
):
    cursor.execute(
        """
        SELECT
            d.id AS delivery_id,
            d.commitment_id,

            c.purchase_order_id,
            c.purchase_order_line_id,
            c.supplier_id,

            po.procurement_id,
            po.supplier_id
                AS purchase_order_supplier_id,

            p.organization_id,
            p.status AS procurement_status

        FROM deliveries d

        JOIN supplier_commitments c
            ON c.id = d.commitment_id

        JOIN purchase_orders po
            ON po.id = c.purchase_order_id

        JOIN procurements p
            ON p.id = po.procurement_id

        WHERE d.id = %s

        FOR UPDATE
        """,
        (delivery_id,)
    )

    return cursor.fetchone()


def get_inspection_context(
    cursor,
    inspection_id
):
    cursor.execute(
        """
        SELECT
            i.id AS inspection_id,
            i.delivery_id,
            i.result,

            d.commitment_id,

            c.purchase_order_id,
            c.purchase_order_line_id,
            c.supplier_id,

            po.procurement_id,

            p.organization_id

        FROM inspections i

        JOIN deliveries d
            ON d.id = i.delivery_id

        JOIN supplier_commitments c
            ON c.id = d.commitment_id

        JOIN purchase_orders po
            ON po.id = c.purchase_order_id

        JOIN procurements p
            ON p.id = po.procurement_id

        WHERE i.id = %s

        FOR UPDATE
        """,
        (inspection_id,)
    )

    return cursor.fetchone()