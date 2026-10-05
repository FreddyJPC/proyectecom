import json
from decimal import Decimal
from typing import List, Optional

from psycopg2.extras import Json

from src.config.database import get_connection
from src.jobs._locks import acquire_lock, release_lock


class StockWatcherRepository:
    @staticmethod
    def acquire_lock(job_name: str) -> bool:
        return acquire_lock(job_name)

    @staticmethod
    def release_lock(job_name: str) -> None:
        release_lock(job_name)

    @staticmethod
    def listar_activos() -> List[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select sku, umbral_stock_minimo from skus_monitoreados where activo = true order by sku"
                )
                return [{"sku": row[0], "umbral_stock_minimo": row[1]} for row in cur.fetchall()]

    @staticmethod
    def obtener_ultimo_snapshot(sku: str) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select stock, price, capturado_en from stock_snapshots
                    where sku = %s order by capturado_en desc limit 1
                    """,
                    (sku,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return {"stock": row[0], "price": row[1], "capturado_en": row[2]}

    @staticmethod
    def guardar_snapshot(sku: str, stock: int, price: Decimal) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into stock_snapshots (sku, stock, price) values (%s, %s, %s)",
                    (sku, stock, price),
                )

    @staticmethod
    def guardar_alerta(sku: str, tipo: str, detalle: dict) -> None:
        """Fase 2 - Etapa 3: antes esto solo se logueaba (ver
        StockWatcherService._revisar_uno) -- ahora queda como un evento
        consultable, igual que webhook_events con los avisos de Rocketfy."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into alertas_stock (sku, tipo, detalle) values (%s, %s, %s)",
                    (sku, tipo, Json(detalle, dumps=lambda o: json.dumps(o, default=str))),
                )
