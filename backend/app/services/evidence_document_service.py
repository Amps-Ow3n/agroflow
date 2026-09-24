from pathlib import Path
from uuid import uuid4

from app.core.config import settings

from fastapi import HTTPException, UploadFile


ALLOWED_DOCUMENT_TYPES = {
    "RFQ",
    "QUOTATION",
    "SUPPLIER_RESPONSE",
    "EVALUATION",
    "PURCHASE_ORDER",
    "COMMITMENT",
    "DELIVERY_NOTE",
    "GRN",
    "INSPECTION_RECORD",
    "INVOICE",
    "APPROVAL",
}


ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


MAX_FILE_SIZE = settings.MAX_EVIDENCE_FILE_SIZE

ALLOWED_EXTENSIONS = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
}

SUPPLIER_VISIBLE_DOCUMENT_TYPES = {
    "SUPPLIER_RESPONSE",
    "COMMITMENT",
    "DELIVERY_NOTE"
}


def validate_visibility_for_document_type(
    document_type,
    visibility
):

    if (
        visibility == "SUPPLIER_VISIBLE"
        and
        document_type
        not in SUPPLIER_VISIBLE_DOCUMENT_TYPES
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "This document type cannot be "
                "supplier-visible in Phase A."
            )
        )
    
def validate_document_type(
    document_type
):

    if document_type not in ALLOWED_DOCUMENT_TYPES:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported evidence document type."
            )
        )


def validate_visibility(
    visibility
):

    if visibility not in {
        "INTERNAL",
        "SUPPLIER_VISIBLE"
    }:

        raise HTTPException(
            status_code=400,
            detail="Invalid document visibility."
        )


def validate_file(
    file: UploadFile
):

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="A file is required."
        )


    if file.content_type not in ALLOWED_MIME_TYPES:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only PDF, JPEG, and PNG files "
                "are supported in Phase A."
            )
        )

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS[file.content_type]:
        raise HTTPException(
            status_code=400,
            detail="The file extension does not match the declared document type."
        )

    header = file.file.read(16)
    file.file.seek(0)

    signatures = {
        "application/pdf": header.startswith(b"%PDF-"),
        "image/png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": header.startswith(b"\xff\xd8\xff"),
    }

    if not signatures[file.content_type]:
        raise HTTPException(
            status_code=400,
            detail="The file contents do not match the declared document type."
        )


def get_procurement_for_user(
    cursor,
    procurement_id,
    user_id
):

    cursor.execute(
        """
        SELECT
            p.id,
            p.organization_id,
            p.status
        FROM procurements p
        JOIN organization_memberships om
            ON om.organization_id = p.organization_id
        JOIN organizations o
            ON o.id = p.organization_id
        WHERE p.id = %s
          AND om.user_id = %s
          AND om.status = 'ACTIVE'
          AND o.status = 'ACTIVE'
          AND o.verification_status = 'VERIFIED'
        LIMIT 1
        """,
        (
            procurement_id,
            user_id
        )
    )

    return cursor.fetchone()


def validate_event_belongs_to_procurement(
    cursor,
    event_id,
    procurement_id
):

    if event_id is None:

        return


    cursor.execute(
        """
        SELECT id
        FROM procurement_events
        WHERE id = %s
          AND procurement_id = %s
        LIMIT 1
        """,
        (
            event_id,
            procurement_id
        )
    )

    event = cursor.fetchone()

    if not event:

        raise HTTPException(
            status_code=400,
            detail=(
                "The selected procurement event "
                "does not belong to this procurement."
            )
        )


def save_uploaded_file(
    file: UploadFile,
    storage_root: Path,
    procurement_id: int
):

    extension = ""

    if file.filename and "." in file.filename:

        extension = (
            "." +
            file.filename.rsplit(
                ".",
                1
            )[1].lower()
        )


    generated_name = (
        f"{uuid4().hex}{extension}"
    )


    procurement_directory = (
        storage_root /
        "procurements" /
        str(procurement_id) /
        "evidence"
    )

    procurement_directory.mkdir(
        parents=True,
        exist_ok=True
    )


    physical_path = (
        procurement_directory /
        generated_name
    )


    total_size = 0


    with physical_path.open("wb") as output:

        while True:

            chunk = file.file.read(
                1024 * 1024
            )

            if not chunk:
                break

            total_size += len(chunk)

            if total_size > settings.MAX_EVIDENCE_FILE_SIZE:

                output.close()

                physical_path.unlink(
                    missing_ok=True
                )

                # Do not leave empty procurement/evidence directories behind
                # after rejecting an oversized upload. The file itself is the
                # security boundary, but cleanup keeps failed attacks from
                # accumulating filesystem clutter.
                for directory in (physical_path.parent, physical_path.parent.parent):
                    try:
                        directory.rmdir()
                    except OSError:
                        pass

                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"Evidence file exceeds the {settings.MAX_EVIDENCE_FILE_SIZE // (1024 * 1024)} MB Phase A limit."
                    )
                )

            output.write(chunk)


    storage_reference = str(
        physical_path.relative_to(
            storage_root
        )
    ).replace("\\", "/")


    return (
        storage_reference,
        total_size
    )


def create_evidence_document(
    cursor,
    storage_root,
    procurement_id,
    user_id,
    file,
    document_type,
    visibility,
    event_id=None
):

    validate_document_type(
        document_type
    )

    validate_visibility(
        visibility
    )

    validate_visibility_for_document_type(
    document_type,
    visibility
)
    
    validate_file(file)


    procurement = get_procurement_for_user(
        cursor,
        procurement_id,
        user_id
    )

    if not procurement:

        raise HTTPException(
            status_code=404,
            detail="Procurement not found."
        )


    validate_event_belongs_to_procurement(
        cursor,
        event_id,
        procurement_id
    )


    # --------------------------------------------------
    # SECURITY DECISION
    #
    # Supplier-visible evidence must not be created
    # by simply trusting a client-provided visibility
    # value.
    #
    # The route layer must establish that the uploader
    # is allowed to create supplier-visible evidence.
    # --------------------------------------------------

    storage_reference = None
    physical_file_created = False


    try:

        (
            storage_reference,
            file_size
        ) = save_uploaded_file(
            file,
            storage_root,
            procurement_id
        )

        physical_file_created = True


        cursor.execute(
            """
            INSERT INTO evidence_documents
            (
                procurement_id,
                event_id,
                document_type,
                document_name,
                original_filename,
                mime_type,
                file_size,
                storage_reference,
                visibility,
                uploaded_by
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING
                id,
                procurement_id,
                event_id,
                document_type,
                document_name,
                original_filename,
                mime_type,
                file_size,
                storage_reference,
                visibility,
                uploaded_by,
                uploaded_at
            """,
            (
                procurement_id,
                event_id,
                document_type,
                file.filename,
                file.filename,
                file.content_type,
                file_size,
                storage_reference,
                visibility,
                user_id
            )
        )

        return cursor.fetchone()


    except Exception:

        if (
            physical_file_created
            and storage_reference
        ):

            (
                storage_root /
                storage_reference
            ).unlink(
                missing_ok=True
            )

        raise