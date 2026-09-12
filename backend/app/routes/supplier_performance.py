from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from app.core.db import get_db

from app.core.dependencies import (
    require_procurement_viewer,
    require_supplier_user,
    require_supplier_performance_view,
    require_supplier_performance_refresh,
)

from app.services.supplier_performance_service import (
    get_supplier_performance,
    refresh_supplier_performance
)

from app.models.suppliers import (
    get_supplier_by_id,
    get_supplier_by_user
)

from app.core.logger import log_error
from app.core.transactions import write_transaction


router = APIRouter(
    prefix="/suppliers",
    tags=["Supplier Performance"]
)


# =========================================================
# SUPPLIER PERFORMANCE
# SCHOOL / PROCUREMENT VIEW
# =========================================================

@router.get(
    "/{supplier_id}/performance"
)
def get_performance(
    supplier_id: int,
    user=Depends(
        require_supplier_performance_view
    )
):

    conn, cursor = get_db()

    try:

        supplier = get_supplier_by_id(
            cursor,
            supplier_id
        )

        if not supplier:

            raise HTTPException(
                status_code=404,
                detail="Supplier not found."
            )


        performance = get_supplier_performance(
            cursor,
            supplier_id
        )


        return {
            "supplier": {
                "id":
                    supplier["id"],

                "supplier_code":
                    supplier["supplier_code"],

                "organization_name":
                    supplier["organization_name"],

                "verification_status":
                    supplier[
                        "verification_status"
                    ]
            },

            "performance":
                performance
        }


    except HTTPException:

        raise


    except Exception as e:

        log_error(
            message=
                "Supplier performance retrieval failed",

            user_id=
                user["user"]["id"],

            action=
                "GET_SUPPLIER_PERFORMANCE_ERROR",

            entity=
                "supplier",

            extra={
                "supplier_id":
                    supplier_id,

                "exception":
                    str(e)
            }
        )

        raise HTTPException(
            status_code=500,
            detail=
                "Unable to load supplier performance."
        )


    finally:

        conn.close()


# =========================================================
# REFRESH PERFORMANCE SNAPSHOT
# =========================================================

@router.post(
    "/{supplier_id}/performance/refresh"
)
def refresh_performance(
    supplier_id: int,
    user=Depends(
        require_supplier_performance_refresh
    )
):

    conn, cursor = get_db()

    try:

        with write_transaction(conn):
            result = refresh_supplier_performance(
                cursor,
                supplier_id
            )

        return {
            "message":
                "Supplier performance refreshed.",

            "performance":
                result
        }


    except HTTPException:

        conn.rollback()
        raise


    except Exception as e:

        conn.rollback()

        log_error(
            message=
                "Supplier performance refresh failed",

            user_id=
                user["user"]["id"],

            action=
                "REFRESH_SUPPLIER_PERFORMANCE_ERROR",

            entity=
                "supplier",

            extra={
                "supplier_id":
                    supplier_id,

                "exception":
                    str(e)
            }
        )

        raise HTTPException(
            status_code=500,
            detail=
                "Unable to refresh supplier performance."
        )


    finally:

        conn.close()


# =========================================================
# CURRENT SUPPLIER PERFORMANCE
# =========================================================

@router.get(
    "/me/performance"
)
def get_my_performance(
    user=Depends(
        require_supplier_user
    )
):

    conn, cursor = get_db()

    try:

        supplier = get_supplier_by_user(
            cursor,
            user["user"]["id"]
        )

        if not supplier:

            raise HTTPException(
                status_code=404,
                detail=
                    "Supplier profile not found."
            )


        performance = get_supplier_performance(
            cursor,
            supplier["id"]
        )


        return {
            "supplier": dict(supplier),

            "performance":
                performance
        }


    finally:

        conn.close()