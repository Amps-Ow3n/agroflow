from contextlib import contextmanager

import psycopg2

from app.core.db_errors import raise_translated_database_error


@contextmanager
def write_transaction(conn):
    """Run one write operation as one atomic database transaction.

    The caller must perform authorization, row locking, validation,
    mutation, event/audit writes, and every other database operation
    inside this context.
    """
    try:
        conn.autocommit = False
        with conn.cursor() as tx_cursor:
            tx_cursor.execute("BEGIN")
        yield
        conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise_translated_database_error(exc)
    except Exception:
        conn.rollback()
        raise
