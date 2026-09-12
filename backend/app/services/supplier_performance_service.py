from fastapi import HTTPException
from app.engines.supplier_performance_engine import calculate_supplier_performance,save_supplier_performance
from app.models.suppliers import get_supplier_by_id

def get_supplier_performance(cursor,supplier_id):
    if not get_supplier_by_id(cursor,supplier_id): raise HTTPException(404,"Supplier not found.")
    return calculate_supplier_performance(cursor,supplier_id)

def refresh_supplier_performance(cursor,supplier_id):
    if not get_supplier_by_id(cursor,supplier_id): raise HTTPException(404,"Supplier not found.")
    return dict(save_supplier_performance(cursor,calculate_supplier_performance(cursor,supplier_id)))
