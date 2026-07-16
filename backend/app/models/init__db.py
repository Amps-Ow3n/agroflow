# models/init_db.py

from core.db import get_db

def init_db():
    conn, cursor = get_db()

    # =====================================================
    # USERS
    # =====================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK (
            role IN ('farmer','trader','cooperative','processor','buyer','admin')
        ),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # =====================================================
    # SUPPLY SOURCES (multi-actor supply layer)
    # =====================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS supply_sources (
        id SERIAL PRIMARY KEY,
        actor_id INTEGER REFERENCES users(id),
        actor_type TEXT NOT NULL,
        actor_name TEXT NOT NULL,
        product TEXT NOT NULL,
        qty_available INTEGER NOT NULL,
        location TEXT,
        available_from DATE,
        available_to DATE,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # =====================================================
    # SUPPLIER COMMITMENTS (promise layer)
    # =====================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS supplier_commitments (
        id SERIAL PRIMARY KEY,
        supplier_id INTEGER REFERENCES users(id),
        school_id INTEGER REFERENCES users(id),
        product TEXT NOT NULL,
        promised_qty INTEGER NOT NULL,
        delivery_start DATE NOT NULL,
        delivery_end DATE NOT NULL,
        chain_id INTEGER,
        status TEXT DEFAULT 'PENDING',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # =====================================================
    # PROCUREMENT CHAIN (core intelligence backbone)
    # =====================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS procurement_chains (
        id SERIAL PRIMARY KEY,
        commitment_id INTEGER REFERENCES supplier_commitments(id) ON DELETE CASCADE,
        source_id INTEGER REFERENCES supply_sources(id) ON DELETE CASCADE,
        allocated_qty INTEGER NOT NULL,
        chain_position INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # =====================================================
    # DELIVERIES (truth layer controlled by school)
    # =====================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS deliveries (
        id SERIAL PRIMARY KEY,
        commitment_id INTEGER REFERENCES supplier_commitments(id),
        delivered_qty INTEGER DEFAULT 0,
        received_qty INTEGER DEFAULT 0,

        week_start DATE,
        week_end DATE,

        status TEXT DEFAULT 'PENDING',
        verification_status TEXT DEFAULT 'PENDING',

        quality_status TEXT DEFAULT 'PENDING',
        delay_status TEXT DEFAULT 'PENDING',

        confidence_score REAL DEFAULT 0,

        verification_notes TEXT,
        verified_by INTEGER REFERENCES users(id),
        verified_at TIMESTAMP,

        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # =====================================================
    # TRUST (long-term reliability)
    # =====================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS actor_trust (
        actor_id INTEGER PRIMARY KEY,
        score INTEGER DEFAULT 100,
        total_deliveries INTEGER DEFAULT 0
    )
    """)

    # =====================================================
    # RISK CACHE (AI/engine output storage)
    # =====================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS actor_risk_cache (
        actor_id INTEGER PRIMARY KEY,
        risk_score REAL DEFAULT 0,
        risk_level TEXT,
        explanation TEXT,
        last_updated TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()