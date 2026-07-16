from fastapi import APIRouter, Depends
from app.core.dependencies import require_buyer
from app.core.db import get_db
from app.engines.support.reliability_engine import compute_supplier_reliability


router = APIRouter()


@router.get("/school/overview")
def school_overview(user=Depends(require_buyer)):

    conn, cursor = get_db()

    try:

        # Expected commitment quantity
        cursor.execute("""
            SELECT 
                COALESCE(SUM(promised_qty),0) AS expected
            FROM supplier_commitments
            WHERE school_id=%s
        """,
        (user["id"],))

        expected = cursor.fetchone()["expected"]



        # Count all physically received quantities
        # VERIFIED + PARTIAL
        cursor.execute("""
            SELECT 
                COALESCE(SUM(received_qty),0) AS received
            FROM deliveries d

            JOIN supplier_commitments c
            ON d.commitment_id=c.id

            WHERE c.school_id=%s

            AND d.verification_status IN
            (
                'VERIFIED',
                'PARTIAL'
            )

        """,
        (user["id"],))


        received = cursor.fetchone()["received"]



        cursor.execute("""
            SELECT DISTINCT supplier_id

            FROM supplier_commitments

            WHERE school_id=%s

        """,
        (user["id"],))


        suppliers = cursor.fetchall()


        scores=[]
        confidences=[]


        for supplier in suppliers:

            result = compute_supplier_reliability(
                cursor,
                supplier["supplier_id"]
            )

            scores.append(result["score"])
            confidences.append(
                result["confidence"]
            )



        average_score = (

            round(
                sum(scores)/len(scores),
                2
            )

            if scores
            else 0

        )


        return {

            "expected_total": expected,

            "received_total": received,

            "supplier_trust_avg": average_score,

            "supplier_trust_confidence":

                (
                "stable"
                if all(
                    c=="stable"
                    for c in confidences
                )

                else
                "low_sample_warning"
                )

        }


    finally:

        conn.close()