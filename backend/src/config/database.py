"""
Pool de conexiones a Postgres (Supabase) para uso en runtime de la app.
Distinto de tools/apply_migrations.py, que abre su propia conexión suelta
porque corre una sola vez y termina.
"""
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as pg_pool

from src.config.settings import load_settings

_pool = None


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        settings = load_settings()
        _pool = pg_pool.ThreadedConnectionPool(1, 5, settings.supabase_db_url)
    return _pool


@contextmanager
def get_connection():
    """Da una conexión del pool; hace commit si el bloque termina sin
    excepción, rollback si la hay, y siempre la devuelve al pool."""
    conn = _get_pool().getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)
