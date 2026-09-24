from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile
from fastapi.responses import FileResponse
from app.core.dependencies import require_user, require_evidence_upload
from app.core.db import get_db
from app.core.authorization import membership_has_permission
from app.services.evidence_security_service import safe_evidence_path
from app.services.evidence_document_service import create_evidence_document
from app.core.config import settings
from app.core.transactions import write_transaction

router = APIRouter(tags=["Evidence"])


def _evidence_context(cursor, evidence_id):
    cursor.execute("""
        SELECT ed.id, ed.storage_reference, ed.original_filename, ed.mime_type,
               ed.visibility, p.organization_id, po_supplier_org.organization_id AS supplier_organization_id
        FROM evidence_documents ed
        JOIN procurements p ON p.id = ed.procurement_id
        LEFT JOIN purchase_orders po ON po.procurement_id = p.id
        LEFT JOIN suppliers po_supplier ON po_supplier.id = po.supplier_id
        LEFT JOIN organizations po_supplier_org ON po_supplier_org.id = po_supplier.organization_id
        WHERE ed.id = %s
    """, (evidence_id,))
    return cursor.fetchone()


@router.post("/evidence/{procurement_id}/upload", status_code=201)
def upload_evidence(
    procurement_id: int,
    document_type: str = Form(...),
    visibility: str = Form("INTERNAL"),
    event_id: int | None = Form(None),
    file: UploadFile = File(...),
    user=Depends(require_evidence_upload),
):
    conn, cursor = get_db()
    try:
        with write_transaction(conn):
            evidence = create_evidence_document(
                cursor,
                settings.EVIDENCE_STORAGE_DIR,
                procurement_id,
                user["user"]["id"],
                file,
                document_type,
                visibility,
                event_id,
            )
            return {"evidence": evidence}
    finally:
        conn.close()


@router.get("/evidence/{evidence_id}/download")
def download_evidence(evidence_id: int, user=Depends(require_user)):
    conn, cursor = get_db()
    try:
        evidence = _evidence_context(cursor, evidence_id)
        if not evidence:
            raise HTTPException(404, "Evidence document not found.")
        organization_ids = [evidence["organization_id"]]
        if evidence.get("supplier_organization_id") is not None:
            organization_ids.append(evidence["supplier_organization_id"])

        cursor.execute("""
            SELECT om.*, o.status organization_status, o.verification_status,
                   o.organization_type
            FROM organization_memberships om
            JOIN organizations o ON o.id = om.organization_id
            WHERE om.organization_id = ANY(%s) AND om.user_id = %s
              AND om.status = 'ACTIVE'
        """, (organization_ids, user["user"]["id"]))
        memberships = cursor.fetchall()

        school_membership = next((m for m in memberships if m["organization_id"] == evidence["organization_id"]), None)
        if school_membership and school_membership["organization_status"] == "ACTIVE" and school_membership["verification_status"] == "VERIFIED" and membership_has_permission(school_membership, "evidence:view"):
            membership = school_membership
        elif evidence["visibility"] == "SUPPLIER_VISIBLE":
            supplier_membership = next((m for m in memberships if m["organization_id"] == evidence.get("supplier_organization_id") and m["organization_type"] == "SUPPLIER"), None)
            if not supplier_membership or supplier_membership["organization_status"] != "ACTIVE" or supplier_membership["verification_status"] != "VERIFIED" or not membership_has_permission(supplier_membership, "evidence:view"):
                raise HTTPException(403, "You are not authorized to access this evidence.")
            membership = supplier_membership
        else:
            raise HTTPException(403, "You are not authorized to access this evidence.")

        path = safe_evidence_path(evidence["storage_reference"])
        if not path.is_file():
            raise HTTPException(404, "Evidence file is unavailable.")
        return FileResponse(path=str(path), media_type=evidence["mime_type"], filename=evidence["original_filename"])
    finally:
        conn.close()
