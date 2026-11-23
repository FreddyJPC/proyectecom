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

    # ------------------------------------------------------------------
    # Pedidos hechos A MANO en el panel de Rocketfy (pendiente #89, 2026-11-23)
    # ------------------------------------------------------------------
    @staticmethod
    def obtener_por_id_rocketfy(id_rocketfy: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from pedidos where id_rocketfy = %s", (id_rocketfy,))
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def insertar_externo(id_local: int, id_rocketfy: int, estado_local: str, status_id: Optional[int], payload: dict) -> bool:
        """Guarda un pedido que el dueño creó en el panel de Rocketfy (no lo creó este sistema). Devuelve False si ese id_local
        o ese id_rocketfy ya existían (no se pisa nada): el llamador prueba otro id_local o avisa que ya estaba registrado."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into pedidos (id_local, id_rocketfy, estado_local, status_id_rocketfy, payload_creacion,
                                         confirmado_en, actualizado_en)
                    values (%s, %s, %s, %s, %s, case when %s = 'confirmado' then now() end, now())
                    on conflict do nothing
                    """,
                    (id_local, id_rocketfy, estado_local, status_id,
                     Json(payload, dumps=lambda o: json.dumps(o, default=str)), estado_local),
                )
                return cur.rowcount == 1

    @staticmethod
    def ultimo_status_avisado(id_rocketfy: int) -> Optional[int]:
        """El último estado que Rocketfy avisó por el webhook para ese pedido (los avisos se guardan aunque el pedido no sea
        nuestro todavía)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select status_id from webhook_events where id_rocketfy = %s order by recibido_en desc, id desc limit 1",
                    (id_rocketfy,),
                )
                row = cur.fetchone()
                return row[0] if row else None

    @staticmethod
    def sin_vincular(dias: int = 14, limite: int = 20) -> list:
        """Pedidos de los que Rocketfy nos avisó por el webhook pero que no están en `pedidos`: los que el dueño creó a mano
        en su panel. El más reciente primero, con el último aviso de cada uno."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select w.id_rocketfy, max(w.recibido_en) as ultimo_aviso,
                           (array_agg(w.payload order by w.recibido_en desc, w.id desc))[1] as payload
                    from webhook_events w
                    where not exists (select 1 from pedidos p where p.id_rocketfy = w.id_rocketfy)
                      and w.recibido_en > now() - make_interval(days => %s)
                    group by w.id_rocketfy
                    order by ultimo_aviso desc
                    limit %s
                    """,
                    (dias, limite),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, fila)) for fila in cur.fetchall()]
