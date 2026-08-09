from fastapi import APIRouter, Depends, HTTPException

from app.core.db import get_db
from app.core.dependencies import require_supplier, require_user

from app.engines.chain_engine import build_procurement_chain
from app.engines.feasibility_engine import evaluate_commitment_feasibility
from app.engines.risk_engine import calculate_chain_risk
from app.utils.audit import create_audit_log
from app.core.logger import log_error
router = APIRouter(tags=["Chains"])

# ==============================
# BUILD CHAIN
# ==============================
@router.post("/chain/build/{commitment_id}")
def build_chain(
    commitment_id: int,
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    try:
        result = build_procurement_chain(
    cursor,
    commitment_id
)

        create_audit_log(

    cursor,

    user["id"],

    "BUILD_CHAIN",

    "procurement_chain",

    commitment_id,

    new_data=result

)

        conn.commit()
        return result

    except HTTPException:
        conn.rollback()
        raise

    except Exception as e:

        conn.rollback()

        log_error(
        message="Database transaction failed",
        user_id=user["id"],
        action="DATABASE_ERROR",
        entity="procurement_chain",
        extra={
            "exception": str(e)
        }
    )

        raise HTTPException(
        status_code=500,
        detail="Failed to build procurement chain."
    )

    finally:
        conn.close()

# ==============================
# VIEW CHAIN
# ==============================
@router.get("/commitments/{commitment_id}/chain")
def get_chain(
    commitment_id: int,
    user=Depends(require_user)
):
    conn, cursor = get_db()

    try:
        cursor.execute("""
    SELECT
        pc.id,
        pc.commitment_id,
        pc.source_id,
        pc.allocated_qty,
        pc.chain_position,

        ss.actor_name,
        ss.actor_type,
        ss.product,
        ss.location

    FROM procurement_chains pc

    JOIN supply_sources ss
    ON pc.source_id = ss.id

    WHERE pc.commitment_id = %s

    ORDER BY pc.chain_position ASC

""", (commitment_id,))

        chain = cursor.fetchall()

        risk = calculate_chain_risk(
    cursor,
    commitment_id
)

        return {
    "chain": chain,
    "risk": risk
}

    except HTTPException:
        raise

    except Exception:

        raise HTTPException(
        status_code=500,
        detail="Unable to retrieve procurement chain."
    )

    finally:
        conn.close()
# ==============================
# FEASIBILITY CHECK
# ==============================
@router.get("/chain/feasibility/{commitment_id}")
def check_feasibility(
    commitment_id: int,
    user=Depends(require_supplier)
):
    conn, cursor = get_db()

    try:
        return evaluate_commitment_feasibility(
            cursor,
            commitment_id
        )

    except HTTPException:
        raise

    except Exception:

        raise HTTPException(
        status_code=500,
        detail="Unable to retrieve procurement chain."
    )

    finally:
        conn.close()


# ==============================
# CHAIN RISK
# ==============================
@router.get("/chain/risk/{commitment_id}")
def chain_risk(
    commitment_id: int,
    user=Depends(require_user)
):
    conn, cursor = get_db()

    try:
        return calculate_chain_risk(
            cursor,
            commitment_id
        )

    except HTTPException:
        raise

    except Exception:

        raise HTTPException(
        status_code=500,
        detail="Unable to retrieve procurement chain."
    )

    finally:
        conn.close()