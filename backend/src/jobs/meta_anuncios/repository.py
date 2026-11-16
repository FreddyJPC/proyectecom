"""Acceso a datos del trabajo de anuncios de Meta (migración 034). Todo SQL va con parámetros."""
from datetime import date
from typing import Any, Dict, List, Optional

from src.config.database import get_connection

_COLUMNAS_ANUNCIO = (
    "id_anuncio", "nombre", "estado", "estado_efectivo", "id_conjunto", "nombre_conjunto", "presupuesto_diario",
    "id_campana", "nombre_campana", "titulo", "texto", "miniatura_url",
)


def _filas(cur) -> List[Dict[str, Any]]:
    columnas = [d[0] for d in cur.description]
    return [dict(zip(columnas, f)) for f in cur.fetchall()]


class MetaAnunciosRepository:
    @staticmethod
    def guardar_anuncios(anuncios: List[Dict[str, Any]]) -> int:
        if not anuncios:
            return 0
        columnas = ", ".join(_COLUMNAS_ANUNCIO)
        asignaciones = ", ".join(f"{c} = excluded.{c}" for c in _COLUMNAS_ANUNCIO if c != "id_anuncio")
        with get_connection() as conn:
            with conn.cursor() as cur:
                for anuncio in anuncios:
                    cur.execute(
                        f"insert into meta_anuncios ({columnas}, leido_en) values ({', '.join(['%s'] * len(_COLUMNAS_ANUNCIO))}, now()) "
                        f"on conflict (id_anuncio) do update set {asignaciones}, leido_en = now()",
                        tuple(anuncio.get(c) for c in _COLUMNAS_ANUNCIO),
                    )
        return len(anuncios)

    @staticmethod
    def guardar_metricas(metricas: List[Dict[str, Any]]) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for m in metricas:
                    cur.execute(
                        """
                        insert into meta_metricas_diarias (id_anuncio, fecha, gasto, impresiones, clics, conversaciones, leido_en)
                        values (%s, %s, %s, %s, %s, %s, now())
                        on conflict (id_anuncio, fecha) do update set gasto = excluded.gasto, impresiones = excluded.impresiones,
                            clics = excluded.clics, conversaciones = excluded.conversaciones, leido_en = now()
                        """,
                        (m["id_anuncio"], m["fecha"], m["gasto"], m["impresiones"], m["clics"], m["conversaciones"]),
                    )
        return len(metricas)

    @staticmethod
    def anuncios_con_vinculo() -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select m.id_anuncio, m.nombre, m.estado, m.estado_efectivo, ap.producto_sku, ap.oferta_id "
                    "from meta_anuncios m left join anuncios_productos ap on ap.id_anuncio = m.id_anuncio"
                )
                return _filas(cur)

    @staticmethod
    def productos(skus: List[str]) -> Dict[str, Dict[str, Any]]:
        if not skus:
            return {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select sku, nombre, activo, estado, stock_ultimo from productos_bot where sku = any(%s)", (sorted(set(skus)),))
                return {f["sku"]: f for f in _filas(cur)}

    @staticmethod
    def metricas_por_anuncio(desde: date) -> Dict[str, Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select id_anuncio, sum(gasto) as gasto, sum(conversaciones) as conversaciones, sum(impresiones) as impresiones, "
                    "sum(clics) as clics from meta_metricas_diarias where fecha >= %s group by id_anuncio",
                    (desde,),
                )
                return {f["id_anuncio"]: f for f in _filas(cur)}

    @staticmethod
    def ventas_por_anuncio(desde: date) -> Dict[str, Dict[str, Any]]:
        """Ventas no canceladas por anuncio desde `desde`. `ganancia` es None si alguna venta no tiene costo (no se inventa)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select id_anuncio, count(*) as ventas, coalesce(sum(total), 0) as ingreso,
                           coalesce(sum(descuento_total), 0) as descuentos,
                           case when count(*) filter (where costo_productos is null) > 0 then null
                                else sum(total - costo_productos - coalesce(costo_envio_negocio, 0)) end as ganancia
                    from ventas where id_anuncio is not null and estado <> 'cancelada' and cerrada_en::date >= %s
                    group by id_anuncio
                    """,
                    (desde,),
                )
                return {f["id_anuncio"]: f for f in _filas(cur)}

    @staticmethod
    def regateo_por_producto(desde: date) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select l.producto_sku as sku, max(l.producto_nombre) as nombre, count(distinct v.id) as ventas,
                           count(distinct v.id) filter (where v.descuentos @> '[{"motivo": "regateo"}]'::jsonb) as con_regateo
                    from ventas v join ventas_lineas l on l.venta_id = v.id
                    where v.estado <> 'cancelada' and v.cerrada_en::date >= %s
                    group by l.producto_sku
                    """,
                    (desde,),
                )
                return _filas(cur)

    @staticmethod
    def registrar_alerta(regla: str, objeto: str, mensaje: str, id_anuncio: Optional[str], fecha: date) -> bool:
        """True si es nueva (no se había avisado hoy de lo mismo)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into meta_alertas (regla, objeto, fecha, id_anuncio, mensaje) values (%s, %s, %s, %s, %s) "
                    "on conflict (regla, objeto, fecha) do nothing returning id",
                    (regla, objeto, fecha, id_anuncio, mensaje),
                )
                return cur.fetchone() is not None

    @staticmethod
    def pausas_de_hoy(fecha: date) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select id_anuncio, resultado from meta_acciones where accion = 'pausar' and creada_en::date = %s", (fecha,)
                )
                return _filas(cur)

    @staticmethod
    def registrar_accion(id_anuncio: str, regla: str, motivo: str, resultado: str, detalle: Optional[str], usuario: Optional[str]) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into meta_acciones (id_anuncio, accion, regla, motivo, resultado, detalle, creada_por) "
                    "values (%s, 'pausar', %s, %s, %s, %s, %s)",
                    (id_anuncio, regla, motivo[:500], resultado, (detalle or "")[:500] or None, usuario),
                )
                if resultado == "hecho":
                    cur.execute(
                        "update meta_anuncios set estado = 'PAUSED', estado_efectivo = 'PAUSED', leido_en = now() where id_anuncio = %s",
                        (id_anuncio,),
                    )

    @staticmethod
    def resumen_del_dia(dia: date) -> Dict[str, Any]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select coalesce(sum(gasto), 0) as gasto, coalesce(sum(conversaciones), 0) as conversaciones "
                    "from meta_metricas_diarias where fecha = %s",
                    (dia,),
                )
                meta = _filas(cur)[0]
                cur.execute(
                    """
                    select count(*) as ventas, coalesce(sum(total), 0) as ingreso,
                           case when count(*) filter (where costo_productos is null) > 0 then null
                                else coalesce(sum(total - costo_productos - coalesce(costo_envio_negocio, 0)), 0) end as ganancia
                    from ventas where id_anuncio is not null and estado <> 'cancelada'
                      and (cerrada_en at time zone 'America/Guayaquil')::date = %s
                    """,
                    (dia,),
                )
                ventas = _filas(cur)[0]
        return {**meta, **ventas}


