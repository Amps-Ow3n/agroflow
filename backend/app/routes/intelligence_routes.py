from fastapi import APIRouter, Depends

from app.core.db import get_db

from app.core.dependencies import (
    require_supplier,
    require_admin
)

from app.engines.intelligence.capacity_engine import (
    compute_supplier_capacity,
    compute_network_capacity
)

from app.engines.intelligence.delivery_reliability_engine import (
    compute_delivery_reliability,
    compute_supplier_ranking
)

router = APIRouter(
    tags=["Intelligence"]
)

# ==================================================
# SUPPLIER CAPACITY INTELLIGENCE
# ==================================================

@router.get("/supplier/capacity")
def supplier_capacity(
    user=Depends(require_supplier)
):

    conn, cursor = get_db()


    try:

        result = compute_supplier_capacity(
            cursor,
            user["id"]
        )


        return {

            "supplier_id":
                user["id"],

            "capacity":
                result

        }

    finally:

        conn.close()

# ==================================================
# SUPPLIER DELIVERY RELIABILITY
# ==================================================

@router.get("/supplier/reliability")
def supplier_reliability(
    user=Depends(require_supplier)
):

    conn, cursor = get_db()


    try:

        result = compute_delivery_reliability(
            cursor,
            user["id"]
        )


        return {

            "supplier_id":
                user["id"],

            "reliability":
                result

        }


    finally:

        conn.close()



# ==================================================
# SYSTEM CAPACITY NETWORK
# ==================================================

@router.get("/dashboard/system/capacity-network")
def system_capacity_network(
    user=Depends(require_admin)
):

    conn, cursor = get_db()


    try:

        result = compute_network_capacity(
            cursor
        )


        return {

            "network_capacity":
                result

        }


    finally:

        conn.close()



# ==================================================
# SYSTEM RELIABILITY RANKING
# ==================================================

@router.get("/dashboard/system/reliability-ranking")
def reliability_ranking(
    user=Depends(require_admin)
):

    conn, cursor = get_db()


    try:

        result = compute_supplier_ranking(
            cursor
        )


        return {

            "supplier_ranking":
                result

        }


    finally:

        conn.close()



# ==================================================
# SYSTEM RISK ALERTS
# ==================================================
@router.get("/dashboard/system/risk-alerts")
def system_risk_alerts(
    user=Depends(require_admin)
):

    conn, cursor = get_db()

    try:

        capacity = compute_network_capacity(
            cursor
        )

        reliability = compute_supplier_ranking(
            cursor
        )

        alerts = []

        # ----------------------------------
        # CAPACITY ALERTS
        # ----------------------------------

        for supplier in capacity:

            for product_capacity in supplier["capacity"]:

                if product_capacity["shortfall"] > 0:

                    alerts.append({

                        "type":
                            "CAPACITY",

                        "severity":
                            "HIGH",

                        "supplier_id":
                            supplier["supplier_id"],

                        "supplier_name":
                            supplier["supplier_name"],

                        "product":
                            product_capacity["product"],

                        "available":
                            product_capacity["available"],

                        "committed":
                            product_capacity["committed"],

                        "shortfall":
                            product_capacity["shortfall"],

                        "message":
                            "Supplier capacity exceeded"

                    })

        # ----------------------------------
        # RELIABILITY ALERTS
        # ----------------------------------

        for supplier in reliability:

            reliability_data = supplier["reliability"]

            score = reliability_data["score"]

            if score < 60:

                alerts.append({

                    "type":
                        "RELIABILITY",

                    "severity":
                        "HIGH",

                    "supplier_id":
                        supplier["supplier_id"],

                    "supplier_name":
                        supplier["supplier_name"],

                    "message":
                        "Supplier reliability risk detected",

                    "score":
                        score,

                    "confidence":
                        reliability_data["confidence"],

                    "delivery_count":
                        reliability_data["delivery_count"],

                    "confidence_message":
                        reliability_data[
                            "confidence_message"
                        ]

                })

        return {

            "alerts":
                alerts,

            "total":
                len(alerts)

        }

    finally:

        conn.close()