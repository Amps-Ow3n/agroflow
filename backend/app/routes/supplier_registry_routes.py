from fastapi import APIRouter,Depends,HTTPException
from app.core.db import get_db
from app.core.dependencies import (
    require_supplier_user,
    require_supplier_view,
    require_supplier_update,
    require_permission,
)

from app.core.authorization import (
    PERMISSION_SUPPLIER_UPDATE,
)
from app.core.transactions import write_transaction
from app.models.suppliers import get_supplier_by_id,get_supplier_by_user,get_supplier_capabilities,get_supplier_products,get_supplier_contacts
from app.schemas.supplier_schema import CapabilityCreate,ProductCreate,ContactCreate

router=APIRouter(prefix="/suppliers",tags=["Suppliers"])

@router.get("/me")
def me(user=Depends(require_supplier_user)):
    conn,cursor=get_db()
    try:
        supplier=get_supplier_by_user(cursor,user["user"]["id"])
        if not supplier: raise HTTPException(404,"Supplier profile not found.")
        return {"supplier":dict(supplier),"capabilities":[dict(r) for r in get_supplier_capabilities(cursor,supplier["id"])],"products":[dict(r) for r in get_supplier_products(cursor,supplier["id"])],"contacts":[dict(r) for r in get_supplier_contacts(cursor,supplier["id"])]}
    finally: conn.close()

@router.get("/{supplier_id}")
def detail(supplier_id:int,user=Depends(require_supplier_view)):
    conn,cursor=get_db()
    try:
        supplier=get_supplier_by_id(cursor,supplier_id)
        if not supplier: raise HTTPException(404,"Supplier not found.")
        return {"supplier":dict(supplier),"capabilities":[dict(r) for r in get_supplier_capabilities(cursor,supplier_id)],"products":[dict(r) for r in get_supplier_products(cursor,supplier_id)],"contacts":[dict(r) for r in get_supplier_contacts(cursor,supplier_id)]}
    finally: conn.close()

@router.post("/me/capabilities")
def add_capability(
    payload: CapabilityCreate,
    user=Depends(
        require_permission(
            PERMISSION_SUPPLIER_UPDATE,
            organization_type="SUPPLIER",
        )
    ),
):
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            supplier=get_supplier_by_user(cursor,user["user"]["id"])
            if not supplier: raise HTTPException(404,"Supplier profile not found.")
            cursor.execute("""INSERT INTO supplier_capabilities(supplier_id,capability) VALUES(%s,%s)
                              ON CONFLICT(supplier_id,capability) DO UPDATE SET status='ACTIVE',updated_at=CURRENT_TIMESTAMP
                              RETURNING *""",(supplier["id"],payload.capability.strip()))
            return dict(cursor.fetchone())
    finally: conn.close()

@router.post("/me/products")
def add_product(
    payload: ProductCreate,
    user=Depends(
        require_permission(
            PERMISSION_SUPPLIER_UPDATE,
            organization_type="SUPPLIER",
        )
    ),
):    
    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            supplier=get_supplier_by_user(cursor,user["user"]["id"])
            if not supplier: raise HTTPException(404,"Supplier profile not found.")
            cursor.execute("""INSERT INTO supplier_products(supplier_id,product) VALUES(%s,%s)
                              ON CONFLICT(supplier_id,product) DO UPDATE SET status='ACTIVE',updated_at=CURRENT_TIMESTAMP
                              RETURNING *""",(supplier["id"],payload.product.strip()))
            return dict(cursor.fetchone())
    finally: conn.close()

@router.post("/me/contacts")
def add_contact(
    payload: ContactCreate,
    user=Depends(
        require_permission(
            PERMISSION_SUPPLIER_UPDATE,
            organization_type="SUPPLIER",
        )
    ),
):

    conn,cursor=get_db()
    try:
        with write_transaction(conn):
            supplier=get_supplier_by_user(cursor,user["user"]["id"])
            if not supplier: raise HTTPException(404,"Supplier profile not found.")
            if payload.is_primary:
                cursor.execute("UPDATE supplier_contacts SET is_primary=FALSE,updated_at=CURRENT_TIMESTAMP WHERE supplier_id=%s",(supplier["id"],))
            cursor.execute("""INSERT INTO supplier_contacts(supplier_id,contact_name,phone,email,role,is_primary)
                              VALUES(%s,%s,%s,%s,%s,%s) RETURNING *""",(supplier["id"],payload.contact_name.strip(),payload.phone,payload.email,payload.role,payload.is_primary))
            return dict(cursor.fetchone())
    finally: conn.close()

@router.get("/{supplier_id}/eligibility")
def eligibility(supplier_id:int,user=Depends(require_supplier_view)):
    conn,cursor=get_db()
    try:
        supplier=get_supplier_by_id(cursor,supplier_id)
        if not supplier: raise HTTPException(404,"Supplier not found.")
        products=len(get_supplier_products(cursor,supplier_id)); capabilities=len(get_supplier_capabilities(cursor,supplier_id)); contacts=len(get_supplier_contacts(cursor,supplier_id))
        return {"supplier_id":supplier_id,"eligible":supplier["status"]=="ACTIVE" and supplier["verification_status"]=="VERIFIED" and products>0,
                "verification_status":supplier["verification_status"],"active":supplier["status"]=="ACTIVE","has_products":products>0,"has_capabilities":capabilities>0,"has_contacts":contacts>0}
    finally: conn.close()
