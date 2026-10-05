from typing import List, Optional

from src.config.database import get_connection

_COLUMNAS_CONVERSACION = (
    "id, telefono, origen, fep_expira_en, id_anuncio, ctwa_clid, "
    "estado, vista_en, notas_internas, creada_en, actualizada_en"
)
_COLUMNAS_MENSAJE = "id, conversacion_id, rol, contenido, tipo, wamid, creado_en"
_COLUMNAS_PRODUCTO_BOT = (
    "id, sku, nombre, descripcion, precio, variantes, tiempo_entrega, "
    "metodos_pago_aceptados, preguntas_frecuentes, temas_no_responder, "
    "activo, creado_en, actualizado_en"
)
_COLUMNAS_LEAD = (
    "id, conversacion_id, nombre_cliente, telefono, direccion, canton, provincia, "
    "producto_sku, producto_nombre, producto_variante, total, metodo_pago, estado_pago, "
    "captura_pago_url, estado, id_pedido_local, id_pedido_rocketfy, creado_en, actualizado_en"
)


class ConversacionRepository:
    @staticmethod
    def obtener_por_telefono(telefono: str) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select {_COLUMNAS_CONVERSACION} from conversaciones where telefono = %s",
                    (telefono,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def obtener_por_id(conversacion_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select {_COLUMNAS_CONVERSACION} from conversaciones where id = %s",
                    (conversacion_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def crear(
        telefono: str,
        origen: str = "directo",
        fep_expira_en=None,
        id_anuncio: Optional[str] = None,
        ctwa_clid: Optional[str] = None,
    ) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    insert into conversaciones (telefono, origen, fep_expira_en, id_anuncio, ctwa_clid)
                    values (%s, %s, %s, %s, %s)
                    returning {_COLUMNAS_CONVERSACION}
                    """,
                    (telefono, origen, fep_expira_en, id_anuncio, ctwa_clid),
                )
                row = cur.fetchone()
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def actualizar_estado(conversacion_id: int, estado: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update conversaciones set estado = %s, actualizada_en = now() where id = %s",
                    (estado, conversacion_id),
                )

    @staticmethod
    def marcar_escalada(conversacion_id: int) -> None:
        """A diferencia de actualizar_estado() genérico, también limpia
        vista_en -- si esta conversación ya se había escalado antes y se
        vio, debe volver a aparecer como "sin revisar" (módulo de
        Conversaciones del dashboard, Tarea 2)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update conversaciones set estado = 'escalada', vista_en = null, actualizada_en = now() where id = %s",
                    (conversacion_id,),
                )

    @staticmethod
    def actualizar_timestamp(conversacion_id: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update conversaciones set actualizada_en = now() where id = %s",
                    (conversacion_id,),
                )

    @staticmethod
    def marcar_esperando_pago(conversacion_id: int) -> None:
        """Espejo a nivel conversación de leads.estado='esperando_pago' --
        sin esto, el filtro/pestaña "Esperando pago" del módulo de
        Conversaciones (dashboard) nunca encontraría nada, porque nada
        ponía este estado en `conversaciones` hasta ahora (solo en
        `leads`). Se llama desde tools.py::_handle_registrar_metodo_pago."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update conversaciones set estado = 'esperando_pago', actualizada_en = now() where id = %s",
                    (conversacion_id,),
                )

    @staticmethod
    def marcar_vista(conversacion_id: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update conversaciones set vista_en = now() where id = %s",
                    (conversacion_id,),
                )

    @staticmethod
    def actualizar_notas(conversacion_id: int, notas_internas: Optional[str]) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update conversaciones set notas_internas = %s where id = %s",
                    (notas_internas, conversacion_id),
                )

    @staticmethod
    def listar(
        estado: Optional[str] = None,
        origen: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Listado del módulo de Conversaciones (dashboard): una fila por
        conversación, con el nombre/producto del lead y el último mensaje
        ya resueltos (evita N+1 desde el frontend). `q` busca por teléfono
        o nombre del cliente (sin distinguir mayúsculas)."""
        condiciones = []
        params: list = []
        if estado:
            condiciones.append("c.estado = %s")
            params.append(estado)
        if origen:
            condiciones.append("c.origen = %s")
            params.append(origen)
        if q:
            condiciones.append("(c.telefono ILIKE %s OR lower(l.nombre_cliente) LIKE lower(%s))")
            comodin = f"%{q}%"
            params.extend([comodin, comodin])
        where = f"where {' and '.join(condiciones)}" if condiciones else ""

        # Cola de escaladas: la más antigua primero. Cualquier otro filtro:
        # la más reciente primero (lo último que se movió sube arriba).
        orden = "c.creada_en asc" if estado == "escalada" else "c.actualizada_en desc"

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select count(*) from conversaciones c left join leads l on l.conversacion_id = c.id {where}", params)
                total = cur.fetchone()[0]

                offset = (page - 1) * page_size
                cur.execute(
                    f"""
                    select
                        c.id, c.telefono, c.origen, c.estado, c.vista_en, c.creada_en, c.actualizada_en,
                        l.nombre_cliente, l.producto_nombre,
                        m.rol as ultimo_mensaje_rol, m.contenido as ultimo_mensaje_contenido, m.creado_en as ultimo_mensaje_creado_en
                    from conversaciones c
                    left join leads l on l.conversacion_id = c.id
                    left join lateral (
                        select rol, contenido, creado_en from mensajes
                        where conversacion_id = c.id order by creado_en desc limit 1
                    ) m on true
                    {where}
                    order by {orden}
                    limit %s offset %s
                    """,
                    params + [page_size, offset],
                )
                cols = [d[0] for d in cur.description]
                filas = [dict(zip(cols, row)) for row in cur.fetchall()]

        return {"items": filas, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def contar_por_filtro_rapido() -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        count(*) filter (where estado = 'escalada') as escaladas,
                        count(*) filter (where estado = 'escalada' and vista_en is null) as escaladas_sin_revisar,
                        count(*) filter (where estado = 'esperando_pago') as esperando_pago
                    from conversaciones
                    """
                )
                row = cur.fetchone()
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))


class MensajeRepository:
    @staticmethod
    def existe_por_wamid(wamid: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1 from mensajes where wamid = %s", (wamid,))
                return cur.fetchone() is not None

    @staticmethod
    def crear(conversacion_id: Optional[int], rol: str, contenido: str, tipo: str = "texto", wamid: Optional[str] = None) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    insert into mensajes (conversacion_id, rol, contenido, tipo, wamid)
                    values (%s, %s, %s, %s, %s)
                    returning {_COLUMNAS_MENSAJE}
                    """,
                    (conversacion_id, rol, contenido, tipo, wamid),
                )
                row = cur.fetchone()
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def obtener_por_conversacion(conversacion_id: int) -> List[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select {_COLUMNAS_MENSAJE} from mensajes
                    where conversacion_id = %s
                    order by creado_en asc
                    """,
                    (conversacion_id,),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]


class ColaMensajeRepository:
    """Persistencia de `cola_mensajes` -- ver worker.py para el porqué:
    la queue.Queue en memoria no sobrevive a un reinicio del proceso, esta
    tabla es la fuente de verdad que permite recuperar el trabajo
    pendiente al arrancar."""

    @staticmethod
    def crear(conversacion_id: int, modo: str, mensaje_id: Optional[int] = None, texto_fijo: Optional[str] = None) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into cola_mensajes (conversacion_id, mensaje_id, modo, texto_fijo)
                    values (%s, %s, %s, %s)
                    returning id, conversacion_id, mensaje_id, modo, texto_fijo, estado, intentos
                    """,
                    (conversacion_id, mensaje_id, modo, texto_fijo),
                )
                row = cur.fetchone()
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def marcar_procesando(cola_mensajes_id: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update cola_mensajes set estado = 'procesando' where id = %s",
                    (cola_mensajes_id,),
                )

    @staticmethod
    def marcar_completado(cola_mensajes_id: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update cola_mensajes set estado = 'completado', procesado_en = now() where id = %s",
                    (cola_mensajes_id,),
                )

    @staticmethod
    def marcar_error(cola_mensajes_id: int, error_detalle: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update cola_mensajes
                    set estado = 'error', error_detalle = %s, intentos = intentos + 1
                    where id = %s
                    """,
                    (error_detalle, cola_mensajes_id),
                )

    @staticmethod
    def obtener_pendientes() -> List[dict]:
        """Tareas a recuperar al arrancar el worker: las que quedaron
        'pendiente' (nunca se llegó a procesar) y las que quedaron
        'procesando' hace más de 5 minutos (huérfanas de un proceso
        anterior que murió a medio trabajar). Trae el teléfono (vía
        conversaciones) y el texto del cliente (vía mensajes, solo aplica
        a modo='ia') porque TareaRespuestaDTO los necesita y, al ser una
        recuperación tras reinicio, no hay contexto en memoria del que
        tomarlos."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select cm.id, cm.conversacion_id, cm.modo, cm.texto_fijo,
                           c.telefono, m.contenido as mensaje_cliente_texto
                    from cola_mensajes cm
                    join conversaciones c on c.id = cm.conversacion_id
                    left join mensajes m on m.id = cm.mensaje_id
                    where cm.estado = 'pendiente'
                       or (cm.estado = 'procesando' and cm.creado_en < now() - interval '5 minutes')
                    order by cm.creado_en asc
                    """
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]


class ProductoBotRepository:
    """Base de conocimiento de ventas de Victoria -- ver migración
    008_productos_bot.sql. Completamente separada del catálogo de
    Rocketfy (src/routes/productos): esa es para SKU/stock real, esta es
    contenido de ventas."""

    @staticmethod
    def obtener_por_sku(sku: str) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select {_COLUMNAS_PRODUCTO_BOT} from productos_bot where sku = %s",
                    (sku,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def obtener_por_id_anuncio(id_anuncio: str) -> Optional[dict]:
        columnas_prefijadas = ", ".join(f"p.{c.strip()}" for c in _COLUMNAS_PRODUCTO_BOT.split(","))
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select {columnas_prefijadas}
                    from anuncios_productos ap
                    join productos_bot p on p.sku = ap.producto_sku
                    where ap.id_anuncio = %s
                    """,
                    (id_anuncio,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def listar_activos() -> List[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select {_COLUMNAS_PRODUCTO_BOT} from productos_bot where activo = true order by nombre asc"
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    @staticmethod
    def crear(
        sku: str,
        nombre: str,
        descripcion: str,
        precio,
        tiempo_entrega: str,
        metodos_pago_aceptados: str = "contraentrega, transferencia",
        variantes: Optional[str] = None,
        preguntas_frecuentes: Optional[str] = None,
        temas_no_responder: Optional[str] = None,
    ) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    insert into productos_bot
                        (sku, nombre, descripcion, precio, variantes, tiempo_entrega,
                         metodos_pago_aceptados, preguntas_frecuentes, temas_no_responder)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    returning {_COLUMNAS_PRODUCTO_BOT}
                    """,
                    (sku, nombre, descripcion, precio, variantes, tiempo_entrega,
                     metodos_pago_aceptados, preguntas_frecuentes, temas_no_responder),
                )
                row = cur.fetchone()
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def actualizar(
        sku: str,
        nombre: str,
        descripcion: str,
        precio,
        tiempo_entrega: str,
        metodos_pago_aceptados: str = "contraentrega, transferencia",
        variantes: Optional[str] = None,
        preguntas_frecuentes: Optional[str] = None,
        temas_no_responder: Optional[str] = None,
    ) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    update productos_bot set
                        nombre = %s, descripcion = %s, precio = %s, variantes = %s,
                        tiempo_entrega = %s, metodos_pago_aceptados = %s,
                        preguntas_frecuentes = %s, temas_no_responder = %s,
                        actualizado_en = now()
                    where sku = %s
                    returning {_COLUMNAS_PRODUCTO_BOT}
                    """,
                    (nombre, descripcion, precio, variantes, tiempo_entrega,
                     metodos_pago_aceptados, preguntas_frecuentes, temas_no_responder, sku),
                )
                row = cur.fetchone()
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def vincular_anuncio(id_anuncio: str, producto_sku: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into anuncios_productos (id_anuncio, producto_sku)
                    values (%s, %s)
                    on conflict (id_anuncio) do update set producto_sku = excluded.producto_sku
                    """,
                    (id_anuncio, producto_sku),
                )


class LeadRepository:
    """Datos de venta que Victoria va recopilando durante la conversación
    -- ver migración 006_leads.sql. Nunca se fusiona con `pedidos`
    (Fase 1): esa es el contrato ya cerrado con Rocketfy, esta es la
    venta en curso."""

    @staticmethod
    def obtener_por_conversacion(conversacion_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select {_COLUMNAS_LEAD} from leads where conversacion_id = %s",
                    (conversacion_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def obtener_por_id(lead_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS_LEAD} from leads where id = %s", (lead_id,))
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def crear(conversacion_id: int, telefono: str) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    insert into leads (conversacion_id, telefono)
                    values (%s, %s)
                    returning {_COLUMNAS_LEAD}
                    """,
                    (conversacion_id, telefono),
                )
                row = cur.fetchone()
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def obtener_o_crear(conversacion_id: int, telefono: str) -> dict:
        existente = LeadRepository.obtener_por_conversacion(conversacion_id)
        if existente is not None:
            return existente
        return LeadRepository.crear(conversacion_id, telefono)

    @staticmethod
    def actualizar_datos_cliente(
        lead_id: int,
        nombre_cliente: Optional[str] = None,
        direccion: Optional[str] = None,
        canton: Optional[str] = None,
        provincia: Optional[str] = None,
    ) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update leads set
                        nombre_cliente = coalesce(%s, nombre_cliente),
                        direccion      = coalesce(%s, direccion),
                        canton         = coalesce(%s, canton),
                        provincia      = coalesce(%s, provincia),
                        actualizado_en = now()
                    where id = %s
                    """,
                    (nombre_cliente, direccion, canton, provincia, lead_id),
                )

    @staticmethod
    def actualizar_producto(
        lead_id: int, producto_sku: str, producto_nombre: str, total, variante: Optional[str] = None
    ) -> None:
        # producto_variante usa COALESCE: si esta llamada no trae variante
        # (p.ej. el cliente todavía no la eligió), no borra una que ya se
        # haya guardado en una llamada anterior.
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update leads set
                        producto_sku = %s, producto_nombre = %s, total = %s,
                        producto_variante = coalesce(%s, producto_variante),
                        actualizado_en = now()
                    where id = %s
                    """,
                    (producto_sku, producto_nombre, total, variante, lead_id),
                )

    @staticmethod
    def actualizar_metodo_pago(lead_id: int, metodo_pago: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update leads set
                        metodo_pago = %s,
                        estado = case when %s = 'transferencia' then 'esperando_pago' else estado end,
                        actualizado_en = now()
                    where id = %s
                    """,
                    (metodo_pago, metodo_pago, lead_id),
                )

    @staticmethod
    def actualizar_despacho(lead_id: int, id_pedido_local: int, id_pedido_rocketfy: Optional[int]) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update leads set
                        estado = 'despachado', id_pedido_local = %s, id_pedido_rocketfy = %s, actualizado_en = now()
                    where id = %s
                    """,
                    (id_pedido_local, id_pedido_rocketfy, lead_id),
                )

    @staticmethod
    def existe_despachado_por_telefono(telefono: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select 1 from leads where telefono = %s and estado = 'despachado' limit 1",
                    (telefono,),
                )
                return cur.fetchone() is not None
