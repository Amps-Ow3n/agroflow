from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import sqlite3
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from datetime import date, datetime, timedelta
from pathlib import Path
import os
from fastapi import HTTPException
from dotenv import load_dotenv
from collections import defaultdict
from fastapi import Query
import psycopg2
import os
from psycopg2.extras import RealDictCursor
from mappers.supply_mapper import map_to_supply
from mappers.commitment_mapper import map_to_commitment
from mappers.delivery_mapper import map_to_delivery
from mappers.intelligence_mapper import map_to_intelligence
# ======================================================
# APP CONFIG
# ======================================================
app = FastAPI(title="AgroFlow MVP - Farmer Supply Registry")

origins = [
    "http://localhost:3000", 
    "http://127.0.0.1:3000",
    "*",  

]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

SECRET_KEY = "amp5-ow3n"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

load_dotenv()
ADMIN_SECRET_CODE = os.getenv("ADMIN_SECRET_CODE")  

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "agroflow.db"

def get_db():
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        raise Exception("DATABASE_URL not set")

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    return conn, cursor
# ======================================================
# DATABASE INITIALIZATION
# ======================================================
def init_db():
    conn, cursor = get_db()

    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT CHECK(role IN ('farmer','buyer','admin')) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # SUPPLY
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farmer_supply (
        id SERIAL PRIMARY KEY,
        farmer_id INTEGER REFERENCES users(id),
        crop TEXT,
        qty_min INTEGER,
        qty_max INTEGER,
        zone TEXT,
        available_from DATE,
        available_to DATE,
        last_updated TIMESTAMP
    )
    """)

    # COMMITMENTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS commitments (
        id SERIAL PRIMARY KEY,
        farmer_id INTEGER REFERENCES users(id),
        crop TEXT,
        promised_qty INTEGER,
        zone TEXT,
        delivery_start DATE,
        delivery_end DATE,
        status TEXT DEFAULT 'PENDING',
        created_at TIMESTAMP,
        last_updated TIMESTAMP
    )
    """)

    # DELIVERIES
    cursor.execute("""
CREATE TABLE IF NOT EXISTS deliveries (

    id SERIAL PRIMARY KEY,

    commitment_id INTEGER REFERENCES commitments(id),

    delivered_qty INTEGER,

    week_start DATE,
    week_end DATE,

    status TEXT,

    verification_status TEXT DEFAULT 'PENDING',

    confidence_score REAL DEFAULT 0,

    verification_notes TEXT,

    verified_by INTEGER REFERENCES users(id),

    verified_at TIMESTAMP,

    weekly_promised_qty REAL,

    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
    
    # DECISION LOGS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS decision_logs (
        id SERIAL PRIMARY KEY,
        farmer_id INTEGER,
        crop TEXT,
        week TEXT,
        over_amount INTEGER,
        explanation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # TRUST
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farmer_trust (
        farmer_id INTEGER PRIMARY KEY,
        score INTEGER DEFAULT 100,
        total_deliveries INTEGER DEFAULT 0
    )
    """)

    # RISK CACHE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farmer_risk_cache (
        farmer_id INTEGER PRIMARY KEY,
        risk_score REAL,
        risk_level TEXT,
        explanation TEXT,
        last_updated TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()
init_db()

# ======================================================
# Pydantic Models
# ======================================================
class SupplyCreate(BaseModel):
    crop: str
    qty_min: int = Field(..., gt=0)
    qty_max: int = Field(..., gt=0)
    zone: str
    available_from: date
    available_to: date

class SupplyUpdate(BaseModel):
    qty_min: Optional[int] = Field(None, gt=0)
    qty_max: Optional[int] = Field(None, gt=0)
    available_from: Optional[date]
    available_to: Optional[date]

class SupplyOut(BaseModel):
    id: int
    farmer_id: int
    crop: str
    qty_min: int
    qty_max: int
    zone: str
    available_from: date
    available_to: date
    last_updated: datetime

class CommitmentCreate(BaseModel):
    crop: str
    promised_qty: int = Field(..., gt=0)
    zone: str
    delivery_start: date
    delivery_end: date

class CommitmentUpdate(BaseModel):
    promised_qty: Optional[int] = Field(None, gt=0)
    delivery_start: Optional[date]
    delivery_end: Optional[date]

class CommitmentOut(BaseModel):
    id: int
    farmer_id: int
    crop: str
    promised_qty: int
    zone: str
    delivery_start: date
    delivery_end: date
    status: str
    created_at: datetime
    last_updated: datetime

class DeliveryCreate(BaseModel):
    commitment_id: int
    delivered_qty: int
    week_start: date
    week_end: date

class DeliveryUpdate(BaseModel):
    delivered_qty: int
    week_start: date
    week_end: date

class DeliveryVerification(BaseModel):
    verification_status: str
    verification_notes: Optional[str] = None
# ======================================================
# HELPER FUNCTIONS
# ======================================================
def normalize(text: str) -> str:
    return text.strip().lower()

def require_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

def get_current_user(token: str = Depends(oauth2_scheme)):
    return require_user(token)

def require_farmer(user=Depends(require_user)):
    if user["role"] != "farmer":
        raise HTTPException(status_code=403, detail="Not a farmer")
    return user

