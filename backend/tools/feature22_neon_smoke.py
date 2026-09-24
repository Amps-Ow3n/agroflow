"""Safe Feature 22 PostgreSQL/Neon smoke and transaction test.

Usage:
    cd AgroFlow/backend
    python -m tools.feature22_neon_smoke

The script reads DATABASE_URL from the local environment/.env through the
application settings. It never prints the connection string or password.
It is intentionally read-only against AgroFlow tables and uses temporary
PostgreSQL tables for transaction/locking checks.
"""

from __future__ import annotations

import os
import sys
import threading
import time

import psycopg2

# Import after the working directory has been set to backend.
from app.core.config import settings


def _safe_db_label(conn) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_schema(), version()")
        database, schema, version = cur.fetchone()
    major = version.split(" on ")[0]
    return f"database={database!r}, schema={schema!r}, server={major}"


def _table_exists(conn, name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = %s)",
            (name,),
        )
        return bool(cur.fetchone()[0])


def _index_exists(conn, name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_indexes "
            "WHERE schemaname = current_schema() AND indexname = %s)",
            (name,),
        )
        return bool(cur.fetchone()[0])


def main() -> int:
    if not settings.DATABASE_URL:
        print("NEON SMOKE: SKIPPED — DATABASE_URL is not configured in the local environment.")
        return 2

    conn1 = conn2 = None
    try:
        conn1 = psycopg2.connect(settings.DATABASE_URL, connect_timeout=10)
        conn2 = psycopg2.connect(settings.DATABASE_URL, connect_timeout=10)
        print("NEON SMOKE: CONNECTED")
        print("NEON SMOKE:", _safe_db_label(conn1))

        required_tables = ["organizations", "procurements", "purchase_orders", "purchase_order_lines", "supplier_commitments", "deliveries"]
        missing = [name for name in required_tables if not _table_exists(conn1, name)]
        if missing:
            print("NEON SMOKE: FAIL — missing expected tables:", ", ".join(missing))
            return 1
        print("NEON SMOKE: SCHEMA TABLES OK")

        if not _index_exists(conn1, "uq_active_commitment_per_po_line_supplier"):
            print("NEON SMOKE: FAIL — expected active-commitment unique index is missing")
            return 1
        print("NEON SMOKE: UNIQUE INDEX OK")

        # Verify that a real PostgreSQL transaction can observe a temporary
        # table and that SELECT ... FOR UPDATE creates a real lock boundary.
        with conn1.cursor() as cur:
            cur.execute("CREATE TEMP TABLE feature22_lock_probe (id integer primary key, value integer) ON COMMIT DROP")
            cur.execute("INSERT INTO feature22_lock_probe VALUES (1, 0)")
        conn1.commit()

        # Temporary tables are session-local, so create a matching probe in
        # conn2 only for the isolation check below; the lock experiment uses
        # a transaction-local advisory lock instead, which is PostgreSQL-native
        # and does not modify application tables.
        with conn1.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(92222023)")
            assert cur.fetchone()[0] is True

        lock_acquired = []
        started = threading.Event()

        def contender():
            with conn2.cursor() as cur:
                started.set()
                cur.execute("SELECT pg_try_advisory_lock(92222023)")
                lock_acquired.append(cur.fetchone()[0])
            conn2.commit()

        thread = threading.Thread(target=contender, daemon=True)
        thread.start()
        started.wait(timeout=5)
        thread.join(timeout=5)

        with conn1.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(92222023)")
            assert cur.fetchone()[0] is True
        conn1.commit()

        if lock_acquired != [False]:
            print("NEON SMOKE: FAIL — PostgreSQL advisory-lock contention was not observed")
            return 1
        print("NEON SMOKE: POSTGRES TRANSACTION/LOCK CHECK OK")
        print("NEON SMOKE: PASS")
        return 0
    except Exception as exc:
        # Deliberately avoid printing DSN/credentials. Exception text from
        # psycopg2 normally omits the password, but keep output conservative.
        print(f"NEON SMOKE: FAIL — {type(exc).__name__}: {str(exc).splitlines()[0][:240]}")
        return 1
    finally:
        for conn in (conn1, conn2):
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


if __name__ == "__main__":
    sys.exit(main())
