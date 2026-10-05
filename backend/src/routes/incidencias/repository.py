from typing import Optional

from src.config.database import get_connection
from src.routes.webhooks.services import EVENTOS_PARA_EQUIPO

_STATUS_IDS_INCIDENCIA = tuple(int(s) for s in EVENTOS_PARA_EQUIPO)

_COLUMNAS_EVENTO = """
    id, id_rocketfy, shopify_order_id, status_id, event_date, recibido_en,
    payload ->> 'status_name' as status_name,
    payload ->> 'details' as details,
    payload ->> 'tracking_code' as tracking_code,
    payload ->> 'tracking_url' as tracking_url,
    payload ->> 'shipping_company' as shipping_company
"""


class IncidenciasRepository:
    @staticmethod
    def listar_eventos_webhook(solo_incidencias: bool = True, limit: int = 20, offset: int = 0) -> list:
        query = f"select {_COLUMNAS_EVENTO} from webhook_events"
        params: list = []
        if solo_incidencias:
            query += " where status_id = any(%s)"
            params.append(list(_STATUS_IDS_INCIDENCIA))
        query += " order by coalesce(event_date, recibido_en) desc limit %s offset %s"
        params.extend([limit, offset])
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in rows]

    @staticmethod
    def contar_eventos_webhook(solo_incidencias: bool = True) -> int:
        query = "select count(*) from webhook_events"
        params: list = []
        if solo_incidencias:
            query += " where status_id = any(%s)"
            params.append(list(_STATUS_IDS_INCIDENCIA))
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()[0]

    @staticmethod
    def listar_alertas_stock(sku: Optional[str] = None, limit: int = 20, offset: int = 0) -> list:
        query = "select id, sku, tipo, detalle, creado_en from alertas_stock"
        params: list = []
        if sku:
            query += " where sku = %s"
            params.append(sku)
        query += " order by creado_en desc limit %s offset %s"
        params.extend([limit, offset])
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in rows]

    @staticmethod
    def contar_alertas_stock(sku: Optional[str] = None) -> int:
        query = "select count(*) from alertas_stock"
        params: list = []
        if sku:
            query += " where sku = %s"
            params.append(sku)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()[0]
