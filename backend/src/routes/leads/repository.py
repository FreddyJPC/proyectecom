"""
Acceso a datos de la pantalla de Leads (docs/PLAN_LEADS_CRM.md): la lista con sus filtros, los números del resumen, el detalle
con su historial y la ficha del contacto (visión 360 y valor del cliente).

Las ESCRITURAS de temperatura y de «no contactar» viven en `sql.py` (a nivel de cursor, para poder ir dentro de otras
transacciones); aquí cada método abre su propia conexión.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.config.database import get_connection

from .sql import cerrar_leads_abiertos_del_contacto, fijar_temperatura, marcar_no_contactar  # noqa: F401  (para el servicio)
from .temperaturas import ABIERTAS, TEMPERATURAS

# Cómo se ordena la lista (lista blanca: nunca se arma SQL con lo que llega de la API).
_ORDENES = {
    "actividad": "l.actualizado_en desc, l.id desc",
    "valor": "l.total desc nulls last, l.id desc",
    "temperatura": "array_position(array['caliente','tibio','frio','perdido','ganado'], l.temperatura), l.actualizado_en desc, l.id desc",
    "antiguedad": "l.creado_en asc, l.id asc",
}
ORDENES_VALIDOS = tuple(_ORDENES)

_DESDE = """
    from leads l
    join conversaciones c on c.id = l.conversacion_id
    join contactos ct on ct.id = l.contacto_id
    left join lateral (
        select rol, contenido, creado_en from mensajes
        where conversacion_id = l.conversacion_id order by creado_en desc, id desc limit 1
    ) m on true
    left join lateral (
        select max(creado_en) as ultimo from mensajes where conversacion_id = l.conversacion_id and rol = 'cliente'
    ) mc on true
    left join lateral (
        select titulo from conversacion_anuncios where id_anuncio = l.id_anuncio order by creado_en desc, id desc limit 1
    ) a on true
    left join lateral (
        select tipo, enviado_en from seguimientos where lead_id = l.id and estado = 'enviado' order by id desc limit 1
    ) sg on true
"""

_COLUMNAS = """
    l.id, l.contacto_id, l.conversacion_id, c.canal, c.id_externo, c.estado as estado_conversacion,
    ct.telefono, ct.nombre as contacto_nombre, c.nombre_perfil, l.nombre_cliente,
    l.producto_sku, l.producto_nombre, l.producto_variante, l.cantidad, l.total,
    l.estado as etapa, l.temperatura, l.temperatura_motivo, l.temperatura_origen, l.temperatura_en,
    l.temperatura_fijada_hasta, l.motivo_perdida, l.origen, l.id_anuncio, a.titulo as titulo_anuncio,
    l.creado_en, l.actualizado_en, l.cerrado_en,
    ct.no_contactar, ct.no_contactar_motivo,
    m.rol as ultimo_rol, m.contenido as ultimo_contenido, m.creado_en as ultimo_en, mc.ultimo as ultimo_cliente_en,
    sg.tipo as seguimiento_tipo, sg.enviado_en as seguimiento_en