class TableroRepository:
    """Lo que muestra el panel: cada anuncio con su gasto (Meta) y lo que pasó después (nuestra base)."""

    @staticmethod
    def anuncios(desde: date) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    with metricas as (
                        select id_anuncio, sum(gasto) as gasto, sum(conversaciones) as conversaciones_meta,
                               sum(impresiones) as impresiones, sum(clics) as clics
                        from meta_metricas_diarias where fecha >= %(desde)s group by id_anuncio
                    ),
                    llegadas as (
                        select id_anuncio, count(distinct conversacion_id) as conversaciones
                        from conversacion_anuncios where id_anuncio is not null and creado_en::date >= %(desde)s group by id_anuncio
                    ),
                    vendido as (
                        select v.id_anuncio, count(*) as ventas, coalesce(sum(v.total), 0) as ingreso,
                               coalesce(sum(v.descuento_total), 0) as descuentos,
                               case when count(*) filter (where v.costo_productos is null) > 0 then null
                                    else sum(v.total - v.costo_productos - coalesce(v.costo_envio_negocio, 0)) end as ganancia,
                               count(*) filter (where p.status_id_rocketfy = 8) as entregadas,
                               count(*) filter (where p.status_id_rocketfy in (3, 9, 10)) as devueltas
                        from ventas v left join pedidos p on p.id_local = v.id_pedido_local
                        where v.id_anuncio is not null and v.estado <> 'cancelada' and v.cerrada_en::date >= %(desde)s
                        group by v.id_anuncio
                    )
                    select m.id_anuncio, m.nombre, m.estado, m.estado_efectivo, m.nombre_campana, m.nombre_conjunto,
                           m.presupuesto_diario, m.titulo, m.miniatura_url, m.leido_en,
                           ap.producto_sku, ap.oferta_id, pb.nombre as producto_nombre, o.nombre as oferta_nombre,
                           coalesce(me.gasto, 0) as gasto, coalesce(me.conversaciones_meta, 0) as conversaciones_meta,
                           coalesce(me.impresiones, 0) as impresiones, coalesce(me.clics, 0) as clics,
                           coalesce(ll.conversaciones, 0) as conversaciones,
                           coalesce(vd.ventas, 0) as ventas, coalesce(vd.ingreso, 0) as ingreso,
                           coalesce(vd.descuentos, 0) as descuentos, vd.ganancia,
                           coalesce(vd.entregadas, 0) as entregadas, coalesce(vd.devueltas, 0) as devueltas
                    from meta_anuncios m
                    left join anuncios_productos ap on ap.id_anuncio = m.id_anuncio
                    left join productos_bot pb on pb.sku = ap.producto_sku
                    left join ofertas o on o.id = ap.oferta_id
                    left join metricas me on me.id_anuncio = m.id_anuncio
                    left join llegadas ll on ll.id_anuncio = m.id_anuncio
                    left join vendido vd on vd.id_anuncio = m.id_anuncio
                    order by (m.estado_efectivo = 'ACTIVE') desc, coalesce(me.gasto, 0) desc, m.nombre
                    """,
                    {"desde": desde},
                )
                return _filas(cur)

    @staticmethod
    def ultima_lectura() -> Optional[Any]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select max(leido_en) from meta_anuncios")
                return cur.fetchone()[0]

    @staticmethod
    def alertas(limite: int = 30) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select id, regla, objeto, id_anuncio, mensaje, creada_en from meta_alertas where regla not in ('resumen') "
                    "order by creada_en desc limit %s",
                    (limite,),
                )
                return _filas(cur)

    @staticmethod
    def acciones(limite: int = 20) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select id, id_anuncio, accion, regla, motivo, resultado, detalle, creada_por, creada_en from meta_acciones "
                    "order by creada_en desc limit %s",
                    (limite,),
                )
                return _filas(cur)
