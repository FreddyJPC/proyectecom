"""
Acceso a datos de las solicitudes de gestión (tabla `solicitudes_gestion`, migración 020).

Regla central: UNA sola solicitud PENDIENTE por conversación (índice único parcial). La primera
intención la crea; las siguientes la completan. Así «quiere comprar» y más tarde «pedido cerrado» son
la misma fila que va ganando datos, y el dueño ve un aviso por cliente, no cinco.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.config.database import get_connection

from .tipos import tipo as tipo_de


@dataclass
class ResultadoUpsert:
    id: int
    creada: bool
    tipo: str
    tipo_anterior: Optional[str]

    @property
    def cambio_de_tipo(self) -> bool:
        return self.tipo_anterior is not None and self.tipo != self.tipo_anterior


def upsert_solicitud(
    cur,
    conversacion_id: int,
    lead_id: Optional[int],
    tipo: str,
    detalle: Optional[str],
    venta_id: Optional[int] = None,
) -> ResultadoUpsert:
    """Crea la solicitud pendiente de la conversación o completa la que ya existe. Recibe el cursor
    para poder usarse dentro de otra transacción (el cierre de una venta propia)."""
    cur.execute(
        "select id, tipo, detalle from solicitudes_gestion where conversacion_id = %s and estado = 'pendiente' for update",
        (conversacion_id,),
    )
    existente = cur.fetchone()
    if existente is None:
        cur.execute(
            """
            insert into solicitudes_gestion (conversacion_id, lead_id, venta_id, tipo, detalle)
            values (%s, %s, %s, %s, %s) returning id
            """,
            (conversacion_id, lead_id, venta_id, tipo, detalle),
        )
        return ResultadoUpsert(id=cur.fetchone()[0], creada=True, tipo=tipo, tipo_anterior=None)

    solicitud_id, tipo_actual, detalle_actual = existente
    gana_el_nuevo = tipo_de(tipo).prioridad > tipo_de(tipo_actual).prioridad
    tipo_final = tipo if gana_el_nuevo else tipo_actual
    detalle_final = detalle if (gana_el_nuevo and detalle) else detalle_actual
    cur.execute(
        """
        update solicitudes_gestion set
            tipo = %s, detalle = %s,
            lead_id = coalesce(%s, lead_id), venta_id = coalesce(%s, venta_id),
            actualizada_en = now()
        where id = %s
        """,
        (tipo_final, detalle_final, lead_id, venta_id, solicitud_id),
    )
    return ResultadoUpsert(id=solicitud_id, creada=False, tipo=tipo_final, tipo_anterior=tipo_actual)


_SELECT_LISTA = """
    select s.id, s.conversacion_id, s.tipo, s.detalle, s.estado, s.nota_atencion, s.atendida_por,
           s.creada_en, s.atendida_en,
           c.canal, c.id_externo, ct.telefono, c.estado as estado_conversacion,
           l.nombre_cliente, l.direccion, l.canton, l.provincia, l.producto_nombre, l.producto_variante,
           l.cantidad, l.metodo_pago, l.entrega_nombre, l.entrega_tipo, l.costo_envio,
           v.id as venta_id, v.total as venta_total, v.estado as venta_estado,
           v.cobrada_en as venta_cobrada_en, v.cobrada_por as venta_cobrada_por, v.nota_cobro as venta_nota_cobro,
           v.cancelada_en as venta_cancelada_en, v.cancelada_por as venta_cancelada_por,
           v.motivo_cancelacion as venta_motivo_cancelacion,
           pr.nombre as proveedor_nombre, pr.cierre as proveedor_cierre
      from solicitudes_gestion s
      join conversaciones c on c.id = s.conversacion_id
      join contactos ct on ct.id = c.contacto_id
      left join leads l on l.id = s.lead_id
      left join ventas v on v.id = s.venta_id
      left join proveedores pr on pr.id = v.proveedor_id
"""


class SolicitudGestionRepository:
    @staticmethod
    def solicitar(
        conversacion_id: int, lead_id: Optional[int], tipo: str, detalle: Optional[str], venta_id: Optional[int] = None
    ) -> ResultadoUpsert:
        with get_connection() as conn:
            with conn.cursor() as cur:
                return upsert_solicitud(cur, conversacion_id, lead_id, tipo, detalle, venta_id)

    @staticmethod
    def listar(estado: str = "pendiente", limite: int = 100) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"{_SELECT_LISTA} where s.estado = %s "
                    "order by (case when s.estado = 'pendiente' then s.creada_en end) asc nulls last, "
                    "s.atendida_en desc nulls last limit %s",
                    (estado, limite),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, fila)) for fila in cur.fetchall()]

    @staticmethod
    def obtener(solicitud_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"{_SELECT_LISTA} where s.id = %s", (solicitud_id,))
                fila = cur.fetchone()
                return dict(zip([d[0] for d in cur.description], fila)) if fila else None

    @staticmethod
    def contar_pendientes() -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from solicitudes_gestion where estado = 'pendiente'")
                return int(cur.fetchone()[0])

    @staticmethod
    def atender(solicitud_id: int, usuario: Optional[str], nota: Optional[str]) -> Optional[Dict[str, Any]]:
        """Marca la solicitud como atendida (solo si seguía pendiente). Si tenía una venta por gestionar,
        la pasa a «gestionada». Si la conversación estaba en manos del dueño («en_gestion»), vuelve a
        «activa»: ya terminó su parte y el cliente que escriba después se trata como cliente con pedido
        previo. Devuelve la solicitud, o None si no existe o ya estaba atendida."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update solicitudes_gestion set
                        estado = 'atendida', atendida_por = %s, nota_atencion = %s,
                        atendida_en = now(), actualizada_en = now()
                    where id = %s and estado = 'pendiente'
                    returning conversacion_id, venta_id
                    """,
                    (usuario, nota, solicitud_id),
                )
                fila = cur.fetchone()
                if fila is None:
                    return None
                conversacion_id, venta_id = fila
                if venta_id is not None:
                    cur.execute(
                        """
                        update ventas set estado = 'gestionada', gestionada_en = now(), gestionada_por = %s
                        where id = %s and estado = 'por_gestionar'
                        """,
                        (usuario, venta_id),
                    )
                cur.execute(
                    "update conversaciones set estado = 'activa', actualizada_en = now() "
                    "where id = %s and estado = 'en_gestion'",
                    (conversacion_id,),
                )
        return SolicitudGestionRepository.obtener(solicitud_id)