def require_admin(user=Depends(require_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return user

def require_buyer(user=Depends(require_user)):
    if user["role"] != "buyer":
        raise HTTPException(status_code=403, detail="Buyers only")
    return user

def get_weeks_between(start_date, end_date):
    """
    Returns a list of ISO weeks (YYYY-Www) between start_date and end_date inclusive.
    """
    start_date = to_date(start_date)
    end_date = to_date(end_date)

    weeks = set()
    current = start_date
    while current <= end_date:
        year, week, _ = current.isocalendar()
        weeks.add(f"{year}-W{week:02d}")  # leading zero for ISO week
        current += timedelta(days=1)

    return sorted(list(weeks))

# ----------------------------
# Aggregate farmer supply capacity (evenly across ISO weeks)
# ----------------------------
def calculate_supply_capacity(supplies):
    """
    Returns a dict {(crop, ISO_week): weekly_capacity}
    """
    capacity = {}

    for s in supplies:
        crop = s["crop"]
        total_qty = s["qty_max"]
        start_date = to_date(s["available_from"])
        end_date = to_date(s["available_to"])

        weeks = get_weeks_between(start_date, end_date)
        if not weeks:
            continue

        weekly_capacity = total_qty / len(weeks)

        for week in weeks:
            key = (crop, week)
            capacity[key] = capacity.get(key, 0) + weekly_capacity

    return capacity

# ----------------------------
# Aggregate commitments (evenly across ISO weeks)
# ----------------------------
def calculate_commitment_load(commitments):
    """
    Returns a dict {(crop, ISO_week): weekly_committed_qty}
    """
    load = {}

    for c in commitments:
        crop = c["crop"]
        total_qty = c["promised_qty"]
        start_date = to_date(c["delivery_start"])
        end_date = to_date(c["delivery_end"])

        weeks = get_weeks_between(start_date, end_date)
        if not weeks:
            continue

        weekly_qty = total_qty / len(weeks)

        for week in weeks:
            key = (crop, week)
            load[key] = load.get(key, 0) + weekly_qty

    return load

# ----------------------------
# Feasibility check per farmer
# ----------------------------
def check_feasibility(farmer_id: int):
    """
    Evaluates a farmer's commitments vs supply and returns feasibility summary.
    Aggregates commitments per crop/week and compares to weekly capacity.
    """
    conn, cursor = get_db()

    try:
        # Fetch commitments
        cursor.execute("""
            SELECT crop, promised_qty, delivery_start, delivery_end
            FROM commitments
            WHERE farmer_id = %s
        """, (farmer_id,))
        commitments = [dict(row) for row in cursor.fetchall()]

        # Fetch supply
        cursor.execute("""
            SELECT crop, qty_max, available_from, available_to
            FROM farmer_supply
            WHERE farmer_id = %s
        """, (farmer_id,))
        supplies = [dict(row) for row in cursor.fetchall()]

        if not supplies:
            return {
                "farmer_id": farmer_id,
                "feasible_commitments": [],
                "over_commitments": [],
                "confidence_score": 0,
                "calculation_details": {}
            }

        # Step 1: aggregate
        load = calculate_commitment_load(commitments)
        capacity = calculate_supply_capacity(supplies)

        # Step 2: compare
        feasible = []
        overcommitted = []
        utilization_list = []
        calculation_details = {}

        for key, promised in load.items():
            crop, week = key
            available = capacity.get(key, 0)
            utilization = promised / available if available > 0 else 0
            over_ratio = max(0, (promised - available) / available) if available > 0 else 0
            utilization_list.append(utilization)

            calculation_details[str(key)] = {
    "promised": round(promised, 2),
    "capacity": round(available, 2),
    "utilization": round(utilization, 2),
    "message": (
    f"Over capacity by {round(over_ratio * 100, 1)}% — requires reduction or rescheduling"
    if over_ratio > 0
    else "Within capacity limits — operationally feasible"
)
}

            if promised > available:
                overcommitted.append({
    "crop": crop,
    "week": week,
    "promised": round(promised, 2),
    "capacity": round(available, 2),
    "over_by": round(promised - available, 2),
    "over_ratio": round(over_ratio, 2),
    "risk_signal": "LOW" if promised <= available else "HIGH",
    "message": (
    f"CRITICAL: Exceeds capacity by {round(over_ratio * 100, 1)}% — high default risk"
)
})
            else:
                feasible.append({
    "crop": crop,
    "week": week,
    "promised": round(promised, 2),
    "capacity": round(available, 2),
    "over_ratio": round(over_ratio, 2),
    "risk_signal": "LOW" if promised <= available else "HIGH",
    "message": "Within capacity"
})
        # Step 3: confidence
        if not utilization_list:
            confidence = 0
        else:
           avg_util = sum(utilization_list) / len(utilization_list)

           if avg_util <= 0.8:
              confidence = 85
           elif avg_util <= 1.0:
                confidence = 65
           else:
               confidence = max(20, 100 - (avg_util * 60))
        return {
            "farmer_id": farmer_id,
            "feasible_commitments": feasible,
            "over_commitments": overcommitted,
            "confidence_score": round(confidence, 2),
            "calculation_details": calculation_details
        }

    finally:
        conn.close() 

# -----------------------------------
# Compute delivery status
# -----------------------------------
def compute_delivery_status(delivered, promised):
    """
    Compute delivery status based on TOTAL commitment fulfillment.
    This ensures consistency across:
    - Delivery table
    - Commitment table
    - Farmer dashboard
    - Admin dashboard
    """
    delivered = delivered or 0
    promised = promised or 0

    if promised <= 0:
        return "COMPLETED" if delivered > 0 else "FAILED"

    fulfillment_ratio = delivered / promised

    if fulfillment_ratio >= 1:
        return "COMPLETED"
    elif fulfillment_ratio >= 0.5:
        return "PARTIAL"
    elif fulfillment_ratio > 0:
        return "LOW"
    else:
        return "FAILED"

def compute_delivery_status_with_reason(delivered, promised):
    """
    Extends compute_delivery_status with human-readable explanation.
    DOES NOT break existing logic.
    """

    status = compute_delivery_status(delivered, promised)

    delivered = delivered or 0
    promised = promised or 0

    if promised <= 0:
        if delivered > 0:
            reason = f"Delivered {delivered} units without a formal commitment."
        else:
            reason = "No commitment and no delivery recorded."
        return status, reason

    shortfall = max(promised - delivered, 0)
    ratio = (delivered / promised) if promised > 0 else 0

    if status == "COMPLETED":
        reason = f"Delivered {delivered}/{promised} units (100% fulfillment)."

    elif status == "PARTIAL":
        reason = f"Delivered {delivered}/{promised} units ({round(ratio*100)}%). Shortfall: {shortfall} units."

    elif status == "LOW":
        reason = f"Low fulfillment: {delivered}/{promised} units ({round(ratio*100)}%). Major shortfall: {shortfall} units."

    elif status == "FAILED":
        reason = f"No delivery made. Expected {promised} units."

    else:
        reason = "Unknown delivery state."

    return status, reason
# -----------------------------------
# Aggregate total supply per crop + zone
# -----------------------------------
def aggregate_supply(db, farmer_id):
    """
    Compute total supply per crop and zone for a farmer.
    """
    rows = db.execute("""
        SELECT crop, zone, SUM(qty_max) as total_capacity
        FROM farmer_supply
        WHERE farmer_id = %s
        GROUP BY crop, zone
    """, (farmer_id,)).fetchall()

    supply = {}
    for row in rows:
        crop = row["crop"]
        zone = row["zone"]
        total_capacity = row["total_capacity"]
        if crop not in supply:
            supply[crop] = {}
        supply[crop][zone] = total_capacity
    return supply
# ----------------------------
# Aggregate total commitments per crop + zone
# ----------------------------
def aggregate_commitments(db, farmer_id):
    """
    Compute total commitments per crop and zone for a farmer.
    """
    rows = db.execute("""
        SELECT crop, zone, SUM(promised_qty) as total_committed
        FROM commitments
        WHERE farmer_id = %s
        GROUP BY crop, zone
    """, (farmer_id,)).fetchall()

    commitments = {}
    for row in rows:
        crop = row["crop"]
        zone = row["zone"]
        total_committed = row["total_committed"]
        if crop not in commitments:
            commitments[crop] = {}
        commitments[crop][zone] = total_committed
    return commitments
# -----------------------------------
# Delivery completion percentage
# -----------------------------------
def compute_delivery_metrics(db, farmer_id):
    rows = db.execute("""
        SELECT d.crop, d.zone, SUM(d.delivered_qty) as total_delivered
        FROM deliveries d
        JOIN commitments c ON d.commitment_id = c.id
        WHERE c.farmer_id = %s
        GROUP BY d.crop, d.zone
    """, (farmer_id,)).fetchall()

    result = []

    for r in rows:
        crop = normalize(r["crop"])
        zone = normalize(r["zone"])

        result.append({
            "crop": crop,
            "zone": zone,
            "total_delivered": r["total_delivered"]
        })

    return result
# -----------------------------------
# Missed deliveries count
# -----------------------------------
def count_missed(deliveries):
    return sum(
        1 for d in deliveries 
        if d["status"] in ["FAILED", "MISSED"]
    )
# -----------------------------------
# Farmer Reliability Score Engine
# -----------------------------------
def update_farmer_trust(
    farmer_id,
    verification_status,
    confidence_score=1.0
):

    conn, cursor = get_db()

    try:

        cursor.execute("""
            SELECT score, total_deliveries
            FROM farmer_trust
            WHERE farmer_id = %s
        """, (farmer_id,))

        row = cursor.fetchone()

        # -----------------------------
        # Create initial trust profile
        # -----------------------------
        if not row:

            score = 80
            total = 0

            cursor.execute("""
                INSERT INTO farmer_trust (
                    farmer_id,
                    score,
                    total_deliveries
                )
                VALUES (%s, %s, %s)
            """, (
                farmer_id,
                score,
                total
            ))

        else:
            score = row["score"]
            total = row["total_deliveries"]

        # -----------------------------
        # TRUST UPDATE LOGIC
        # -----------------------------
        if verification_status == "VERIFIED":

            score += 1.5 * confidence_score

        elif verification_status == "PARTIAL":

            score -= 1.5 * (1 - confidence_score)

        elif verification_status == "REJECTED":

            score -= 4

        # Clamp score
        score = max(0, min(100, score))

        total += 1

        # -----------------------------
        # SAVE
        # -----------------------------
        cursor.execute("""
            UPDATE farmer_trust
            SET
                score = %s,
                total_deliveries = %s
            WHERE farmer_id = %s
        """, (
            score,
            total,
            farmer_id
        ))

        conn.commit()

    except Exception as e:

        print("Trust update error:", e)

    finally:
        conn.close()
# ==================================================
# VERIFICATION CONFIDENCE ENGINE
# ==================================================
def compute_confidence_score(verification_status):

    if verification_status == "VERIFIED":
        return 1.0

    elif verification_status == "PARTIAL":
        return 0.5

    elif verification_status == "REJECTED":
        return 0.0

    return 0.0

# ==============================
# FARMER DASHBOARD ENGINE
# ==============================
def generate_farmer_dashboard(conn, farmer_id):

    try:

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # =====================================================
        # 1. SUPPLY SUMMARY
        # =====================================================
        cursor.execute("""
            SELECT
                crop,
                COALESCE(zone, '-') as zone,
                SUM(qty_max) as total_capacity
            FROM farmer_supply
            WHERE farmer_id = %s
            GROUP BY crop, zone
            ORDER BY crop
        """, (farmer_id,))

        supply_summary = cursor.fetchall()

        supply_map = {
            (s["crop"], s["zone"]): s["total_capacity"]
            for s in supply_summary
        }

        # =====================================================
        # 2. COMMITMENT SUMMARY
        # =====================================================
        cursor.execute("""
            SELECT
                id,
                crop,
                COALESCE(zone, '-') as zone,
                promised_qty,
                delivery_start,
                delivery_end,
                status
            FROM commitments
            WHERE farmer_id = %s
            ORDER BY id DESC
        """, (farmer_id,))

        commitment_rows = cursor.fetchall()

        commitment_summary = []

        total_promised = 0

        for r in commitment_rows:

            crop = r["crop"]
            zone = r["zone"]

            promised = r["promised_qty"] or 0
            capacity = supply_map.get((crop, zone), 0)

            utilization = (
                (promised / capacity) * 100
                if capacity > 0 else 0
            )

            total_promised += promised

            commitment_summary.append({
                "commitment_id": r["id"],
                "crop": crop,
                "zone": zone,
                "promised_qty": promised,
                "capacity": capacity,
                "utilization_percent": round(utilization, 2),
                "delivery_start": r["delivery_start"],
                "delivery_end": r["delivery_end"],
                "status": r["status"]
            })

        # =====================================================
        # 3. DELIVERY PERFORMANCE
        # =====================================================
        cursor.execute("""
            SELECT
                c.id as commitment_id,
                c.crop,
                COALESCE(c.zone, '-') as zone,
                c.promised_qty,

                COALESCE(SUM(d.delivered_qty), 0) as reported_qty,

                COALESCE(SUM(
                    CASE
                        WHEN d.verification_status IN ('VERIFIED', 'PARTIAL')
                        THEN d.delivered_qty
                        ELSE 0
                    END
                ), 0) as verified_qty,

                COALESCE(MAX(d.verification_status), 'PENDING')
                as verification_status

            FROM commitments c

            LEFT JOIN deliveries d
            ON d.commitment_id = c.id

            WHERE c.farmer_id = %s

            GROUP BY
                c.id,
                c.crop,
                c.zone,
                c.promised_qty

            ORDER BY c.id DESC
        """, (farmer_id,))

        delivery_rows = cursor.fetchall()

        delivery_history = []

        total_reported = 0
        total_verified = 0
        total_missed = 0

        for r in delivery_rows:

            promised = r["promised_qty"] or 0

            reported_qty = min(
                r["reported_qty"] or 0,
                promised
            )

            verified_qty = min(
                r["verified_qty"] or 0,
                promised
            )

            total_reported += reported_qty
            total_verified += verified_qty

            missed_qty = max(promised - verified_qty, 0)

            total_missed += missed_qty

            reported_status, reported_reason = \
                compute_delivery_status_with_reason(
                    reported_qty,
                    promised
                )

            verified_status, verified_reason = \
                compute_delivery_status_with_reason(
                    verified_qty,
                    promised
                )

            delivery_history.append({

                "commitment_id": r["commitment_id"],

                "crop": r["crop"],

                "zone": r["zone"],

                "promised_qty": promised,

                "verification_status": r["verification_status"],

                # --------------------------------
                # REPORTED
                # --------------------------------
                "reported_delivery": {
                    "qty": reported_qty,
                    "status": reported_status,
                    "reason": reported_reason
                },

                # --------------------------------
                # VERIFIED
                # --------------------------------
                "verified_delivery": {
                    "qty": verified_qty,
                    "status": verified_status,
                    "reason": verified_reason
                },

                # --------------------------------
                # GAP
                # --------------------------------
                "verification_gap": max(
                    reported_qty - verified_qty,
                    0
                )
            })

        # =====================================================
        # 4. TRUST SCORE
        # =====================================================
        cursor.execute("""
            SELECT score
            FROM farmer_trust
            WHERE farmer_id = %s
        """, (farmer_id,))

        trust_row = cursor.fetchone()

        trust_score = (
            trust_row["score"]
            if trust_row else 100
        )

        if trust_score >= 80:
            trust_label = "RELIABLE"

        elif trust_score >= 50:
            trust_label = "MODERATE"

        else:
            trust_label = "RISKY"

        # =====================================================
        # 5. PERFORMANCE METRICS
        # =====================================================
        reported_rate = (
            (total_reported / total_promised) * 100
            if total_promised > 0 else 0
        )

        verified_rate = (
            (total_verified / total_promised) * 100
            if total_promised > 0 else 0
        )

        # =====================================================
        # 6. RISK ENGINE
        # =====================================================
        risk_summary = compute_farmer_risk_v2(
            cursor,
            farmer_id
        )

        # =====================================================
        # 7. RISK ALERTS
        # =====================================================
        risk_alerts = []

        for explanation in risk_summary.get("explanation", []):

            risk_alerts.append({
                "message": explanation,
                "risk_level": risk_summary["risk_level"]
            })

        # =====================================================
        # FINAL RESPONSE
        # =====================================================
        return {

            # --------------------------------
            # SUPPLY
            # --------------------------------
            "supply_summary": supply_summary,

            # --------------------------------
            # COMMITMENTS
            # --------------------------------
            "commitment_summary": commitment_summary,

            # --------------------------------
            # DELIVERIES
            # --------------------------------
            "delivery_history": delivery_history,

            # --------------------------------
            # REPORTED PERFORMANCE
            # --------------------------------
            "reported_performance": {
                "completion_rate": round(reported_rate, 2),
                "total_reported_qty": total_reported
            },

            # --------------------------------
            # VERIFIED PERFORMANCE
            # --------------------------------
            "verified_performance": {
                "completion_rate": round(verified_rate, 2),
                "total_verified_qty": total_verified,
                "missed_qty": total_missed
            },

            # --------------------------------
            # TRUST
            # --------------------------------
            "trust_score": {
                "score": trust_score,
                "label": trust_label
            },

            # --------------------------------
            # RISK
            # --------------------------------
            "risk_summary": risk_summary,

            "risk_alerts": risk_alerts
        }

    except Exception as e:

        print("Error generating farmer dashboard:", e)

        return {
            "error": str(e)
        }

# ==============================
# ADMIN DASHBOARD ENGINE V2
# ==============================
def generate_admin_dashboard(conn):

    try:

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # =====================================================
        # 1. PLATFORM TOTALS
        # =====================================================
        cursor.execute("""
            SELECT
                COUNT(*) as total_commitments,
                COALESCE(SUM(promised_qty), 0) as total_promised
            FROM commitments
        """)

        totals = cursor.fetchone()

        total_commitments = totals["total_commitments"] or 0
        total_promised = totals["total_promised"] or 0

        # =====================================================
        # 2. VERIFIED DELIVERY TOTALS
        # =====================================================
        cursor.execute("""
            SELECT

                COALESCE(SUM(d.delivered_qty), 0) as total_reported,

                COALESCE(SUM(
                    CASE
                        WHEN d.verification_status IN ('VERIFIED', 'PARTIAL')
                        THEN d.delivered_qty
                        ELSE 0
                    END
                ), 0) as total_verified,

                COUNT(*) FILTER (
                    WHERE d.verification_status = 'REJECTED'
                ) as rejected_count,

                COUNT(*) FILTER (
                    WHERE d.verification_status = 'VERIFIED'
                ) as verified_count

            FROM deliveries d
        """)

        delivery_totals = cursor.fetchone()

        total_reported = delivery_totals["total_reported"] or 0
        total_verified = delivery_totals["total_verified"] or 0

        rejected_count = delivery_totals["rejected_count"] or 0
        verified_count = delivery_totals["verified_count"] or 0

        # =====================================================
        # 3. PLATFORM VERIFICATION RATE
        # =====================================================
        verification_rate = 0

        total_verifications = verified_count + rejected_count

        if total_verifications > 0:
            verification_rate = (
                verified_count / total_verifications
            ) * 100

        # =====================================================
        # 4. PLATFORM COMPLETION RATE
        # =====================================================
        completion_rate = 0

        if total_promised > 0:
            completion_rate = (
                total_verified / total_promised
            ) * 100

        # =====================================================
        # 5. FARMER RISK OVERVIEW
        # =====================================================
        cursor.execute("""
            SELECT
                frc.farmer_id,
                u.name,
                frc.risk_score,
                frc.risk_level,
                frc.explanation,
                ft.score as trust_score

            FROM farmer_risk_cache frc

            LEFT JOIN users u
            ON frc.farmer_id = u.id

            LEFT JOIN farmer_trust ft
            ON frc.farmer_id = ft.farmer_id

            ORDER BY frc.risk_score DESC
        """)

        risk_rows = cursor.fetchall()

        farmers = []

        total_risk_score = 0

        for r in risk_rows:

            risk_score = r["risk_score"] or 0
            trust_score = r["trust_score"] or 100

            total_risk_score += risk_score

            # -----------------------------
            # TRUST LABEL
            # -----------------------------
            if trust_score >= 80:
                trust_label = "HIGH"

            elif trust_score >= 50:
                trust_label = "MEDIUM"

            else:
                trust_label = "LOW"

            farmers.append({

                "farmer_id": r["farmer_id"],

                "farmer_name": r["name"],

                "risk_score": round(risk_score, 2),

                "risk_level": r["risk_level"],

                "trust_score": trust_score,

                "trust_label": trust_label,

                "risk_explanation": r["explanation"]
            })

        # =====================================================
        # 6. SYSTEM RISK OVERVIEW
        # =====================================================
        avg_platform_risk = 0

        if len(farmers) > 0:
            avg_platform_risk = (
                total_risk_score / len(farmers)
            )

        high_risk_farmers = [
            f for f in farmers
            if f["risk_level"] == "HIGH"
        ]

        # =====================================================
        # 7. VERIFICATION GAPS
        # =====================================================
        cursor.execute("""
            SELECT

                c.id as commitment_id,
                c.crop,
                c.zone,

                u.name as farmer_name,

                c.promised_qty,

                COALESCE(SUM(d.delivered_qty), 0) as reported_qty,

                COALESCE(SUM(
                    CASE
                        WHEN d.verification_status
                        IN ('VERIFIED', 'PARTIAL')
                        THEN d.delivered_qty
                        ELSE 0
                    END
                ), 0) as verified_qty

            FROM commitments c

            LEFT JOIN deliveries d
            ON c.id = d.commitment_id

            LEFT JOIN users u
            ON c.farmer_id = u.id

            GROUP BY
                c.id,
                c.crop,
                c.zone,
                u.name,
                c.promised_qty

            ORDER BY c.id DESC
        """)

        gap_rows = cursor.fetchall()

        verification_gaps = []

        for r in gap_rows:

            reported = r["reported_qty"] or 0
            verified = r["verified_qty"] or 0

            gap = max(reported - verified, 0)

            if gap > 0:

                verification_gaps.append({

                    "commitment_id": r["commitment_id"],

                    "farmer_name": r["farmer_name"],

                    "crop": r["crop"],

                    "zone": r["zone"] or "-",

                    "reported_qty": reported,

                    "verified_qty": verified,

                    "gap": gap,

                    "severity": round(
                        min(100, (gap / max(reported, 1)) * 100),
                        2
                    )
                })

        # =====================================================
        # 8. UNRELIABLE ACTORS
        # =====================================================
        unreliable_actors = []

        for f in farmers:

            reasons = []

            if f["risk_score"] >= 70:
                reasons.append("High operational risk")

            if f["trust_score"] < 50:
                reasons.append("Low trust score")

            if f["risk_level"] == "HIGH":
                reasons.append("Repeated delivery inconsistencies")

            if reasons:

                unreliable_actors.append({

                    "farmer_id": f["farmer_id"],

                    "farmer_name": f["farmer_name"],

                    "risk_score": f["risk_score"],

                    "trust_score": f["trust_score"],

                    "reasons": reasons
                })

        # =====================================================
        # 9. FINAL RESPONSE
        # =====================================================
        return {

            # -------------------------------------------------
            # SYSTEM OVERVIEW
            # -------------------------------------------------
            "system_risk_overview": {

                "total_commitments": total_commitments,

                "total_promised_qty": total_promised,

                "total_reported_qty": total_reported,

                "total_verified_qty": total_verified,

                "platform_completion_rate":
                    round(completion_rate, 2),

                "verification_rate":
                    round(verification_rate, 2),

                "average_platform_risk":
                    round(avg_platform_risk, 2),

                "high_risk_farmers":
                    len(high_risk_farmers)
            },

            # -------------------------------------------------
            # FARMER RISK TABLE
            # -------------------------------------------------
            "farmer_risk_overview": farmers,

            # -------------------------------------------------
            # VERIFICATION GAPS
            # -------------------------------------------------
            "verification_gaps": verification_gaps,

            # -------------------------------------------------
            # UNRELIABLE ACTORS
            # -------------------------------------------------
            "unreliable_actors": unreliable_actors
        }

    except Exception as e:

        print("Error generating admin dashboard:", e)

        return {
            "error": str(e)
        }
def hash_password(password: str):
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=400,
            detail="Password too long (max 72 characters)"
        )
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def log_decision(farmer_id, category, message):
    conn, cursor = get_db()
    cursor.execute("""
        INSERT INTO decision_logs
        (farmer_id, crop, week, over_amount, explanation)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        farmer_id,
        category,
        "N/A",  
        0,
        message
    ))
    conn.commit()
    conn.close()

VALID_CROPS = {"maize", "beans", "rice", "cassava", "sorghum"}

def validate_crop(crop):
    crop = crop.lower().strip()
    if crop not in VALID_CROPS:
        raise HTTPException(status_code=400, detail="Unsupported crop")
    return crop

def validate_quantity(qty):
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

def validate_date_range(start, end):
    if start > end:
        raise HTTPException(status_code=400, detail="Invalid date range")

def validate_zone(zone):
    if not zone or len(zone) < 2:
        raise HTTPException(status_code=400, detail="Invalid zone")
    
def to_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)

def to_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)

def get_farmer_history(cursor, farmer_id):
    cursor.execute("""
        SELECT d.delivered_qty, d.status, d.week_start, d.week_end,
               c.promised_qty
        FROM deliveries d
        JOIN commitments c ON d.commitment_id = c.id
        WHERE c.farmer_id = %s
    """, (farmer_id,))
    
    return [dict(r) for r in cursor.fetchall()]

# -----------------------------
# Compute consistency
# -----------------------------
def compute_consistency(deliveries):
    if not deliveries:
        return 0
    
    completed = sum(1 for d in deliveries if d["status"] == "COMPLETED")
    return completed / len(deliveries)

# -----------------------------
# Compute overcommitment frequency
# -----------------------------
def compute_overcommitment(cursor, farmer_id):
    # Total promised
    cursor.execute("""
        SELECT SUM(promised_qty) as total_promised
        FROM commitments
        WHERE farmer_id = %s
    """, (farmer_id,))
    promised = cursor.fetchone()["total_promised"] or 0

    # Total supply capacity
    cursor.execute("""
        SELECT SUM(qty_max) as total_supply
        FROM farmer_supply
        WHERE farmer_id = %s
    """, (farmer_id,))
    supply = cursor.fetchone()["total_supply"] or 0

    if supply <= 0:
        return 0

    overcommitment_ratio = max(0, (promised - supply) / supply) if supply > 0 else 0
    overcommitment_ratio = min(overcommitment_ratio, 1.0)  # <-- NEW cap
    return round(overcommitment_ratio, 2)
# -----------------------------
# Compute trend (last vs previous)
# -----------------------------
def compute_trend(deliveries):
    if len(deliveries) < 4:
        return 0.5  # neutral
    
    deliveries = sorted(deliveries, key=lambda x: x["week_start"])
    
    mid = len(deliveries) // 2
    first_half = deliveries[:mid]
    second_half = deliveries[mid:]
    
    def avg_completion(ds):
        return sum(1 for d in ds if d["status"] == "COMPLETED") / len(ds)
    
    return avg_completion(second_half) - avg_completion(first_half)

def build_risk_explanation(overcommitment_risk,
                           verification_risk,
                           mismatch_risk,
                           inconsistency_risk,
                           risk_score):

    explanation = []

    # -----------------------------
    # OVERCOMMITMENT
    # -----------------------------
    if overcommitment_risk > 0.2:
        explanation.append(
            "Farmer has committed more supply than available capacity."
        )
    elif overcommitment_risk > 0:
        explanation.append(
            "Mild overcommitment detected between supply and commitments."
        )

    # -----------------------------
    # VERIFICATION
    # -----------------------------
    if verification_risk > 0.3:
        explanation.append(
            "High rejection rate from buyer verification."
        )
    elif verification_risk > 0:
        explanation.append(
            "Some deliveries have been rejected by buyer."
        )

    # -----------------------------
    # MISMATCH
    # -----------------------------
    if mismatch_risk > 0.3:
        explanation.append(
            "Large gap between reported and verified deliveries."
        )
    elif mismatch_risk > 0:
        explanation.append(
            "Minor mismatch between reported and verified quantities."
        )

    # -----------------------------
    # INCONSISTENCY
    # -----------------------------
    if inconsistency_risk > 0.3:
        explanation.append(
            "Delivery quantities are highly inconsistent over time."
        )
    elif inconsistency_risk > 0:
        explanation.append(
            "Some variation in delivery consistency detected."
        )

    # -----------------------------
    # GLOBAL SUMMARY
    # -----------------------------
    if not explanation:
        if risk_score < 30:
            explanation.append("Farmer shows stable and reliable performance.")
        elif risk_score < 70:
            explanation.append("Moderate risk detected in farmer performance.")
        else:
            explanation.append("High risk farmer with multiple performance issues.")

    return explanation

def compute_farmer_risk_v2(cursor, farmer_id):

    # -----------------------------
    # 1. OVERCOMMITMENT RISK
    # -----------------------------
    cursor.execute("""
        SELECT
            COALESCE(SUM(c.promised_qty),0) as promised,
            COALESCE(SUM(s.qty_max),0) as capacity
        FROM commitments c
        JOIN farmer_supply s
        ON c.farmer_id = s.farmer_id
        AND c.crop = s.crop
        AND c.zone = s.zone
        WHERE c.farmer_id = %s
    """, (farmer_id,))

    row = cursor.fetchone()
    promised = row["promised"]
    capacity = row["capacity"]

    overcommitment_risk = (
        (promised - capacity) / capacity
        if capacity > 0 and promised > capacity else 0
    )

    # -----------------------------
    # 2. VERIFICATION RISK
    # -----------------------------
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN verification_status = 'VERIFIED' THEN 1 ELSE 0 END) as verified,
            SUM(CASE WHEN verification_status = 'REJECTED' THEN 1 ELSE 0 END) as rejected
        FROM deliveries d
        JOIN commitments c ON d.commitment_id = c.id
        WHERE c.farmer_id = %s
    """, (farmer_id,))

    v = cursor.fetchone()
    total = v["total"] or 0
    verified = v["verified"] or 0
    rejected = v["rejected"] or 0

    verification_rate = (verified / total) if total > 0 else 0
    rejection_rate = (rejected / total) if total > 0 else 0
    verification_risk = rejection_rate
    # -----------------------------
    # 3. MISMATCH RISK (reported vs verified)
    # -----------------------------
    cursor.execute("""
        SELECT
            COALESCE(SUM(d.delivered_qty),0) as reported,
            COALESCE(SUM(
                CASE
                    WHEN d.verification_status = 'VERIFIED'
                    THEN d.delivered_qty
                    ELSE 0
                END
            ),0) as verified_qty
        FROM deliveries d
        JOIN commitments c ON d.commitment_id = c.id
        WHERE c.farmer_id = %s
    """, (farmer_id,))

    m = cursor.fetchone()

    reported = m["reported"] or 0
    verified_qty = m["verified_qty"] or 0

    mismatch_risk = (
        (reported - verified_qty) / reported
        if reported > 0 else 0
    )

    # -----------------------------
    # 4. DELIVERY INCONSISTENCY
    # -----------------------------
    cursor.execute("""
        SELECT delivered_qty
        FROM deliveries d
        JOIN commitments c ON d.commitment_id = c.id
        WHERE c.farmer_id = %s
    """, (farmer_id,))

    rows = cursor.fetchall()
    values = [r["delivered_qty"] for r in rows if r["delivered_qty"] is not None]

    if len(values) > 1:
        avg = sum(values) / len(values)
        variance = sum((x - avg) ** 2 for x in values) / len(values)
        inconsistency_risk = min(1, variance / (avg ** 2 + 1))
    else:
        inconsistency_risk = 0

    # -----------------------------
    # FINAL RISK SCORE (0 - 100)
    # -----------------------------
    risk_score = (
        overcommitment_risk * 35 +
        verification_risk * 25 +
        mismatch_risk * 25 +
        inconsistency_risk * 15
    ) * 100

    risk_score = max(0, min(100, risk_score))

    if risk_score < 30:
        risk_level = "LOW"
    elif risk_score < 70:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"
    
    explanation = build_risk_explanation(
    overcommitment_risk,
    verification_risk,
    mismatch_risk,
    inconsistency_risk,
    risk_score
)
    cursor.execute("""
INSERT INTO farmer_risk_cache (
    farmer_id,
    risk_score,
    risk_level,
    explanation,
    last_updated
)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (farmer_id)
DO UPDATE SET
    risk_score = EXCLUDED.risk_score,
    risk_level = EXCLUDED.risk_level,
    explanation = EXCLUDED.explanation,
    last_updated = EXCLUDED.last_updated
""", (
    farmer_id,
    round(risk_score, 2),
    risk_level,
    "\n".join(explanation),
    datetime.now()
))
    return {
    "risk_score": round(risk_score, 2),
    "risk_level": risk_level,

    "explanation": explanation,

    "breakdown": {
        "verification_risk": round(verification_risk * 100, 2),
        "mismatch_risk": round(mismatch_risk * 100, 2),
        "overcommitment_risk": round(overcommitment_risk * 100, 2),
        "inconsistency_risk": round(inconsistency_risk * 100, 2)
    }
}

import math

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

def predict_failure(risk):
    # Convert risk_score into smoother probability
    raw_score = risk.get("risk_score", 0)

    # Center around 0.5 and scale
    probability = sigmoid((raw_score - 0.5) * 5)

    if probability > 0.7:
        prediction = "Likely to FAIL next week"
    elif probability > 0.4:
        prediction = "Unstable"
    else:
        prediction = "Stable"

    return {
        "farmer_id": risk["farmer_id"],
        "failure_probability": round(probability, 2),
        "prediction": prediction
    }

def compute_time_risk_trend(deliveries):
    if len(deliveries) < 3:
        return []

    deliveries = sorted(deliveries, key=lambda x: x["week_start"])

    trend_series = []

    for d in deliveries:
        promised = d["promised_qty"] or 0
        delivered = d["delivered_qty"] or 0

        if promised == 0:
            risk = 1
        else:
            risk = 1 - (delivered / promised)

        trend_series.append({
            "week": d["week_start"],
            "risk": round(risk, 2)
        })

    return trend_series

def generate_intervention(risk, all_results=None):
    actions = []

    level = risk.get("risk_level")
    delivery_rate = risk.get("delivery_rate", 1)
    overcommitment = risk.get("overcommitment", 0)
    trend = risk.get("trend", 0)

    # -----------------------------
    # Base actions
    # -----------------------------
    if level == "HIGH":
        actions.append("Reduce commitments immediately")
        actions.append("Flag farmer for manual review")

    if overcommitment > 0.3:
        actions.append("Rebalance committed quantities")

    if delivery_rate < 0.7:
        actions.append("Reallocate demand to reliable farmers")

    if trend < 0:
        actions.append("Investigate performance decline")

    # -----------------------------
    # AUTO REALLOCATION ENGINE (FIXED)
    # -----------------------------
    reallocation_targets = []

    if all_results and level == "HIGH":
        for r in all_results:
            other = r["risk"]

            if (
                other.get("risk_level") == "LOW"
                and other.get("delivery_rate", 0) > 0.8
                and other.get("consistency", 0) > 0.7
                and other.get("farmer_id") != risk.get("farmer_id")
            ):
                reallocation_targets.append({
                    "farmer_id": other["farmer_id"],
                    "score": other["delivery_rate"]
                })

        # Sort best candidates
        reallocation_targets = sorted(
            reallocation_targets,
            key=lambda x: x["score"],
            reverse=True
        )

        top_targets = [t["farmer_id"] for t in reallocation_targets[:3]]

        if top_targets:
            actions.append(f"Shift demand to farmers {top_targets}")

    # fallback
    if not actions:
        actions.append("No immediate action required")

    return {
        "farmer_id": risk.get("farmer_id"),
        "actions": actions
    }

def recompute_all_risks():
    conn, cursor = get_db()

    try:
        # 1. Clear old logs
        cursor.execute("DELETE FROM decision_logs")

        # 2. Get all farmers
        cursor.execute("SELECT id FROM users WHERE role = 'farmer'")
        farmers = cursor.fetchall()

        for f in farmers:
            farmer_id = f["id"]

            #STEP A: Compute + cache risk
            compute_farmer_risk_v2(cursor, farmer_id)

            #STEP B: System-level overcommit logging
            cursor.execute("""
    SELECT COALESCE(SUM(qty_max),0) AS total_supply
    FROM farmer_supply
    WHERE farmer_id = %s
""", (farmer_id,))

            row = cursor.fetchone()
            total_supply = row["total_supply"] or 0
            cursor.execute("""
                SELECT crop, COALESCE(SUM(promised_qty),0) AS total
                FROM commitments
                WHERE farmer_id = %s
                GROUP BY crop
            """, (farmer_id,))
            rows = cursor.fetchall()

            for r in rows:
                crop = r["crop"]
                promised = r["total"]

                over = max(0, promised - total_supply)

                if total_supply > 0:
                    over_ratio = round(over / total_supply, 2)
                else:
                    over_ratio = 0

                if over > 0:
                    cursor.execute("""
                        INSERT INTO decision_logs
                        (farmer_id, crop, week, over_amount, explanation)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        farmer_id,
                        crop,
                        datetime.now().date().isoformat(),
                        over,
                        f"{crop} overcommitted by {int(over)} units ({int(over_ratio*100)}% beyond capacity)"
                    ))

        conn.commit()

    finally:
        conn.close()
# ======================================================
# ROUTES
# ======================================================
# -----------------------------
# CREATE SUPPLY (MERGE SAFE)
# -----------------------------
@app.post("/supply", response_model=SupplyOut)
def create_supply(s: SupplyCreate, user=Depends(require_farmer)):

    conn, cursor = get_db()

    crop = normalize(s.crop)
    if crop not in VALID_CROPS:
        raise HTTPException(400, f"Unsupported crop: {crop}")

    if s.qty_min > s.qty_max:
        raise HTTPException(400, "qty_min cannot exceed qty_max")

    if s.available_from > s.available_to:
        raise HTTPException(400, "available_from cannot be after available_to")

    now = datetime.utcnow().isoformat()

    # ------------------------------------
    # CHECK IF SAME SUPPLY ALREADY EXISTS
    # ------------------------------------
    cursor.execute("""
    SELECT id, qty_min, qty_max
    FROM farmer_supply
    WHERE farmer_id=%s AND crop=%s AND zone=%s
    AND available_from=%s AND available_to=%s
""", (
    user["id"],
    crop,
    s.zone,
    s.available_from,
    s.available_to
))

    existing = cursor.fetchone()

    # ------------------------------------
    # MERGE IF EXISTS
    # ------------------------------------
    if existing:
        supply_id, old_min, old_max = existing

        new_min = min(old_min, s.qty_min)
        new_max = max(old_max, s.qty_max)

        cursor.execute("""
            UPDATE farmer_supply
            SET qty_min=%s, qty_max=%s, last_updated=%s
            WHERE id=%s
        """, (new_min, new_max, now, supply_id))

        conn.commit()
        conn.close()

        return SupplyOut(
            id=supply_id,
            farmer_id=user["id"],
            crop=crop,
            qty_min=new_min,
            qty_max=new_max,
            zone=s.zone,
            available_from=s.available_from,
            available_to=s.available_to,
            last_updated=datetime.fromisoformat(now)
        )

    # ------------------------------------
    # INSERT NEW
    # ------------------------------------
    cursor.execute("""
    INSERT INTO farmer_supply (
        farmer_id, crop, qty_min, qty_max, zone,
        available_from, available_to, last_updated
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
""", (
    user["id"],
    crop,
    s.qty_min,
    s.qty_max,
    s.zone,
    s.available_from,
    s.available_to,
    now
))

    supply_id = cursor.fetchone()["id"]
    conn.commit()
    conn.close()

    return SupplyOut(
        id=supply_id,
        farmer_id=user["id"],
        crop=crop,
        qty_min=s.qty_min,
        qty_max=s.qty_max,
        zone=s.zone,
        available_from=s.available_from,
        available_to=s.available_to,
        last_updated=datetime.fromisoformat(now)
    )

# -----------------------------
# LIST SUPPLIES (SAFE)
# -----------------------------
@app.get("/supply", response_model=List[SupplyOut])
def list_supplies(
    crop: Optional[str] = None,
    zone: Optional[str] = None,
    user=Depends(require_farmer)
):
    conn, cursor = get_db()

    query = """
    SELECT id, farmer_id, crop, qty_min, qty_max, zone,
           available_from, available_to, last_updated
    FROM farmer_supply
    WHERE farmer_id=%s
"""
    params = [user["id"]]
    if crop:
        query += " AND crop=%s"
        params.append(normalize(crop))

    if zone:
        query += " AND zone=%s"
        params.append(zone)

    query += " ORDER BY last_updated DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []

    for r in rows:
        try:
           mapped = map_to_supply(dict(r))

           results.append(
            SupplyOut(
                id=mapped["capability_id"],
                farmer_id=mapped["actor_id"],
                crop=mapped["crop"],
                qty_min=mapped["quantity_range"]["min"],
                qty_max=mapped["quantity_range"]["max"],
                zone=mapped["zone"],
                available_from=mapped["availability_window"]["from"],
                available_to=mapped["availability_window"]["to"],
                last_updated=mapped["last_updated"]
            )
        )

        except Exception as e:
            print("Skipping bad row:", r, e)
    return results

# -----------------------------
# UPDATE SUPPLY (FIXED)
# -----------------------------
@app.put("/supply/{supply_id}", response_model=SupplyOut)
def update_supply(supply_id: int, update: SupplyUpdate, user=Depends(require_farmer)):

    conn, cursor = get_db()

    cursor.execute("""
    SELECT crop, zone, qty_min, qty_max, available_from, available_to
    FROM farmer_supply
    WHERE id=%s AND farmer_id=%s
""", (supply_id, user["id"]))

    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Supply not found")

    crop = row["crop"]
    zone = row["zone"]
    qty_min = row["qty_min"]
    qty_max = row["qty_max"]
    af = row["available_from"]
    at = row["available_to"]

    qty_min = update.qty_min if update.qty_min is not None else qty_min
    qty_max = update.qty_max if update.qty_max is not None else qty_max
    af = update.available_from if update.available_from is not None else to_date(af)
    at = update.available_to if update.available_to is not None else to_date(at)

    if qty_min > qty_max:
        raise HTTPException(400, "qty_min cannot exceed qty_max")
    if af > at:
        raise HTTPException(400, "available_from cannot be after available_to")

    now = datetime.utcnow().isoformat()

    cursor.execute("""
        UPDATE farmer_supply
        SET qty_min=%s, qty_max=%s, available_from=%s, available_to=%s, last_updated=%s
        WHERE id=%s AND farmer_id=%s
    """, (
        qty_min,
        qty_max,
        af.isoformat(),
        at.isoformat(),
        now,
        supply_id,
        user["id"]
    ))

    conn.commit()
    recompute_all_risks()
    conn.close()

    return SupplyOut(
        id=supply_id,
        farmer_id=user["id"],
        crop=crop,
        qty_min=qty_min,
        qty_max=qty_max,
        zone=zone,
        available_from=af,
        available_to=at,
        last_updated=datetime.fromisoformat(now)
    )

# -----------------------------
# DELETE SUPPLY
# -----------------------------
@app.delete("/supply/{supply_id}")
def delete_supply(supply_id: int, user=Depends(require_farmer)):

    conn, cursor = get_db()

    cursor.execute(
        "DELETE FROM farmer_supply WHERE id=%s AND farmer_id=%s",
        (supply_id, user["id"])
    )

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(404, "Supply not found")

    conn.commit()
    recompute_all_risks()
    conn.close()

    return {"message": "Supply deleted"}

# ==================================================
# CREATE COMMITMENT
# ==================================================
@app.post("/commitment", response_model=CommitmentOut)
def create_commitment(cmt: CommitmentCreate, user=Depends(require_farmer)):

    conn, cursor = get_db()

    try:
        crop = normalize(cmt.crop)
        if crop not in VALID_CROPS:
            raise HTTPException(400, f"Unsupported crop: {crop}")

        # ---- fetch supply ----
        cursor.execute("""
    SELECT qty_max, available_from, available_to
    FROM farmer_supply
    WHERE farmer_id=%s AND crop=%s AND zone=%s
""", (user["id"], crop, cmt.zone))

        supply_rows = cursor.fetchall()
        if not supply_rows:
            raise HTTPException(400, "No registered supply found for this crop and zone")

        delivery_start = to_date(cmt.delivery_start)
        delivery_end = to_date(cmt.delivery_end)

     # Check if ANY supply window supports this commitment
        valid_window = False
        total_capacity = 0

        for row in supply_rows:
            qty_max = row["qty_max"]
            avail_from = to_date(row["available_from"])
            avail_to = to_date(row["available_to"])
            if delivery_start >= avail_from and delivery_end <= avail_to:
                valid_window = True
                total_capacity += qty_max

        if not valid_window:
            raise HTTPException(400, "Delivery window must match at least one supply window")
        # ---- current commitments ----
        cursor.execute("""
    SELECT COALESCE(SUM(promised_qty),0) as total
    FROM commitments
    WHERE farmer_id=%s AND crop=%s AND zone=%s
""", (user["id"], crop, cmt.zone))

        row = cursor.fetchone()
        current_commitments = row["total"] if row else 0

        # ---- detect overcommit (DO NOT BLOCK) ----
        new_total = current_commitments + cmt.promised_qty
        over_commit = max(0, new_total - total_capacity)
        now_dt = datetime.utcnow()

        # ---- insert commitment ----
        cursor.execute("""
    INSERT INTO commitments (
        farmer_id, crop, promised_qty, zone,
        delivery_start, delivery_end,
        status, created_at, last_updated
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
""", (
    user["id"],
    crop,
    cmt.promised_qty,
    cmt.zone,
    cmt.delivery_start,
    cmt.delivery_end,
    "PENDING",
    now_dt,
    now_dt
))

        commitment_id = cursor.fetchone()["id"]
        # ---- log overcommit ----
        if over_commit > 0:
            cursor.execute("""
        INSERT INTO decision_logs (farmer_id, crop, week, over_amount, explanation)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        user["id"],
        crop,
        cmt.delivery_start.isoformat(),
        over_commit,
        "Overcommitment detected"
    ))
        else:
            cursor.execute("""
        INSERT INTO decision_logs (farmer_id, crop, week, over_amount, explanation)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        user["id"],
        crop,
        cmt.delivery_start.isoformat(),
        0,
        "Commitment within safe capacity"
    ))
        conn.commit()
        recompute_all_risks()
        return CommitmentOut(
            id=commitment_id,
            farmer_id=user["id"],
            crop=crop,
            promised_qty=cmt.promised_qty,
            zone=cmt.zone,
            delivery_start=cmt.delivery_start,
            delivery_end=cmt.delivery_end,
            status="PENDING",
            created_at=now_dt,
            last_updated=now_dt
        )

    finally:
        conn.close()
# ==================================================
# LIST COMMITMENTS
# ==================================================
@app.get("/commitments", response_model=List[CommitmentOut])
def list_commitments(user=Depends(require_farmer)):
    """
    List commitments for the current farmer only.
    """
    conn, cursor = get_db()
    cursor.execute("""
    SELECT id, farmer_id, crop, promised_qty, zone,
           delivery_start, delivery_end,
           status, created_at, last_updated
    FROM commitments
    WHERE farmer_id=%s
    ORDER BY created_at DESC
""", (user["id"],))

    rows = cursor.fetchall()
    conn.close()

    results = []

    for r in rows:

        mapped = map_to_commitment(dict(r))

        results.append(
        CommitmentOut(
            id=mapped["obligation_id"],
            farmer_id=mapped["actor_id"],
            crop=mapped["crop"],
            promised_qty=mapped["promised_quantity"],
            zone=mapped["zone"],
            delivery_start=to_date(mapped["delivery_window"]["start"]),
            delivery_end=to_date(mapped["delivery_window"]["end"]),
            status=mapped["status"],
            created_at=to_datetime(mapped["created_at"]),
            last_updated=to_datetime(mapped["last_updated"]),
        )
    )

    return results
# ==================================================
# UPDATE COMMITMENT
# ==================================================
@app.put("/commitment/{commitment_id}", response_model=CommitmentOut)
def update_commitment(commitment_id: int, update: CommitmentUpdate, user=Depends(require_farmer)):

    conn, cursor = get_db()

    # ---- get existing commitment ----
    cursor.execute("""
        SELECT crop, promised_qty, zone,
               delivery_start, delivery_end,
               status, created_at
        FROM commitments
        WHERE id=%s AND farmer_id=%s
    """, (commitment_id, user["id"]))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Commitment not found")

    crop = row["crop"]
    current_qty = row["promised_qty"]
    zone = row["zone"]
    d_start = row["delivery_start"]
    d_end = row["delivery_end"]
    status = row["status"]
    created_at = row["created_at"]

    delivery_start = to_date(update.delivery_start) if update.delivery_start else to_date(d_start)
    delivery_end = to_date(update.delivery_end) if update.delivery_end else to_date(d_end)
    promised_qty = update.promised_qty if update.promised_qty is not None else current_qty

    # ---- fetch supply ----
    cursor.execute("""
        SELECT qty_max, available_from, available_to
        FROM farmer_supply
        WHERE farmer_id=%s AND crop=%s AND zone=%s
    """, (user["id"], crop, zone))
    supply_row = cursor.fetchone()
    if not supply_row:
        conn.close()
        raise HTTPException(400, "No registered supply found for this crop and zone")

    qty_max = supply_row["qty_max"]
    avail_from = supply_row["available_from"]
    avail_to = supply_row["available_to"]
    avail_from_date = to_date(avail_from)
    avail_to_date = to_date(avail_to)

    # ---- validations ----
    # compute total capacity across matching supply windows
    cursor.execute("""
    SELECT qty_max
    FROM farmer_supply
    WHERE farmer_id=%s AND crop=%s AND zone=%s
""", (user["id"], crop, zone))
    supply_rows = cursor.fetchall()

    total_capacity = sum(r["qty_max"] for r in supply_rows)

    if promised_qty > total_capacity:
        conn.close()
        raise HTTPException(400, "Promised quantity exceeds total available supply")
    
    if delivery_start < avail_from_date or delivery_end > avail_to_date:
        conn.close()
        raise HTTPException(400, "Delivery window must be within registered supply availability")

    # ---- update ----
    last_updated_dt = datetime.utcnow()

    cursor.execute("""
        UPDATE commitments
        SET promised_qty=%s, delivery_start=%s, delivery_end=%s, last_updated=%s
        WHERE id=%s AND farmer_id=%s
    """, (
        promised_qty,
        delivery_start.isoformat(),
        delivery_end.isoformat(),
        last_updated_dt,
        commitment_id,
        user["id"]
    ))

    conn.commit()
    recompute_all_risks()
    conn.close()

    return CommitmentOut(
        id=commitment_id,
        farmer_id=user["id"],
        crop=crop,
        promised_qty=promised_qty,
        zone=zone,
        delivery_start=delivery_start,
        delivery_end=delivery_end,
        status=status,
        created_at=to_datetime(created_at),
        last_updated=last_updated_dt
    )

# ==================================================
# DELETE COMMITMENT
# ==================================================
@app.delete("/commitment/{commitment_id}")
def delete_commitment(commitment_id: int, user=Depends(require_farmer)):

    conn, cursor = get_db()

    cursor.execute("""
        DELETE FROM commitments
        WHERE id=%s AND farmer_id=%s
    """, (commitment_id, user["id"]))

    deleted = cursor.rowcount
    conn.commit()
    recompute_all_risks() 
    conn.close()

    if not deleted:
        raise HTTPException(404, "Commitment not found or not owned by farmer")

    return {"message": "Commitment deleted successfully"}

@app.get("/feasibility/all")
def feasibility_all(user=Depends(require_admin)):
    conn, cursor = get_db()
    cursor.execute("SELECT DISTINCT farmer_id FROM commitments")
    farmers = cursor.fetchall()

    results = []
    for f in farmers:
        results.append(check_feasibility(f["farmer_id"]))

    return results

@app.get("/feasibility/me")
def feasibility_me(user=Depends(require_farmer)):
    return check_feasibility(user["id"])

@app.get("/admin/feasibility/{farmer_id}")
def feasibility_for_farmer(farmer_id: int, user=Depends(require_admin)):
    return check_feasibility(farmer_id)

@app.get("/admin/feasibility/all")
def feasibility_all_admin(user=Depends(require_admin)):
    conn, cursor = get_db()
    cursor.execute("SELECT DISTINCT farmer_id FROM commitments")
    farmers = cursor.fetchall()

    return [check_feasibility(f["farmer_id"]) for f in farmers]

# ----------------------------
# LOG A DELIVERY
# ----------------------------
@app.post("/delivery")
def log_delivery(d: DeliveryCreate, user=Depends(require_farmer)):
    conn, cursor = get_db()

    try:
        # ----------------------------
        # Fetch commitment info
        # ----------------------------
        cursor.execute("""
            SELECT farmer_id, promised_qty
            FROM commitments
            WHERE id = %s
        """, (d.commitment_id,))
        commitment = cursor.fetchone()

        if not commitment:
            raise HTTPException(status_code=404, detail="Commitment not found")

        if commitment["farmer_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Cannot log delivery for another farmer's commitment")

        promised_qty = commitment["promised_qty"]
        farmer_id = commitment["farmer_id"]

        # ----------------------------
        # Compute delivery status (for THIS delivery)
        # ----------------------------
        # Get total delivered so far INCLUDING this delivery
        cursor.execute("""
    SELECT SUM(delivered_qty) as total_delivered
    FROM deliveries
    WHERE commitment_id = %s
""", (d.commitment_id,))
        previous_total = cursor.fetchone()["total_delivered"] or 0
        cursor.execute("""
    SELECT delivery_start, delivery_end
    FROM commitments
    WHERE id = %s
""", (d.commitment_id,))
        dates = cursor.fetchone()

        from datetime import datetime

        start = to_date(dates["delivery_start"])
        end = to_date(dates["delivery_end"])

        days = (end - start).days + 1
        import math
        num_weeks = max(1, math.ceil(days / 7))
        weekly_promised_qty = promised_qty / num_weeks
        # Compute status ONLY for this delivery
        # TEMP status for individual entry (optional, not authoritative anymore)
        status = "RECORDED"
        # ----------------------------
        # Insert delivery record
        # ----------------------------
        cursor.execute("""
    INSERT INTO deliveries
(
    commitment_id,
    delivered_qty,
    week_start,
    week_end,
    status,
    verification_status,
    weekly_promised_qty
)
VALUES (%s, %s, %s, %s, %s, %s, %s)
""", (
    d.commitment_id,
    d.delivered_qty,
    to_date(d.week_start),
    to_date(d.week_end),
    status,
    "PENDING",
    weekly_promised_qty
))
        # ----------------------------
        # UPDATE COMMITMENT STATUS (CRITICAL FIX)
        # ----------------------------
        # Get total delivered so far for this commitment
        cursor.execute("""
            SELECT SUM(delivered_qty) as total_delivered
            FROM deliveries
            WHERE commitment_id = %s
        """, (d.commitment_id,))
        total_delivered = cursor.fetchone()["total_delivered"] or 0
        # SAFETY: prevent over-delivery weirdness
        total_delivered = min(total_delivered, promised_qty)
        # Determine commitment status
        if total_delivered >= promised_qty:
            commitment_status = "COMPLETED"
        elif total_delivered > 0:
            commitment_status = "PARTIAL"
        else:
            commitment_status = "PENDING"

        # Update commitment
        cursor.execute("""
            UPDATE commitments
            SET status = %s, last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (commitment_status, d.commitment_id))

        conn.commit()
        recompute_all_risks()
        # ----------------------------
        # Update farmer trust
        # ----------------------------
        
        return {
            "message": "Delivery logged",
            "delivery_status": status,
            "commitment_status": commitment_status,
            "total_delivered": total_delivered
        }

    except HTTPException as he:
        raise he

    except Exception as e:
        print("Error logging delivery:", e)
        raise HTTPException(status_code=500, detail="Failed to log delivery")

    finally:
        conn.close()
# ----------------------------
# GET ALL DELIVERIES
# ----------------------------
@app.get("/deliveries", response_model=List[dict])
def get_deliveries(
    farmer_id: int = Query(...),
    crop: Optional[str] = None,
    user=Depends(require_user)
):
    """
    Get all deliveries for a specific farmer with FULL context.
    """

    if user["role"] == "farmer" and user["id"] != farmer_id:
        raise HTTPException(status_code=403, detail="You can only view your own deliveries")

    conn, cursor = get_db()

    query = """
        SELECT 
            d.id,
            d.commitment_id,
            d.delivered_qty,
            d.week_start,
            d.week_end,
            d.status,

            c.crop,
            c.zone,
            c.promised_qty,
            c.status as commitment_status

        FROM deliveries d
        JOIN commitments c ON d.commitment_id = c.id
        WHERE c.farmer_id = %s
    """

    params = [farmer_id]

    if crop:
        query += " AND LOWER(c.crop) = %s"
        params.append(crop.lower())

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []

    for r in rows:

        mapped = map_to_delivery(dict(r))

        results.append({
        "id": mapped["execution_id"],
        "commitment_id": mapped["obligation_id"],
        "delivered_qty": mapped["delivered_qty"],
        "week_start": mapped["week_window"]["start"],
        "week_end": mapped["week_window"]["end"],
        "status": mapped["execution_state"],

        "crop": r["crop"],
        "zone": r["zone"],
        "promised_qty": r["promised_qty"],
        "commitment_status": r["commitment_status"],

        "farmer_id": farmer_id,

        # NEW semantic field
        "fulfillment_ratio": mapped["fulfillment_ratio"]
    })

    return results
@app.get("/deliveries/{commitment_id}")
def delivery_history(commitment_id: int, user=Depends(require_user)):
    conn, cursor = get_db()

    # Fetch commitment owner
    cursor.execute("SELECT farmer_id FROM commitments WHERE id = %s", (commitment_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Commitment not found")

    commitment_farmer_id = row["farmer_id"]

    # Only allow owner or admin
    if user["role"] != "admin" and user["id"] != commitment_farmer_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Access denied")

    cursor.execute("""
        SELECT 
    d.*,
    c.crop,
    c.zone,
    c.promised_qty
FROM deliveries d
JOIN commitments c ON d.commitment_id = c.id
WHERE d.commitment_id = %s
    """, (commitment_id,))
    rows = cursor.fetchall()

    result = []
    for r in rows:

        mapped = map_to_delivery(dict(r))

        result.append({
        "id": mapped["execution_id"],
        "commitment_id": mapped["obligation_id"],

        "crop": r["crop"],
        "zone": r["zone"],

        "promised_qty": r["promised_qty"],
        "delivered_qty": mapped["delivered_qty"],

        "week_start": mapped["week_window"]["start"],
        "week_end": mapped["week_window"]["end"],

        "status": mapped["execution_state"],

        # NEW semantic field
        "fulfillment_ratio": mapped["fulfillment_ratio"]
    })

    conn.close()
    return result

@app.delete("/deliveries/{delivery_id}")
def delete_delivery(delivery_id: int, user=Depends(require_farmer)):

    conn, cursor = get_db()

    # Ensure ownership
    cursor.execute("""
    SELECT 
        c.farmer_id,
        d.commitment_id
    FROM deliveries d
    JOIN commitments c ON d.commitment_id = c.id
    WHERE d.id = %s
""", (delivery_id,))
    
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(404, "Delivery not found")

    if row["farmer_id"] != user["id"]:
        conn.close()
        raise HTTPException(403, "Not allowed")

    commitment_id = row["commitment_id"]

    cursor.execute("DELETE FROM deliveries WHERE id = %s", (delivery_id,))
    # recompute totals
    cursor.execute("""
    SELECT promised_qty
    FROM commitments
    WHERE id = %s
""", (commitment_id,))

    commitment = cursor.fetchone()
    promised_qty = commitment["promised_qty"]

    cursor.execute("""
    SELECT COALESCE(SUM(delivered_qty), 0) AS total
    FROM deliveries
    WHERE commitment_id = %s
""", (commitment_id,))

    total_delivered = cursor.fetchone()["total"]

# determine status
    if total_delivered >= promised_qty:
        new_status = "COMPLETED"
    elif total_delivered > 0:
        new_status = "PARTIAL"
    else:
        new_status = "PENDING"

# update commitment
    cursor.execute("""
    UPDATE commitments
    SET status=%s, last_updated=CURRENT_TIMESTAMP
    WHERE id=%s
""", (new_status, commitment_id))
    conn.commit()
    conn.close()

    return {"message": "Delivery deleted successfully"}

@app.get("/dashboard/farmer/{farmer_id}")
def farmer_dashboard(
    farmer_id: int,
    user=Depends(require_user)
):

    conn, cursor = get_db()

    try:

        # --------------------------------
        # AUTH VALIDATION
        # --------------------------------
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized"
            )

        role = user.get("role")
        user_id = user.get("id")

        # --------------------------------
        # ACCESS CONTROL
        # --------------------------------
        if role == "farmer" and user_id != farmer_id:
            raise HTTPException(
                status_code=403,
                detail="You can only access your own dashboard"
            )

        if role not in ["farmer", "admin", "buyer"]:
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

        # --------------------------------
        # GENERATE DASHBOARD
        # --------------------------------
        dashboard = generate_farmer_dashboard(
            conn,
            farmer_id
        )

        if "error" in dashboard:
            raise HTTPException(
                status_code=500,
                detail=dashboard["error"]
            )

        return dashboard

    except HTTPException as he:
        raise he

    except Exception as e:

        print("Dashboard route error:", e)

        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

    finally:
        conn.close()

@app.get("/dashboard/admin")
def admin_dashboard(user=Depends(require_admin)):
    conn, cursor = get_db()
    try:
        return generate_admin_dashboard(conn)
    finally:
        conn.close()
# ===============================
# USER REGISTRATION
# ===============================

@app.post("/register")
def register(name: str, email: str, password: str, role: str, admin_access_code: str = None):
    conn, cursor = get_db()

    if role not in ["farmer", "admin"]:
        raise HTTPException(status_code=400, detail="Role must be farmer or admin")

    # Secure admin check
    if role == "admin":
        if not admin_access_code or admin_access_code != ADMIN_SECRET_CODE:
            raise HTTPException(status_code=403, detail="Invalid admin access code")

    hashed = hash_password(password)

    try:
        cursor.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, %s)
        """, (name, email, hashed, role))
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Email already registered")

    return {"message": "User registered successfully"}

@app.post("/login")
def login(email: str, password: str):

    conn, cursor = get_db()

    try:
        cursor.execute("""
            SELECT id, password, role
            FROM users
            WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_id = user["id"]
        hashed_password = user["password"]
        role = user["role"]

        if not verify_password(password, hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # TOKEN (Option A — correct)
        token = create_access_token({
    "id": user_id,     # STANDARDIZED
    "role": role
})
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": role,
            "user_id": user_id
        }

    finally:
        conn.close()
        
@app.get("/dashboard/admin/feasibility")
def admin_feasibility_summary(user=Depends(require_admin)):
    conn, cursor = get_db()

    cursor.execute("""
    SELECT DISTINCT farmer_id
    FROM (
        SELECT farmer_id FROM commitments
        UNION
        SELECT farmer_id FROM farmer_supply
    ) x
""")
    farmers = cursor.fetchall()

    total_farmers = len(farmers)
    overcommitted_farmers = 0
    total_overcommitments = 0

    farmer_risk = []

    for f in farmers:
        result = check_feasibility(f["farmer_id"])
        over = len(result["over_commitments"])

        if over > 0:
            overcommitted_farmers += 1

        total_overcommitments += over

        farmer_risk.append({
            "farmer_id": f["farmer_id"],
            "overcommitments": over
        })

    system_feasibility_score = (
        1 - (overcommitted_farmers / total_farmers)
        if total_farmers > 0 else 1
    )

    return {
        "total_farmers": total_farmers,
        "overcommitted_farmers": overcommitted_farmers,
        "total_overcommitments": total_overcommitments,
        "system_feasibility_score": round(system_feasibility_score, 2),
        "farmer_risk_ranking": sorted(
            farmer_risk,
            key=lambda x: x["overcommitments"],
            reverse=True
        )
    }

# ----------------------------
# GET ALL FARMERS (ADMIN ONLY)
# ----------------------------
@app.get("/farmers")
def get_all_farmers(user=Depends(require_admin)):
    conn, cursor = get_db()

    cursor.execute("""
        SELECT id, name, email
        FROM users
        WHERE role = 'farmer'
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r["id"],
            "name": r["name"],
            "email": r["email"]
        }
        for r in rows
    ]

@app.get("/risk-intelligence")
def risk_intelligence(user=Depends(require_admin)):
    conn, cursor = get_db()

    try:
        cursor.execute("SELECT id FROM users WHERE role = 'farmer'")
        farmers = [r["id"] for r in cursor.fetchall()]

        results = []

        for fid in farmers:

            #READ FROM CACHE
            cursor.execute("""
                SELECT risk_score, risk_level
                FROM farmer_risk_cache
                WHERE farmer_id = %s
            """, (fid,))

            row = cursor.fetchone()
            
            risk = compute_farmer_risk_v2(cursor, fid)

            if row:
                  risk = {
        "risk_score": row["risk_score"] or 0,
        "risk_level": row["risk_level"] or "LOW",
        "over_amount": 0,
        "main_crop": "unknown",
        "delivery_failure_rate": 0,
        "reliability_score": 100
    }
            try:
               prediction = predict_failure(risk)
            except Exception:
               prediction = {
        "failure_probability": 0
    }
            results.append({
                "farmer_id": fid,
                "risk": risk,
                "prediction": prediction
            })

        # SORT
        results.sort(
            key=lambda x: x["risk"].get("risk_score", 0),
            reverse=True
        )

        # INTERVENTIONS
        for r in results:
            try:
               r["intervention"] = generate_intervention(r["risk"], results)
            except Exception:
               r["intervention"] = {
        "actions": []
    }
        # BUILD RESPONSE
        risk_alerts = []
        farmer_risk_ranking = []
        recommended_actions = []
        high_risk_count = 0

        for r in results:
            risk = r["risk"]
            prediction = r["prediction"]

            if risk.get("risk_level") == "HIGH":
                high_risk_count += 1

                risk_alerts.append({
                    "farmer_id": r["farmer_id"],
                    "prediction": round(prediction["failure_probability"] * 100, 1),
                    "over_amount": risk.get("over_amount", 0),
                    "crop": risk.get("main_crop", "unknown")
                })

            farmer_risk_ranking.append({
                "farmer_id": r["farmer_id"],
                "risk_level": risk.get("risk_level"),
                "prediction": prediction["failure_probability"] * 100
            })

            for action in r["intervention"]["actions"]:
                recommended_actions.append(
                    f"Farmer {r['farmer_id']}: {action}"
                )

        # SYSTEM STATUS
        if high_risk_count > 2:
            system_status = "UNSTABLE"
        elif high_risk_count > 0:
            system_status = "WARNING"
        else:
            system_status = "STABLE"

        return {
            "system_status": system_status,
            "risk_alerts": risk_alerts,
            "farmer_risk_ranking": farmer_risk_ranking,
            "recommended_actions": recommended_actions,
            "full_results": results
        }

    finally:
        conn.close()

@app.delete("/farmer/delete-account")
def delete_own_account(user=Depends(get_current_user)):
    conn, cursor = get_db()

    try:
        user_id = user["id"]

        # Delete everything tied to farmer
        cursor.execute("DELETE FROM deliveries WHERE commitment_id IN (SELECT id FROM commitments WHERE farmer_id = %s)", (user_id,))
        cursor.execute("DELETE FROM commitments WHERE farmer_id = %s", (user_id,))
        cursor.execute("DELETE FROM farmer_supply WHERE farmer_id = %s", (user_id,))
        cursor.execute("DELETE FROM decision_logs WHERE farmer_id = %s", (user_id,))
        cursor.execute("DELETE FROM farmer_trust WHERE farmer_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

        conn.commit()

        return {"message": "Your account has been deleted"}

    finally:
        conn.close()

@app.delete("/admin/users/{user_id}")
def delete_user(user_id: int, user=Depends(require_admin)):

    conn, cursor = get_db()

    try:
        # -------------------------
        # Prevent admin deleting themselves
        # -------------------------
        if user["id"] == user_id:
            raise HTTPException(
                status_code=400,
                detail="You cannot delete your own account"
            )

        # -------------------------
        # Check user exists
        # -------------------------
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        target = cursor.fetchone()

        if not target:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        # -------------------------
        # Prevent deleting last admin
        # -------------------------
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'admin'")
        admin_count = cursor.fetchone()["count"]

        if target["role"] == "admin" and admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last admin"
            )

        # -------------------------
        # DELETE CASCADE (manual for SQLite)
        # -------------------------
        cursor.execute("""
            DELETE FROM deliveries
            WHERE commitment_id IN (
                SELECT id FROM commitments WHERE farmer_id = %s
            )
        """, (user_id,))

        cursor.execute("DELETE FROM commitments WHERE farmer_id = %s", (user_id,))
        cursor.execute("DELETE FROM farmer_supply WHERE farmer_id = %s", (user_id,))
        cursor.execute("DELETE FROM decision_logs WHERE farmer_id = %s", (user_id,))
        cursor.execute("DELETE FROM farmer_trust WHERE farmer_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

        conn.commit()

        return {"message": "User and all related data deleted successfully"}

    finally:
        conn.close()
@app.get("/admin/report/term")
def generate_term_report(user=Depends(require_admin)):

    conn, cursor = get_db()

    # -----------------------------
    # TOTALS
    # -----------------------------
    cursor.execute("SELECT SUM(qty_max) as total_supply FROM farmer_supply")
    total_supply = cursor.fetchone()["total_supply"] or 0

    cursor.execute("SELECT SUM(promised_qty) as total_committed FROM commitments")
    total_committed = cursor.fetchone()["total_committed"] or 0

    cursor.execute("SELECT SUM(delivered_qty) as total_delivered FROM deliveries")
    total_delivered = cursor.fetchone()["total_delivered"] or 0
    
    total_delivered = min(total_delivered, total_committed)
    fulfillment_rate = (total_delivered / total_committed) if total_committed > 0 else 0

    # -----------------------------
    # FARMER PERFORMANCE
    # -----------------------------
    cursor.execute("""
        SELECT 
    c.farmer_id,
    SUM(c.promised_qty) as promised,
    COALESCE(SUM(d.total_delivered), 0) as delivered
FROM commitments c
LEFT JOIN (
    SELECT commitment_id, SUM(delivered_qty) as total_delivered
    FROM deliveries
    GROUP BY commitment_id
) d ON d.commitment_id = c.id
GROUP BY c.farmer_id
    """)
    rows = cursor.fetchall()

    farmers = []

    for r in rows:
        promised = r["promised"] or 0
        delivered = r["delivered"] or 0

        completion = (delivered / promised) if promised > 0 else 0

        # -----------------------------
        # GET RISK FROM CACHE
        # -----------------------------
        cursor.execute("""
    SELECT risk_score, risk_level
    FROM farmer_risk_cache
    WHERE farmer_id = %s
""", (r["farmer_id"],))
        risk_row = cursor.fetchone()

        if risk_row:
            risk_level = risk_row["risk_level"]
            risk_score = risk_row["risk_score"]
        else:
            risk = compute_farmer_risk(cursor, r["farmer_id"])
            risk_level = risk["risk_level"]
            risk_score = risk["risk_score"]

        farmers.append({
    "farmer_id": r["farmer_id"],
    "promised": promised,
    "delivered": delivered,
    "reliability": round(completion * 100, 2),
    "risk_level": risk_level,
    "risk_score": risk_score,
    "message": f"Farmer is {risk_level} risk with {int(completion * 100)}% delivery success"
})
    # -----------------------------
    # OVERCOMMITMENT
    # -----------------------------
    overcommitment = max(total_committed - total_supply, 0)

    conn.close()

    return {
        "system_summary": {
            "total_supply": total_supply,
            "total_committed": total_committed,
            "total_delivered": total_delivered,
            "fulfillment_rate": round(fulfillment_rate * 100, 2),
            "overcommitment": overcommitment
        },
        "farmer_performance": farmers,
        "generated_at": datetime.now().isoformat()
    }

@app.put("/deliveries/{delivery_id}")
def update_delivery(delivery_id: int, d: DeliveryUpdate, user=Depends(require_farmer)):

    conn, cursor = get_db()

    try:
        # Check ownership
        cursor.execute("""
            SELECT c.farmer_id, d.commitment_id
            FROM deliveries d
            JOIN commitments c ON d.commitment_id = c.id
            WHERE d.id = %s
        """, (delivery_id,))
        
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Delivery not found")

        if row["farmer_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Not allowed")

        # Update delivery
        cursor.execute("""
            UPDATE deliveries
            SET delivered_qty = %s, week_start = %s, week_end = %s
            WHERE id = %s
        """, (
            d.delivered_qty,
            to_date(d.week_start).isoformat(),
            to_date(d.week_end).isoformat(),
            delivery_id
        ))

        conn.commit()

        return {"message": "Delivery updated successfully"}

    except Exception as e:
        print("Update error:", e)
        raise HTTPException(status_code=500, detail="Failed to update delivery")

    finally:
        conn.close()

# ==================================================
# VERIFY DELIVERY (BUYER ONLY)
# ==================================================
@app.put("/deliveries/{delivery_id}/verify")
def verify_delivery(
    delivery_id: int,
    payload: DeliveryVerification,
    user=Depends(require_buyer)
):
    conn, cursor = get_db()
    try:

        allowed = ["VERIFIED", "PARTIAL", "REJECTED"]
        if payload.verification_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"verification_status must be one of {allowed}"
            )

        # -----------------------------------
        # Ensure delivery exists
        # -----------------------------------
        cursor.execute("""
            SELECT
                d.id,
                d.delivered_qty,
                d.commitment_id,
                c.farmer_id,
                c.promised_qty
            FROM deliveries d
            JOIN commitments c ON d.commitment_id = c.id
            WHERE d.id = %s
        """, (delivery_id,))

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Delivery not found"
            )

        commitment_id = row["commitment_id"]
        farmer_id = row["farmer_id"]
        promised_qty = row["promised_qty"]

        # -----------------------------------
        # Compute confidence score
        # -----------------------------------
        confidence_score = compute_confidence_score(
            payload.verification_status
        )

# -----------------------------------
# Update delivery verification
# -----------------------------------
        cursor.execute("""
    UPDATE deliveries
    SET
        verification_status = %s,
        confidence_score = %s,
        verification_notes = %s,
        verified_by = %s,
        verified_at = CURRENT_TIMESTAMP
    WHERE id = %s
""", (
    payload.verification_status,
    confidence_score,
    payload.verification_notes,
    user["id"],
    delivery_id
))
        # -----------------------------------
        # Recompute VERIFIED totals ONLY
        # -----------------------------------
        cursor.execute("""
            SELECT COALESCE(SUM(delivered_qty), 0) AS total_verified
            FROM deliveries
            WHERE commitment_id = %s
            AND verification_status = 'VERIFIED'
        """, (commitment_id,))

        verified_total = cursor.fetchone()["total_verified"]

        # SAFETY
        verified_total = min(verified_total, promised_qty)

        # -----------------------------------
        # Compute commitment status
        # -----------------------------------
        if verified_total >= promised_qty:
            commitment_status = "COMPLETED"

        elif verified_total > 0:
            commitment_status = "PARTIAL"

        else:
            commitment_status = "PENDING"

        # -----------------------------------
        # Update commitment
        # -----------------------------------
        cursor.execute("""
            UPDATE commitments
            SET
                status = %s,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            commitment_status,
            commitment_id
        ))

        conn.commit()

        # -----------------------------------
        # UPDATE TRUST
        # -----------------------------------
        try:

            if payload.verification_status == "VERIFIED":
                update_farmer_trust(farmer_id, "COMPLETED")

            elif payload.verification_status == "PARTIAL":
                update_farmer_trust(farmer_id, "PARTIAL")

            elif payload.verification_status == "REJECTED":
                update_farmer_trust(farmer_id, "MISSED")

        except Exception as e:
            print("Trust update failed:", e)

        recompute_all_risks()

        return {
    "message": "Delivery verification updated",
    "delivery_id": delivery_id,
    "verification_status": payload.verification_status,
    "confidence_score": confidence_score,
    "verification_notes": payload.verification_notes,
    "verified_by": user["id"],
    "commitment_status": commitment_status,
    "verified_total": verified_total
}

    except HTTPException as he:
        raise he

    except Exception as e:
        print("Verification error:", e)

        raise HTTPException(
            status_code=500,
            detail="Verification failed"
        )

    finally:
        conn.close()

# ==================================================
# GET VERIFICATION STATUS BY COMMITMENT
# ==================================================
@app.get("/commitments/{commitment_id}/verification-status")
def get_verification_status(
    commitment_id: int,
    user=Depends(require_user)
):
    conn, cursor = get_db()
    try:

        # -----------------------------------
        # Ensure commitment exists
        # -----------------------------------
        cursor.execute("""
            SELECT
                id,
                farmer_id,
                crop,
                promised_qty
            FROM commitments
            WHERE id = %s
        """, (commitment_id,))

        commitment = cursor.fetchone()

        if not commitment:
            raise HTTPException(
                status_code=404,
                detail="Commitment not found"
            )

        # -----------------------------------
        # Access control
        # -----------------------------------
        if (
            user["role"] == "farmer"
            and user["id"] != commitment["farmer_id"]
        ):
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

        # -----------------------------------
        # Fetch deliveries
        # -----------------------------------
        cursor.execute("""
            SELECT
    d.id,
    d.delivered_qty,
    d.week_start,
    d.week_end,
    d.verification_status,
    d.confidence_score,
    d.verification_notes,
    d.verified_by,
    d.verified_at
            FROM deliveries d
            WHERE d.commitment_id = %s
            ORDER BY d.logged_at ASC
        """, (commitment_id,))

        deliveries = cursor.fetchall()

        return {
            "commitment_id": commitment_id,
            "crop": commitment["crop"],
            "promised_qty": commitment["promised_qty"],
            "deliveries": [
                {
                    "delivery_id": d["id"],
                    "delivered_qty": d["delivered_qty"],
                    "week_start": d["week_start"],
                    "week_end": d["week_end"],
                    "verification_status": d["verification_status"],
                    "confidence_score": d["confidence_score"],
                    "verification_notes": d["verification_notes"],
                    "verified_by": d["verified_by"],
                    "verified_at": d["verified_at"]
                }
                for d in deliveries
            ]
        }

    except HTTPException as he:
        raise he

    except Exception as e:
        print("Verification fetch error:", e)

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch verification status"
        )

    finally:
        conn.close()

