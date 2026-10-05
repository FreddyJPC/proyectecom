import json
from typing import Optional

from psycopg2.extras import Json

from src.config.database import get_connection


class WebhookRepository:
    @staticmethod
    def guardar_evento(
        id_rocketfy: int,
        status_id: int,
        event_date,
        shopify_order_id,
        payload: dict,
    ) -> bool:
        """Inserta el evento crudo de forma idempotente por
        (id_rocketfy, status_id, event_date) — índice único de
        002_webhook_events_idempotencia.sql. Devuelve True si era nuevo,
        False si ya existía (duplicado — no se reprocesa, ver guía del
        proveedor sección 4.7)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into webhook_events
                        (id_rocketfy, status_id, event_date, shopify_order_id, payload)
                    values (%s, %s, %s, %s, %s)
                    on conflict (id_rocketfy, status_id, event_date) do nothing
                    """,
                    (
                        id_rocketfy,
                        status_id,
                        event_date,
                        shopify_order_id,
                        Json(payload, dumps=lambda o: json.dumps(o, default=str)),
                    ),
                )
                return cur.rowcount == 1

    @staticmethod
    def actualizar_estado_pedido(id_rocketfy: int, status_id: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update pedidos set status_id_rocketfy = %s, actualizado_en = now() where id_rocketfy = %s",
                    (status_id, id_rocketfy),
                )

    @staticmethod
    def marcar_procesado(id_rocketfy: int, status_id: int, event_date) -> None:
        """Se llama tras aplicar el evento al pedido local. Deja rastro
        consultable de que ese evento ya fue atendido -- lo necesita el
        futuro dashboard (directriz 17: trazabilidad total visible)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update webhook_events set procesado = true, procesado_en = now()
                    where id_rocketfy = %s and status_id = %s and event_date = %s
                    """,
                    (id_rocketfy, status_id, event_date),
                )

    @staticmethod
    def obtener_datos_pedido(id_rocketfy: int) -> Optional[dict]:
        """Datos del cliente (teléfono, nombre) no vienen en el webhook —
        hay que cruzarlos con nuestro propio pedido (ver guía sección 2)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select payload_creacion from pedidos where id_rocketfy = %s", (id_rocketfy,))
                row = cur.fetchone()
                return row[0] if row else None
