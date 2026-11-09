"""
Acceso a datos de anuncios (Click-to-WhatsApp): el historial de llegadas, el vínculo anuncio→producto y los
números de rendimiento (conversaciones y ventas por anuncio y por origen).

Una sola `with get_connection()` es UNA transacción: lo que debe quedar junto (la llegada y el cambio en la
conversación) se hace dentro del mismo bloque.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json

from src.config.database import get_connection

_COLUMNAS_LLEGADA = (
    "id, conversacion_id, mensaje_id, wamid, id_anuncio, tipo_origen, url_anuncio, titulo, texto, tipo_media, "
    "imagen_url, video_url, miniatura_url, ctwa_clid, mensaje_bienvenida, creado_en"
)


def _filas(cur) -> List[Dict[str, Any]]:
    columnas = [d[0] for d in cur.description]
    return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


def _fila(cur) -> Optional[Dict[str, Any]]:
    fila = cur.fetchone()
    if fila is None:
        return None
    return dict(zip([d[0] for d in cur.description], fila))


class AnuncioRepository:
    # ------------------------------------------------------------------ llegadas

    @staticmethod
    def registrar_llegada(
        conversacion_id: int,
        mensaje_id: Optional[int],
        wamid: Optional[str],
        datos: Dict[str, Optional[str]],
        referral: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Guarda la llegada por anuncio y actualiza la conversación (origen, anuncio y clic MÁS RECIENTES) en una sola
        transacción. Devuelve `{"registrada", "anuncio_nuevo"}`:
        - `registrada` es False si ese mensaje ya estaba registrado (Meta reenvía webhooks).
        - `anuncio_nuevo` es True si es la primera vez que se ve ese anuncio Y no está vinculado a un producto."""
        id_anuncio = datos.get("id_anuncio")
        with get_connection() as conn:
            with conn.cursor() as cur:
                anuncio_nuevo = False
                if id_anuncio:
                    cur.execute(
                        "select exists(select 1 from conversacion_anuncios where id_anuncio = %s) as visto, "
                        "exists(select 1 from anuncios_productos where id_anuncio = %s) as vinculado",
                        (id_anuncio, id_anuncio),
                    )
                    visto, vinculado = cur.fetchone()
                    anuncio_nuevo = not visto and not vinculado

                cur.execute(
                    """
                    insert into conversacion_anuncios (
                        conversacion_id, mensaje_id, wamid, id_anuncio, tipo_origen, url_anuncio, titulo, texto,
                        tipo_media, imagen_url, video_url, miniatura_url, ctwa_clid, mensaje_bienvenida, referral
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (wamid) where wamid is not null do nothing
                    returning id
                    """,
                    (
                        conversacion_id, mensaje_id, wamid, id_anuncio, datos.get("tipo_origen"), datos.get("url_anuncio"),
                        datos.get("titulo"), datos.get("texto"), datos.get("tipo_media"), datos.get("imagen_url"),
                        datos.get("video_url"), datos.get("miniatura_url"), datos.get("ctwa_clid"),
                        datos.get("mensaje_bienvenida"), Json(referral),
                    ),
                )
                if cur.fetchone() is None:
                    return {"registrada": False, "anuncio_nuevo": False}

                # El cliente llegó (de nuevo) por un anuncio: el origen pasa a «anuncio» y el anuncio y el clic vigentes son los
                # de esta llegada (el que más probablemente terminó en la compra). Si Meta no mandó alguno, se conserva el anterior.
                cur.execute(
                    """
                    update conversaciones set
                        origen = 'anuncio',
                        id_anuncio = coalesce(%s, id_anuncio),
                        ctwa_clid = coalesce(%s, ctwa_clid)
                    where id = %s
                    """,
                    (id_anuncio, datos.get("ctwa_clid"), conversacion_id),
                )
                return {"registrada": True, "anuncio_nuevo": anuncio_nuevo}

    @staticmethod
    def llegadas_de(conversacion_id: int) -> List[Dict[str, Any]]:
        """Las llegadas por anuncio de una conversación, la más reciente primero."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select {_COLUMNAS_LLEGADA} from conversacion_anuncios where conversacion_id = %s "
                    "order by creado_en desc, id desc",
                    (conversacion_id,),
                )
                return _filas(cur)

    # ------------------------------------------------------------------ vínculo anuncio -> producto

    @staticmethod
    def vinculo_de(id_anuncio: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select ap.id_anuncio, ap.producto_sku, ap.nombre, p.nombre as producto_nombre "
                    "from anuncios_productos ap join productos_bot p on p.sku = ap.producto_sku "
                    "where ap.id_anuncio = %s",
                    (id_anuncio,),
                )
                return _fila(cur)

    @staticmethod
    def vincular(id_anuncio: str, producto_sku: str, nombre: Optional[str]) -> None:
        """Crea el vínculo o cambia el producto de uno existente. El nombre solo se reemplaza si llega uno."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into anuncios_productos (id_anuncio, producto_sku, nombre)
                    values (%s, %s, %s)
                    on conflict (id_anuncio) do update set
                        producto_sku = excluded.producto_sku,
                        nombre = coalesce(excluded.nombre, anuncios_productos.nombre),
                        actualizado_en = now()
                    """,
                    (id_anuncio, producto_sku, nombre),
                )

    @staticmethod
    def desvincular(id_anuncio: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from anuncios_productos where id_anuncio = %s", (id_anuncio,))
                return cur.rowcount > 0

    # ------------------------------------------------------------------ rendimiento

    @staticmethod
    def listar_anuncios(desde: Optional[datetime]) -> List[Dict[str, Any]]:
        """Cada anuncio visto (o vinculado de antemano) con lo último que dijo Meta de él, su producto y su rendimiento.
        `desde` limita las cifras de conversaciones y ventas a ese periodo (None = todo)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    with ids as (
                        select id_anuncio from conversacion_anuncios where id_anuncio is not null
                        union
                        select id_anuncio from anuncios_productos
                    ),
                    ultima as (
                        select distinct on (id_anuncio)
                            id_anuncio, titulo, texto, url_anuncio, tipo_origen, tipo_media, imagen_url, miniatura_url,
                            creado_en as ultima_llegada
                        from conversacion_anuncios where id_anuncio is not null
                        order by id_anuncio, creado_en desc, id desc
                    ),
                    primera as (
                        select id_anuncio, min(creado_en) as primera_llegada
                        from conversacion_anuncios where id_anuncio is not null group by id_anuncio
                    ),
                    toques as (
                        select id_anuncio, count(*) as llegadas, count(distinct conversacion_id) as conversaciones
                        from conversacion_anuncios
                        where id_anuncio is not null and (%(desde)s::timestamptz is null or creado_en >= %(desde)s)
                        group by id_anuncio
                    ),
                    vendido as (
                        select id_anuncio,
                               count(*) as ventas,
                               coalesce(sum(total), 0) as ingresos,
                               coalesce(sum(total - costo_productos - coalesce(costo_envio_negocio, 0))
                                        filter (where costo_productos is not null), 0) as ganancia,
                               count(*) filter (where costo_productos is null) as ventas_sin_costo
                        from ventas
                        where id_anuncio is not null and estado <> 'cancelada'
                          and (%(desde)s::timestamptz is null or cerrada_en >= %(desde)s)
                        group by id_anuncio
                    )
                    select i.id_anuncio, ap.producto_sku, ap.nombre as nombre_vinculo, p.nombre as producto_nombre,
                           u.titulo, u.texto, u.url_anuncio, u.tipo_origen, u.tipo_media, u.imagen_url, u.miniatura_url,
                           u.ultima_llegada, pr.primera_llegada,
                           coalesce(t.llegadas, 0) as llegadas, coalesce(t.conversaciones, 0) as conversaciones,
                           coalesce(v.ventas, 0) as ventas, coalesce(v.ingresos, 0) as ingresos,
                           coalesce(v.ganancia, 0) as ganancia, coalesce(v.ventas_sin_costo, 0) as ventas_sin_costo
                    from ids i
                    left join anuncios_productos ap on ap.id_anuncio = i.id_anuncio
                    left join productos_bot p on p.sku = ap.producto_sku
                    left join ultima u on u.id_anuncio = i.id_anuncio
                    left join primera pr on pr.id_anuncio = i.id_anuncio
                    left join toques t on t.id_anuncio = i.id_anuncio
                    left join vendido v on v.id_anuncio = i.id_anuncio
                    order by (ap.producto_sku is null) desc, coalesce(u.ultima_llegada, ap.creado_en) desc
                    """,
                    {"desde": desde},
                )
                return _filas(cur)

    @staticmethod
    def resumen_por_origen(desde: Optional[datetime]) -> Dict[str, Any]:
        """Anuncio frente a directo: cuántas conversaciones nuevas y cuántas ventas (y cuánto dinero) trajo cada origen.

        «Anuncio» = conversaciones que llegaron por un anuncio en el periodo; «Directo» = conversaciones creadas en el
        periodo que nunca llegaron por un anuncio. Las ventas se separan por el origen que tenía la conversación al
        cerrarse (`ventas.origen`: «anuncio» es anuncio; cualquier otro valor cuenta como directo). No cuenta las canceladas."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        (select count(distinct conversacion_id) from conversacion_anuncios
                          where %(desde)s::timestamptz is null or creado_en >= %(desde)s) as conv_anuncio,
                        (select count(*) from conversaciones c
                          where (%(desde)s::timestamptz is null or c.creada_en >= %(desde)s)
                            and not exists (select 1 from conversacion_anuncios a where a.conversacion_id = c.id)) as conv_directo,
                        (select count(*) from conversacion_anuncios
                          where %(desde)s::timestamptz is null or creado_en >= %(desde)s) as llegadas,
                        (select count(distinct id_anuncio) from conversacion_anuncios
                          where id_anuncio is not null and (%(desde)s::timestamptz is null or creado_en >= %(desde)s)) as anuncios_activos,
                        (select count(distinct a.id_anuncio) from conversacion_anuncios a
                          where a.id_anuncio is not null
                            and not exists (select 1 from anuncios_productos ap where ap.id_anuncio = a.id_anuncio)) as sin_vincular
                    """,
                    {"desde": desde},
                )
                base = _fila(cur)
                cur.execute(
                    """
                    select (origen = 'anuncio') as es_anuncio,
                           count(*) as ventas,
                           coalesce(sum(total), 0) as ingresos,
                           coalesce(sum(total - costo_productos - coalesce(costo_envio_negocio, 0))
                                    filter (where costo_productos is not null), 0) as ganancia
                    from ventas
                    where estado <> 'cancelada' and (%(desde)s::timestamptz is null or cerrada_en >= %(desde)s)
                    group by (origen = 'anuncio')
                    """,
                    {"desde": desde},
                )
                ventas = {bool(f["es_anuncio"]): f for f in _filas(cur)}
        vacio = {"ventas": 0, "ingresos": 0, "ganancia": 0}
        return {"base": base, "ventas_anuncio": ventas.get(True, vacio), "ventas_directo": ventas.get(False, vacio)}