"""


def _filas(cur) -> List[Dict[str, Any]]:
    columnas = [d[0] for d in cur.description]
    return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


def _fila(cur) -> Optional[Dict[str, Any]]:
    fila = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], fila)) if fila else None


class LeadsRepository:
    @staticmethod
    def listar(
        temperaturas: Optional[List[str]] = None,
        etapa: Optional[str] = None,
        origen: Optional[str] = None,
        canal: Optional[str] = None,
        producto_sku: Optional[str] = None,
        q: Optional[str] = None,
        no_contactar: Optional[bool] = None,
        sin_respuesta_dias: Optional[int] = None,
        orden: str = "actividad",
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        condiciones: List[str] = []
        params: Dict[str, Any] = {}
        if temperaturas:
            condiciones.append("l.temperatura = any(%(temperaturas)s)")
            params["temperaturas"] = list(temperaturas)
        if etapa:
            condiciones.append("l.estado = %(etapa)s")
            params["etapa"] = etapa
        if origen:
            condiciones.append("l.origen = %(origen)s")
            params["origen"] = origen
        if canal:
            condiciones.append("c.canal = %(canal)s")
            params["canal"] = canal
        if producto_sku:
            condiciones.append("l.producto_sku = %(producto_sku)s")
            params["producto_sku"] = producto_sku
        if no_contactar is not None:
            condiciones.append("ct.no_contactar = %(no_contactar)s")
            params["no_contactar"] = no_contactar
        if sin_respuesta_dias:
            condiciones.append("coalesce(mc.ultimo, l.creado_en) <= now() - make_interval(days => %(sin_resp)s)")
            params["sin_resp"] = sin_respuesta_dias
        if q:
            condiciones.append(
                "(ct.telefono ilike %(q)s or c.id_externo ilike %(q)s or lower(ct.nombre) like lower(%(q)s) "
                "or lower(c.nombre_perfil) like lower(%(q)s) or lower(l.nombre_cliente) like lower(%(q)s) "
                "or lower(l.producto_nombre) like lower(%(q)s))"
            )
            params["q"] = f"%{q}%"
        donde = f"where {' and '.join(condiciones)}" if condiciones else ""
        params.update(limite=page_size, desplazamiento=(page - 1) * page_size)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select count(*) {_DESDE} {donde}", params)
                total = cur.fetchone()[0]
                cur.execute(
                    f"select {_COLUMNAS} {_DESDE} {donde} order by {_ORDENES.get(orden, _ORDENES['actividad'])} "
                    "limit %(limite)s offset %(desplazamiento)s",
                    params,
                )
                items = _filas(cur)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def obtener(lead_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} {_DESDE} where l.id = %s", (lead_id,))
                return _fila(cur)

    @staticmethod
    def historial(lead_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select id, de, a, origen, motivo, usuario, creado_en from lead_historial "
                    "where lead_id = %s order by creado_en desc, id desc",
                    (lead_id,),
                )
                return _filas(cur)

    @staticmethod
    def seguimientos(lead_id: int) -> List[Dict[str, Any]]:
        """Los mensajes de seguimiento automático de este lead (los fallidos también: el dueño debe saber que se intentó)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select id, tipo, estado, contenido, plantilla, error, creado_en, enviado_en from seguimientos "
                    "where lead_id = %s order by creado_en desc, id desc",
                    (lead_id,),
                )
                return _filas(cur)

    @staticmethod
    def resumen(desde: Optional[datetime]) -> Dict[str, Any]:
        """Los números de arriba de la pantalla. Las cuentas por temperatura son de AHORA (cuántos leads hay en cada una); las
        de ganados, perdidos y nuevos son del periodo (`desde`, None = todo el tiempo)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        count(*) filter (where temperatura = 'caliente') as calientes,
                        count(*) filter (where temperatura = 'tibio') as tibios,
                        count(*) filter (where temperatura = 'frio') as frios,
                        coalesce(sum(total) filter (where temperatura = any(%(abiertas)s)), 0) as valor_en_juego,
                        count(*) filter (where temperatura = 'ganado' and (%(desde)s::timestamptz is null or cerrado_en >= %(desde)s)) as ganados,
                        coalesce(sum(total) filter (where temperatura = 'ganado' and (%(desde)s::timestamptz is null or cerrado_en >= %(desde)s)), 0) as ingresos_ganados,
                        count(*) filter (where temperatura = 'perdido' and (%(desde)s::timestamptz is null or cerrado_en >= %(desde)s)) as perdidos,
                        count(*) filter (where %(desde)s::timestamptz is null or creado_en >= %(desde)s) as nuevos
                    from leads
                    """,
                    {"abiertas": list(ABIERTAS), "desde": desde},
                )
                base = _fila(cur)
                cur.execute("select count(*) from contactos where no_contactar")
                base["no_contactar"] = cur.fetchone()[0]
                cur.execute(
                    """
                    select coalesce(motivo_perdida, 'otro') as motivo, count(*) as leads from leads
                    where temperatura = 'perdido' and (%(desde)s::timestamptz is null or cerrado_en >= %(desde)s)
                    group by 1 order by 2 desc
                    """,
                    {"desde": desde},
                )
                base["motivos_de_perdida"] = _filas(cur)
        return base

    @staticmethod
    def ficha_de_contacto(contacto_id: int) -> Optional[Dict[str, Any]]:
        """Visión 360 del contacto: quién es, por qué canales habla, todos sus leads, cuánto ha comprado (valor del cliente)
        y cuándo llegó por anuncio."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select id, nombre, telefono, no_contactar, no_contactar_motivo, no_contactar_en, no_contactar_por, "
                    "creado_en from contactos where id = %s",
                    (contacto_id,),
                )
                contacto = _fila(cur)
                if contacto is None:
                    return None
                cur.execute(
                    "select id, canal, id_externo, estado, creada_en from conversaciones where contacto_id = %s order by creada_en",
                    (contacto_id,),
                )
                contacto["conversaciones"] = _filas(cur)
                cur.execute(
                    "select id, conversacion_id, producto_nombre, temperatura, estado as etapa, total, origen, creado_en, cerrado_en "
                    "from leads where contacto_id = %s order by creado_en desc, id desc limit 20",
                    (contacto_id,),
                )
                contacto["leads"] = _filas(cur)
                cur.execute(
                    """
                    select count(*) filter (where estado <> 'cancelada') as compras,
                           coalesce(sum(total) filter (where estado <> 'cancelada'), 0) as total_gastado,
                           coalesce(sum(total - costo_productos - coalesce(costo_envio_negocio, 0))
                                    filter (where estado <> 'cancelada' and costo_productos is not null), 0) as ganancia,
                           count(*) filter (where estado <> 'cancelada' and costo_productos is null) as compras_sin_costo,
                           max(cerrada_en) filter (where estado <> 'cancelada') as ultima_compra
                    from ventas where contacto_id = %s
                    """,
                    (contacto_id,),
                )
                contacto["compras"] = _fila(cur)
                cur.execute(
                    """
                    select count(*) as llegadas, min(a.creado_en) as primera, max(a.creado_en) as ultima
                    from conversacion_anuncios a join conversaciones c on c.id = a.conversacion_id
                    where c.contacto_id = %s
                    """,
                    (contacto_id,),
                )
                contacto["anuncios"] = _fila(cur)
                cur.execute(
                    """
                    select a.id_anuncio, a.titulo from conversacion_anuncios a join conversaciones c on c.id = a.conversacion_id
                    where c.contacto_id = %s order by a.creado_en asc, a.id asc limit 1
                    """,
                    (contacto_id,),
                )
                contacto["primer_anuncio"] = _fila(cur)
        return contacto

    @staticmethod
    def candidatos_a_enfriar() -> List[Dict[str, Any]]:
        """Leads abiertos que el enfriamiento automático puede tocar: sin temperatura fijada por el dueño y cuya conversación
        no está en manos del dueño (si la pelota está en su cancha, el silencio no es culpa del cliente)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select l.id, l.temperatura, coalesce(mc.ultimo, l.creado_en) as ultimo_cliente_en
                    from leads l
                    join conversaciones c on c.id = l.conversacion_id
                    left join lateral (
                        select max(creado_en) as ultimo from mensajes where conversacion_id = l.conversacion_id and rol = 'cliente'
                    ) mc on true
                    where l.temperatura = any(%s)
                      and (l.temperatura_fijada_hasta is null or l.temperatura_fijada_hasta <= now())
                      and c.estado not in ('escalada', 'en_gestion')
                    """,
                    (list(ABIERTAS),),
                )
                return _filas(cur)

    # ---- escrituras (cada una en su propia transacción) -------------------------------------------------------
    @staticmethod
    def fijar_temperatura(lead_id: int, nueva: str, origen: str, **kwargs) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                return fijar_temperatura(cur, lead_id, nueva, origen, **kwargs)

    @staticmethod
    def marcar_no_contactar(contacto_id: int, valor: bool, motivo: Optional[str], por: str, usuario: Optional[str]) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                return marcar_no_contactar(cur, contacto_id, valor, motivo, por, usuario)

    @staticmethod
    def contacto_de_lead(lead_id: int) -> Optional[int]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select contacto_id from leads where id = %s", (lead_id,))
                fila = cur.fetchone()
                return fila[0] if fila else None


__all__ = ["LeadsRepository", "ORDENES_VALIDOS", "TEMPERATURAS"]
