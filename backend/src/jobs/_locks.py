"""
Coordinación de jobs en background sobre la tabla job_locks — mismo patrón
que WEBSERVICES/src/cronTask/despacho_dia_actual.py (st_cron_lock).
Compartido entre reconciliacion/ y stock_watcher/ para no duplicar el SQL.
"""
import os

from src.config.database import get_connection

TIMEOUT_MINUTOS_LOCK_DEFAULT = 30


def acquire_lock(job_name: str, timeout_minutos: int = TIMEOUT_MINUTOS_LOCK_DEFAULT) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "delete from job_locks where job_name = %s and locked_at < now() - (%s || ' minutes')::interval",
                (job_name, timeout_minutos),
            )
            cur.execute(
                """
                insert into job_locks (job_name, instancia)
                values (%s, %s)
                on conflict (job_name) do nothing
                """,
                (job_name, str(os.getpid())),
            )
            return cur.rowcount == 1


def release_lock(job_name: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from job_locks where job_name = %s", (job_name,))
