import json
from typing import Optional

from psycopg2.extras import Json

from src.config.database import get_connection

_COLUMNAS = (
    "id_local, id_rocketfy, estado_local, status_id_rocketfy, "
    "payload_creacion, mensaje_error, creado_en, confirmado_en, actualizado_en"
)


class PedidoRepository:
    @staticmethod
    def obtener(id_local: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from pedidos where id_local = %s", (id_local,))
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def upsert_pendiente(id_local: int, payload_creacion: dict) -> None:
        """Crea el registro en pendiente_creacion, o lo reinicia si el
        intento anterior falló de forma NO ambigua (estado_local='error').
        El llamador (PedidoService) es responsable de no invocar esto sobre
        un pedido en 'pendiente_creacion' o 'confirmado'."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into pedidos (id_local, estado_local, payload_creacion, mensaje_error, actualizado_en)
                    values (%s, 'pendiente_creacion', %s, null, now())
                    on conflict (id_local) do update set
                        estado_local = 'pendiente_creacion',
                        payload_creacion = excluded.payload_creacion,
                        mensaje_error = null,
                        actualizado_en = now()
                    """,
                    (id_local, Json(payload_creacion, dumps=lambda o: json.dumps(o, default=str))),
                )

    @staticmethod
    def marcar_creado(id_local: int, id_rocketfy: int, estado_local: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update pedidos
                    set id_rocketfy = %s, estado_local = %s, actualizado_en = now()
                    where id_local = %s
                    """,
                    (id_rocketfy, estado_local, id_local),
                )

    @staticmethod
    def marcar_error_creacion(id_local: int, mensaje: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update pedidos
                    set estado_local = 'error', mensaje_error = %s, actualizado_en = now()
                    where id_local = %s
                    """,
                    (mensaje, id_local),
                )

    @staticmethod
    def marcar_confirmado(id_local: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update pedidos
                    set estado_local = 'confirmado', confirmado_en = now(),
                        mensaje_error = null, actualizado_en = now()
                    where id_local = %s
                    """,
                    (id_local,),
                )

    @staticmethod
    def marcar_error_confirmacion(id_local: int, mensaje: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update pedidos set mensaje_error = %s, actualizado_en = now() where id_local = %s",
                    (mensaje, id_local),
                )

    @staticmethod
    def actualizar_datos_contacto(id_local: int, campos: dict) -> None:
        """Mergea (no reemplaza) las claves cambiadas dentro de
        payload_creacion — mantiene fresco el teléfono/dirección que usa
        el webhook para notificar (Etapa 4), sin perder el resto del
        payload original."""
        if not campos:
            return
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update pedidos
                    set payload_creacion = payload_creacion || %s::jsonb, actualizado_en = now()
                    where id_local = %s
                    """,
                    (Json(campos, dumps=lambda o: json.dumps(o, default=str)), id_local),
                )

    @staticmethod
    def listar(estado: Optional[str] = None, limit: int = 20, offset: int = 0) -> list:
        query = f"select {_COLUMNAS} from pedidos"
        params: list = []
        if estado:
            query += " where estado_local = %s"
            params.append(estado)
        query += " order by creado_en desc nulls last limit %s offset %s"
        params.extend([limit, offset])
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in rows]

    @staticmethod
    def contar(estado: Optional[str] = None) -> int:
        query = "select count(*) from pedidos"
        params: list = []
        if estado:
            query += " where estado_local = %s"
            params.append(estado)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()[0]

    @staticmethod
    def marcar_rechazado(id_local: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update pedidos set estado_local = 'rechazado', actualizado_en = now() where id_local = %s",
                    (id_local,),
                )
