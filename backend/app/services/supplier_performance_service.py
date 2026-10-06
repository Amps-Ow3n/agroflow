from fastapi import HTTPException
from app.engines.supplier_performance_engine import calculate_supplier_performance,save_supplier_performance
from app.models.suppliers import get_supplier_by_id

def get_supplier_performance(cursor,supplier_id,exclude_procurement_id=None):
    if not get_supplier_by_id(cursor,supplier_id): raise HTTPException(404,"Supplier not found.")
    return calculate_supplier_performance(cursor,supplier_id,exclude_procurement_id=exclude_procurement_id)

def refresh_supplier_performance(cursor,supplier_id):
    if not get_supplier_by_id(cursor,supplier_id): raise HTTPException(404,"Supplier not found.")
    return dict(save_supplier_performance(cursor,calculate_supplier_performance(cursor,supplier_id)))


def get_supplier_history(cursor, supplier_id):
    if not get_supplier_by_id(cursor, supplier_id):
        raise HTTPException(404, "Supplier not found.")

    cursor.execute(
        """
        SELECT
            p.id AS procurement_id,
            p.procurement_identifier,
            p.title,
            p.status AS procurement_status,
            p.required_by_date,
            p.updated_at,
            po.id AS purchase_order_id,
            po.order_number,
            sc.id AS commitment_id,
            sc.promised_qty,
            sc.delivery_start,
            sc.delivery_end,
            sc.status AS commitment_status,
            COALESCE(SUM(dl.actual_quantity), 0) AS delivered_quantity,
            COALESCE(SUM(i.received_qty) FILTER (WHERE i.result = 'ACCEPTED'), 0) AS accepted_quantity,
            COUNT(DISTINCT d.id) AS delivery_count,
            COUNT(DISTINCT i.id) AS inspection_count,
            COUNT(DISTINCT i.id) FILTER (WHERE i.result = 'REJECTED') AS rejected_inspections,
            COUNT(DISTINCT i.id) FILTER (WHERE i.delay_status = 'DELAYED') AS delayed_inspections
        FROM procurements p
        JOIN purchase_orders po ON po.procurement_id = p.id
        JOIN supplier_commitments sc
          ON sc.purchase_order_id = po.id
         AND sc.supplier_id = %s
        LEFT JOIN deliveries d ON d.commitment_id = sc.id
        LEFT JOIN delivery_lines dl ON dl.delivery_id = d.id
        LEFT JOIN inspections i ON i.delivery_id = d.id
        WHERE p.status = 'COMPLETED'
        GROUP BY
            p.id, p.procurement_identifier, p.title, p.status, p.required_by_date, p.updated_at,
            po.id, po.order_number, sc.id, sc.promised_qty, sc.delivery_start, sc.delivery_end, sc.status
        ORDER BY p.updated_at DESC, p.id DESC
        """,
        (supplier_id,),
    )
    return [dict(row) for row in cursor.fetchall()]