@app.get("/why/{farmer_id}")
def get_why(farmer_id: int, user=Depends(require_user)):

    conn, cursor = get_db()

    cursor.execute("""
        SELECT crop, week, over_amount, explanation, created_at
        FROM decision_logs
        WHERE farmer_id = %s
        ORDER BY created_at DESC
        LIMIT 20
    """, (farmer_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "crop": r["crop"],
            "week": r["week"],
            "over_amount": r["over_amount"],
            "explanation": r["explanation"],
            "created_at": r["created_at"]
        }
        for r in rows
    ]

@app.get("/admin/users")
def get_all_users(user=Depends(require_admin)):

    conn, cursor = get_db()

    cursor.execute("""
        SELECT id, role
        FROM users
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [
        {"id": r["id"], "role": r["role"]}
        for r in rows
    ]

@app.get("/report/farmer/{farmer_id}")
def generate_weekly_report(farmer_id: int, user=Depends(require_user)):
    conn, cursor = get_db()

    try:
        # -----------------------------
        # AUTH CHECK (important)
        # -----------------------------
        if user["role"] == "farmer" and user["id"] != farmer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # -----------------------------
        # GET RISK FROM CACHE FIRST
        # -----------------------------
        cursor.execute("""
            SELECT risk_score, risk_level
            FROM farmer_risk_cache
            WHERE farmer_id = %s
        """, (farmer_id,))
        row = cursor.fetchone()

        if row:
            risk_level = row["risk_level"]
            risk_score = row["risk_score"]
        else:
            # fallback (rare)
            risk = compute_farmer_risk(cursor, farmer_id)
            risk_level = risk["risk_level"]
            risk_score = risk["risk_score"]

        # -----------------------------
        # GET DELIVERY RATE (light query)
        # -----------------------------
        cursor.execute("""
            SELECT 
                SUM(d.delivered_qty) as total_delivered,
                SUM(c.promised_qty) as total_promised
            FROM commitments c
            LEFT JOIN deliveries d ON d.commitment_id = c.id
            WHERE c.farmer_id = %s
        """, (farmer_id,))
        data = cursor.fetchone()

        total_delivered = data["total_delivered"] or 0
        total_promised = data["total_promised"] or 0

        delivery_rate = (total_delivered / total_promised) if total_promised > 0 else 0

        # -----------------------------
        # FINAL REPORT
        # -----------------------------
        return {
            "farmer_id": farmer_id,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "delivery_rate": round(delivery_rate, 2),
            "message": f"Farmer is {risk_level} risk with {int(delivery_rate * 100)}% delivery success"
        }

    finally:
        conn.close()

@app.get("/debug/reset-db")
def reset_db_debug():
    conn, cursor = get_db()

    try:
        cursor.execute("DROP TABLE IF EXISTS deliveries CASCADE")
        cursor.execute("DROP TABLE IF EXISTS commitments CASCADE")
        cursor.execute("DROP TABLE IF EXISTS farmer_supply CASCADE")
        cursor.execute("DROP TABLE IF EXISTS decision_logs CASCADE")
        cursor.execute("DROP TABLE IF EXISTS farmer_trust CASCADE")
        cursor.execute("DROP TABLE IF EXISTS farmer_risk_cache CASCADE")
        cursor.execute("DROP TABLE IF EXISTS users CASCADE")

        conn.commit()
        return {"message": "Database reset successful"}

    finally:
        conn.close()