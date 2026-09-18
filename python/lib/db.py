"""Database access layer for the support tool. Uses pg8000 (pure Python,
no C extension) so this CLI runs on any host Python without a build step."""
import logging

import pg8000.dbapi as pg8000

logger = logging.getLogger("support_tool.db")


class DBConnectionError(Exception):
    pass


def get_connection(cfg, timeout_seconds=5):
    try:
        return pg8000.connect(
            host=cfg.db_host,
            port=cfg.db_port,
            database=cfg.db_name,
            user=cfg.db_user,
            password=cfg.db_password,
            timeout=timeout_seconds,
        )
    except Exception as e:
        logger.error("Failed to connect to database at %s:%s: %s", cfg.db_host, cfg.db_port, e)
        raise DBConnectionError(str(e)) from e


def _rows_as_dicts(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def fetch_transaction(conn, transaction_ref):
    cur = conn.cursor()
    cur.execute(
        "SELECT t.id, t.transaction_ref, t.amount, t.status, t.created_at, "
        "t.completed_at, t.failure_code, c.customer_ref, c.name AS customer_name "
        "FROM transactions t JOIN customers c ON c.id = t.customer_id "
        "WHERE t.transaction_ref = %s;",
        (transaction_ref,),
    )
    rows = _rows_as_dicts(cur)
    return rows[0] if rows else None


def fetch_callbacks(conn, transaction_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT attempt_no, http_status, callback_status, attempted_at "
        "FROM callbacks WHERE transaction_id = %s ORDER BY attempt_no;",
        (transaction_id,),
    )
    return _rows_as_dicts(cur)


def fetch_stuck_or_failed(conn, stuck_minutes):
    cur = conn.cursor()
    cur.execute(
        "SELECT transaction_ref, status, created_at, failure_code FROM transactions "
        "WHERE (status = 'PROCESSING' AND created_at < now() - (%s || ' minutes')::interval) "
        "   OR (status = 'FAILED' AND created_at > now() - interval '24 hours') "
        "ORDER BY created_at DESC LIMIT 100;",
        (stuck_minutes,),
    )
    return _rows_as_dicts(cur)
