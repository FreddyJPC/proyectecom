from datetime import datetime
from typing import List, Optional

from src.config.database import get_connection
from src.routes.leads.sql import fijar_temperatura
from src.routes.leads.temperaturas import ABIERTAS, GANADO, ORIGEN_REGLA

# La conversación ya trae a su CONTACTO (ADR-014): `telefono` y `contacto_nombre` son los de la persona (el teléfono puede
# faltar en canales que no lo dan, como Instagram); `canal` + `id_externo` son cómo se la encuentra en ese canal.
_SELECT_CONVERSACION = (
    "select c.id, c.contacto_id, c.canal, c.id_externo, c.nombre_perfil, ct.telefono, ct.nombre as contacto_nombre, "
    "c.origen, c.id_anuncio, c.ctwa_clid, c.estado, c.vista_en, c.notas_internas, c.creada_en, c.actualizada_en "
    "from conversaciones c join contactos ct on ct.id = c.contacto_id"
)
_COLUMNAS_MENSAJE = "id, conversacion_id, rol, contenido, tipo, wamid, creado_en, media_id, media_mime, media_nombre, analisis"
# Lo que Victoria necesita saber de un producto. Además de la ficha, el proveedor (ADR-012: de él depende CÓMO
# se cierra la venta), el costo, el stock propio y el envío.
_COLUMNAS_PRODUCTO_BOT = (
    "id, sku, nombre, descripcion, precio, variantes, tiempo_entrega, "
    "metodos_pago_aceptados, preguntas_frecuentes, temas_no_responder, "
    "max_unidades_por_pedido, activo, imagen_url, estado, proveedor_id, categoria_id, "
    "costo_rocketfy, costo_propio, controla_stock, stock_ultimo, envio_incluido, costo_flete_estimado, "
    "creado_en, actualizado_en"
)
_SELECT_PRODUCTO_BOT = (
    "select "
    + ", ".join(f"p.{c.strip()}" for c in _COLUMNAS_PRODUCTO_BOT.split(","))
    + ", pr.clave as proveedor_clave, pr.cierre as proveedor_cierre, c.nombre as categoria_nombre "
    "from productos_bot p join proveedores pr on pr.id = p.proveedor_id "
    "left join categorias_producto c on c.id = p.categoria_id"
)
_COLUMNAS_LEAD = (
    "id, conversacion_id, contacto_id, nombre_cliente, telefono, direccion, canton, provincia, "
    "producto_sku, producto_nombre, producto_variante, cantidad, subtotal, total, metodo_pago, estado_pago, "
    "entrega_opcion_id, entrega_nombre, entrega_tipo, costo_envio, "
    "captura_pago_url, estado, id_pedido_local, id_pedido_rocketfy, creado_en, actualizado_en, "
    "temperatura, temperatura_motivo, temperatura_origen, temperatura_en, temperatura_fijada_hasta, motivo_perdida, "
    "cerrado_en, origen, id_anuncio, ctwa_clid, datos_confirmacion_pedida_en, datos_confirmados_en"
)

# Si cambia cualquier dato que aparece en el resumen de confirmación, el cliente tiene que volver a confirmar.
_BORRAR_CONFIRMACION = "datos_confirmacion_pedida_en = null, datos_confirmados_en = null"


# Una conversación acumula varios leads con el tiempo (uno por intención de compra): en la lista se muestra el ABIERTO o, si
# ninguno lo está, el más reciente. Sin esto, cada lead repetiría la fila de su conversación.
_LEAD_ACTUAL = (
    "left join lateral (select nombre_cliente, producto_nombre from leads where conversacion_id = c.id "
    "order by (temperatura in ('caliente', 'tibio', 'frio')) desc, creado_en desc, id desc limit 1) l on true"
)


class ConversacionRepository:
    @staticmethod
    def obtener_por_canal(canal: str, id_externo: str) -> Optional[dict]:
        """La conversación de un cliente en un canal (WhatsApp: `id_externo` es su teléfono)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"{_SELECT_CONVERSACION} where c.canal = %s and c.id_externo = %s",
                    (canal, id_externo),
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
                cur.execute(f"{_SELECT_CONVERSACION} where c.id = %s", (conversacion_id,))
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def crear(
        id_externo: str,
        canal: str = "whatsapp",
        origen: str = "directo",
        id_anuncio: Optional[str] = None,
        ctwa_clid: Optional[str] = None,
        nombre_perfil: Optional[str] = None,
        telefono: Optional[str] = None,
    ) -> dict:
        """Crea el contacto (si hace falta) y su conversación en ese canal, en UNA transacción. Es «crear o traer»:
        si dos mensajes del mismo cliente llegan a la vez (dos hilos), el segundo recibe la conversación que creó el
        primero en vez de fallar por duplicado y perder el mensaje.

        `telefono` es el teléfono del contacto cuando se conoce; en WhatsApp es el propio `id_externo`. Un mismo
        teléfono es un solo contacto: si ya existe, la conversación nueva (p. ej. otro canal) se cuelga de él."""
        if telefono is None and canal == "whatsapp":
            telefono = id_externo
        with get_connection() as conn:
            with conn.cursor() as cur:
                if telefono is not None:
                    cur.execute(
                        """
                        insert into contactos (telefono, nombre) values (%s, %s)
                        on conflict (telefono) where telefono is not null
                        do update set actualizado_en = now(), nombre = coalesce(contactos.nombre, excluded.nombre)
                        returning id
                        """,
                        (telefono, nombre_perfil),
                    )
                else:
                    cur.execute("insert into contactos (nombre) values (%s) returning id", (nombre_perfil,))
                contacto_id = cur.fetchone()[0]

                cur.execute(
                    """
                    insert into conversaciones (contacto_id, canal, id_externo, nombre_perfil, origen, id_anuncio, ctwa_clid)
                    values (%s, %s, %s, %s, %s, %s, %s)
                    on conflict (canal, id_externo)
                    do update set nombre_perfil = coalesce(excluded.nombre_perfil, conversaciones.nombre_perfil)
                    returning id
                    """,
                    (contacto_id, canal, id_externo, nombre_perfil, origen, id_anuncio, ctwa_clid),
                )
                conversacion_id = cur.fetchone()[0]

                cur.execute(f"{_SELECT_CONVERSACION} where c.id = %s", (conversacion_id,))
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
    def marcar_manual(conversacion_id: int) -> None:
        """El dueño toma la conversación: Victoria deja de responder. A diferencia de una escalada, el dueño ya la está
        viendo (la acaba de abrir o de escribir), así que queda como vista y no suma a «sin revisar»."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update conversaciones set estado = 'manual', vista_en = now(), actualizada_en = now() where id = %s",
                    (conversacion_id,),
                )

    @staticmethod
    def marcar_en_gestion(conversacion_id: int) -> None:
        """La conversación pasa a manos del dueño (ADR-012): un producto propio no crea el pedido solo,
        así que ante una intención de compra que Victoria no puede resolver, o al cerrar la venta, la
        conversación queda «en gestión» y Victoria deja de responder (igual que con una escalada).
        También limpia vista_en: debe aparecer como «sin revisar»."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update conversaciones set estado = 'en_gestion', vista_en = null, actualizada_en = now() where id = %s",
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
        canal: Optional[str] = None,
    ) -> dict:
        """Listado del módulo de Conversaciones (dashboard): una fila por
        conversación, con el nombre/producto del lead y el último mensaje
        ya resueltos (evita N+1 desde el frontend). `q` busca por teléfono,
        identificador del canal o nombre del cliente (sin distinguir mayúsculas)."""
        condiciones = []
        params: list = []
        if estado:
            condiciones.append("c.estado = %s")
            params.append(estado)
        if origen:
            condiciones.append("c.origen = %s")
            params.append(origen)
        if canal:
            condiciones.append("c.canal = %s")
            params.append(canal)
        if q:
            condiciones.append(
                "(ct.telefono ILIKE %s OR c.id_externo ILIKE %s OR lower(ct.nombre) LIKE lower(%s) "
                "OR lower(c.nombre_perfil) LIKE lower(%s) OR lower(l.nombre_cliente) LIKE lower(%s))"
            )
            comodin = f"%{q}%"
            params.extend([comodin] * 5)
        where = f"where {' and '.join(condiciones)}" if condiciones else ""

        # Cola de escaladas: la más antigua primero. Cualquier otro filtro:
        # la más reciente primero (lo último que se movió sube arriba).
        orden = "c.creada_en asc" if estado == "escalada" else "c.actualizada_en desc"

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select count(*) from conversaciones c join contactos ct on ct.id = c.contacto_id {_LEAD_ACTUAL} {where}",
                    params,
                )
                total = cur.fetchone()[0]

                offset = (page - 1) * page_size
                cur.execute(
                    f"""
                    select
                        c.id, c.canal, c.id_externo, ct.telefono, ct.nombre as contacto_nombre, c.nombre_perfil,
                        c.origen, c.estado, c.vista_en, c.creada_en, c.actualizada_en,
                        l.nombre_cliente, l.producto_nombre,
                        m.rol as ultimo_mensaje_rol, m.contenido as ultimo_mensaje_contenido, m.creado_en as ultimo_mensaje_creado_en
                    from conversaciones c
                    join contactos ct on ct.id = c.contacto_id
                    {_LEAD_ACTUAL}
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
                        count(*) filter (where estado = 'esperando_pago') as esperando_pago,
                        count(*) filter (where estado = 'en_gestion') as en_gestion,
                        count(*) filter (where estado = 'manual') as manual
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
    def contar_fotos(conversacion_id: int, sku: str) -> int:
        """¿Cuántas fotos de este producto se le mandaron ya a este cliente? Cada foto queda como un
        mensaje del bot con tipo 'imagen' y el SKU entre paréntesis (lo escribe `tools.py`): así no hace
        falta una tabla aparte y la próxima tanda de fotos sigue donde quedó la anterior. `strpos` y no
        `like`, para que un SKU con `%` o `_` no se interprete como comodín."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select count(*) from mensajes
                    where conversacion_id = %s and rol = 'bot' and tipo = 'imagen' and strpos(contenido, %s) > 0
                    """,
                    (conversacion_id, f"({sku})"),
                )
                return int(cur.fetchone()[0])

    @staticmethod
    def crear(
        conversacion_id: Optional[int],
        rol: str,
        contenido: str,
        tipo: str = "texto",
        wamid: Optional[str] = None,
        creado_en: Optional[datetime] = None,
        media_id: Optional[str] = None,
        media_mime: Optional[str] = None,
        media_nombre: Optional[str] = None,
    ) -> dict:
        """`creado_en` solo se pasa para ubicar la respuesta del bot ANTES de un mensaje del cliente que llegó
        mientras Victoria la redactaba (ver `VictoriaConversationService.procesar_turno`): así ese mensaje sigue
        figurando como «sin responder». Sin él, vale la hora de la base de datos."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    insert into mensajes (conversacion_id, rol, contenido, tipo, wamid, creado_en, media_id, media_mime, media_nombre)
                    values (%s, %s, %s, %s, %s, coalesce(%s, now()), %s, %s, %s)
                    returning {_COLUMNAS_MENSAJE}
                    """,
                    (conversacion_id, rol, contenido, tipo, wamid, creado_en, media_id, media_mime, media_nombre),
                )
                row = cur.fetchone()
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def guardar_analisis(mensaje_id: int, analisis: str) -> None:
        """Lo que se entendió de un archivo (la descripción de una foto, la transcripción de un audio). Es lo que se le muestra a
        Victoria en el historial en lugar de volver a mandarle el archivo en cada turno."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update mensajes set analisis = %s where id = %s", (analisis, mensaje_id))

    @staticmethod
    def obtener_por_id(mensaje_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS_MENSAJE} from mensajes where id = %s", (mensaje_id,))
                fila = cur.fetchone()
                if fila is None:
                    return None
                return dict(zip([d[0] for d in cur.description], fila))

    @staticmethod
    def obtener_por_conversacion(conversacion_id: int) -> List[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select {_COLUMNAS_MENSAJE} from mensajes
                    where conversacion_id = %s
                    order by creado_en asc, id asc
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
    def marcar_para_reintento(cola_mensajes_id: int, error_detalle: str) -> int:
        """La IA falló al generar la respuesta (sobrecarga, corte de red…): la tarea vuelve a 'pendiente' para
        intentarlo de nuevo en unos segundos. Devuelve cuántos intentos lleva."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update cola_mensajes
                    set estado = 'pendiente', error_detalle = %s, intentos = intentos + 1
                    where id = %s
                    returning intentos
                    """,
                    (error_detalle, cola_mensajes_id),
                )
                return int(cur.fetchone()[0])

    @staticmethod
    def obtener_pendientes() -> List[dict]:
        """Tareas a recuperar al arrancar el worker: las que quedaron
        'pendiente' (nunca se llegó a procesar) y TODAS las 'procesando'
        (huérfanas de un proceso anterior que murió a medio trabajar: hay un
        solo worker, así que al arrancar ninguna está realmente en marcha;
        antes solo se recuperaban las de más de 5 minutos y una tarea
        cortada por un reinicio se perdía en silencio. Si Victoria ya había
        contestado, `procesar_turno` lo detecta y no responde dos veces). Trae el canal y el identificador
        del cliente (vía conversaciones) y el texto del cliente (vía mensajes, solo aplica
        a modo='ia') porque TareaRespuestaDTO los necesita y, al ser una
        recuperación tras reinicio, no hay contexto en memoria del que
        tomarlos."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select cm.id, cm.conversacion_id, cm.modo, cm.texto_fijo, cm.intentos,
                           c.canal, c.id_externo, m.contenido as mensaje_cliente_texto
                    from cola_mensajes cm
                    join conversaciones c on c.id = cm.conversacion_id
                    left join mensajes m on m.id = cm.mensaje_id
                    where cm.estado in ('pendiente', 'procesando')
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
                cur.execute(f"{_SELECT_PRODUCTO_BOT} where p.sku = %s", (sku,))
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def obtener_por_id_anuncio(id_anuncio: str) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"{_SELECT_PRODUCTO_BOT} join anuncios_productos ap on ap.producto_sku = p.sku "
                    "where ap.id_anuncio = %s",
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
                cur.execute(f"{_SELECT_PRODUCTO_BOT} where p.activo = true order by p.nombre asc")
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
        max_unidades_por_pedido: int = 1,
    ) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    insert into productos_bot
                        (sku, nombre, descripcion, precio, variantes, tiempo_entrega,
                         metodos_pago_aceptados, preguntas_frecuentes, temas_no_responder,
                         max_unidades_por_pedido)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    returning {_COLUMNAS_PRODUCTO_BOT}
                    """,
                    (sku, nombre, descripcion, precio, variantes, tiempo_entrega,
                     metodos_pago_aceptados, preguntas_frecuentes, temas_no_responder,
                     max_unidades_por_pedido),
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
        max_unidades_por_pedido: int = 1,
    ) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    update productos_bot set
                        nombre = %s, descripcion = %s, precio = %s, variantes = %s,
                        tiempo_entrega = %s, metodos_pago_aceptados = %s,
                        preguntas_frecuentes = %s, temas_no_responder = %s,
                        max_unidades_por_pedido = %s,
                        actualizado_en = now()
                    where sku = %s
                    returning {_COLUMNAS_PRODUCTO_BOT}
                    """,
                    (nombre, descripcion, precio, variantes, tiempo_entrega,
                     metodos_pago_aceptados, preguntas_frecuentes, temas_no_responder,
                     max_unidades_por_pedido, sku),
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
        """El lead de esta conversación: el que está ABIERTO o, si ninguno lo está, el más reciente (una conversación
        acumula varios leads con el tiempo, uno por cada intención de compra)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select {_COLUMNAS_LEAD} from leads where conversacion_id = %s "
                    "order by (temperatura = any(%s)) desc, creado_en desc, id desc limit 1",
                    (conversacion_id, list(ABIERTAS)),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    def obtener_abierto(contacto_id: int) -> Optional[dict]:
        """El lead abierto (caliente, tibio o frío) de un contacto, por el canal que sea. Hay a lo sumo uno."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select {_COLUMNAS_LEAD} from leads where contacto_id = %s and temperatura = any(%s) limit 1",
                    (contacto_id, list(ABIERTAS)),
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
    def crear(conversacion_id: int, contacto_id: int, telefono: Optional[str], dias_atribucion: int = 30) -> Optional[dict]:
        """Abre un lead NUEVO para el contacto. `telefono` es el de contacto/entrega y puede faltar si el canal no lo da.

        La atribución (de qué anuncio nace) es POR LEAD: hereda el último anuncio del contacto solo si llegó en los últimos
        `dias_atribucion` días; si no, el lead es «directo» (un cliente que compró por un anuncio hace meses y vuelve solo no
        es una venta de ese anuncio). Si el contacto ya tiene otro lead abierto (dos mensajes a la vez), no crea otro y
        devuelve None: quien llama trae el que ya existe."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select a.id_anuncio, a.ctwa_clid
                    from conversacion_anuncios a join conversaciones c on c.id = a.conversacion_id
                    where c.contacto_id = %s and a.creado_en >= now() - make_interval(days => %s)
                    order by a.creado_en desc, a.id desc limit 1
                    """,
                    (contacto_id, dias_atribucion),
                )
                llegada = cur.fetchone()
                origen, id_anuncio, ctwa_clid = ("anuncio", llegada[0], llegada[1]) if llegada else ("directo", None, None)
                cur.execute(
                    f"""
                    insert into leads (conversacion_id, contacto_id, telefono, origen, id_anuncio, ctwa_clid,
                                       temperatura_motivo, temperatura_origen)
                    values (%s, %s, %s, %s, %s, %s, 'Lead nuevo', 'regla')
                    on conflict (contacto_id) where temperatura in ('caliente', 'tibio', 'frio') do nothing
                    returning {_COLUMNAS_LEAD}
                    """,
                    (conversacion_id, contacto_id, telefono, origen, id_anuncio, ctwa_clid),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                lead = dict(zip(cols, row))
                cur.execute(
                    "insert into lead_historial (lead_id, de, a, origen, motivo) values (%s, null, %s, 'regla', 'Lead nuevo')",
                    (lead["id"], lead["temperatura"]),
                )
                return lead

    @staticmethod
    def obtener_o_crear(conversacion_id: int, contacto_id: int, telefono: Optional[str], dias_atribucion: int = 30) -> dict:
        """El lead abierto del contacto o, si no tiene ninguno, uno nuevo (un cliente que vuelve por otro producto, o que ya
        compró, abre otro lead; el anterior queda en su historial)."""
        existente = LeadRepository.obtener_abierto(contacto_id)
        if existente is not None:
            return existente
        nuevo = LeadRepository.crear(conversacion_id, contacto_id, telefono, dias_atribucion)
        if nuevo is not None:
            return nuevo
        return LeadRepository.obtener_abierto(contacto_id)  # otro hilo lo creó justo antes

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
                    "select nombre_cliente, direccion, canton, provincia from leads where id = %s for update", (lead_id,)
                )
                actual = cur.fetchone()
                nuevos = (nombre_cliente, direccion, canton, provincia)
                # Solo cuenta si de verdad cambia un dato (repetir el mismo no obliga a confirmar otra vez).
                cambio = actual is not None and any(n is not None and n != a for n, a in zip(nuevos, actual))
                cur.execute(
                    f"""
                    update leads set
                        nombre_cliente = coalesce(%s, nombre_cliente),
                        direccion      = coalesce(%s, direccion),
                        canton         = coalesce(%s, canton),
                        provincia      = coalesce(%s, provincia),
                        {_BORRAR_CONFIRMACION if cambio else "datos_confirmados_en = datos_confirmados_en"},
                        actualizado_en = now()
                    where id = %s
                    """,
                    (nombre_cliente, direccion, canton, provincia, lead_id),
                )

    @staticmethod
    def marcar_confirmacion_pedida(lead_id: int) -> None:
        """Victoria le mostró el resumen al cliente: queda anotado cuándo (y se descarta una confirmación anterior)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update leads set datos_confirmacion_pedida_en = now(), datos_confirmados_en = null, "
                    "actualizado_en = now() where id = %s",
                    (lead_id,),
                )

    @staticmethod
    def confirmar_datos(lead_id: int) -> None:
        """El cliente confirmó el resumen: ahora sí se puede cerrar la venta."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update leads set datos_confirmados_en = now(), actualizado_en = now() where id = %s", (lead_id,))

    @staticmethod
    def actualizar_producto(
        lead_id: int,
        producto_sku: str,
        producto_nombre: str,
        total,
        variante: Optional[str] = None,
        cantidad: int = 1,
    ) -> None:
        # producto_variante usa COALESCE: si esta llamada no trae variante
        # (p.ej. el cliente todavía no la eligió), no borra una que ya se
        # haya guardado en una llamada anterior. `cantidad` y `total` sí se
        # reemplazan siempre: el total lo calcula el sistema (precio x
        # cantidad) cada vez que se registra el producto.
        #
        # ADR-012: `total` aquí es el SUBTOTAL (solo el producto). Cambiar de producto o de
        # cantidad borra la entrega elegida antes: el envío se vuelve a elegir con registrar_entrega
        # y el total vuelve a ser subtotal + envío.
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select producto_sku, cantidad, producto_variante, entrega_nombre from leads where id = %s for update", (lead_id,)
                )
                actual = cur.fetchone()
                # Registrar el producto también borra la entrega elegida (ver abajo): si había una, el resumen ya no vale.
                cambio = actual is not None and (
                    actual[0] != producto_sku
                    or int(actual[1] or 1) != int(cantidad)
                    or (variante is not None and actual[2] != variante)
                    or actual[3] is not None
                )
                cur.execute(
                    f"""
                    update leads set
                        producto_sku = %s, producto_nombre = %s, total = %s, subtotal = %s,
                        cantidad = %s,
                        producto_variante = coalesce(%s, producto_variante),
                        entrega_opcion_id = null, entrega_nombre = null, entrega_tipo = null, costo_envio = 0,
                        {_BORRAR_CONFIRMACION if cambio else "datos_confirmados_en = datos_confirmados_en"},
                        actualizado_en = now()
                    where id = %s
                    """,
                    (producto_sku, producto_nombre, total, total, cantidad, variante, lead_id),
                )

    @staticmethod
    def actualizar_entrega(
        lead_id: int, opcion_id: Optional[int], nombre: str, tipo: str, costo_envio, total
    ) -> None:
        """Guarda la entrega elegida y el total ya con el envío (lo calcula el sistema, no Victoria)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select entrega_opcion_id, entrega_nombre from leads where id = %s for update", (lead_id,))
                actual = cur.fetchone()
                cambio = actual is not None and (actual[0] != opcion_id or actual[1] != nombre)
                cur.execute(
                    f"""
                    update leads set
                        entrega_opcion_id = %s, entrega_nombre = %s, entrega_tipo = %s,
                        costo_envio = %s, total = %s,
                        {_BORRAR_CONFIRMACION if cambio else "datos_confirmados_en = datos_confirmados_en"},
                        actualizado_en = now()
                    where id = %s
                    """,
                    (opcion_id, nombre, tipo, costo_envio, total, lead_id),
                )

    @staticmethod
    def actualizar_metodo_pago(lead_id: int, metodo_pago: str, esperar_comprobante: bool = True) -> None:
        """`esperar_comprobante=False` es para productos propios: allí el dueño verifica el pago a mano,
        así que la transferencia NO deja el lead «esperando_pago» (ese estado dispara la regla de Rocketfy
        que le pide el comprobante a Victoria)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select metodo_pago from leads where id = %s for update", (lead_id,))
                actual = cur.fetchone()
                cambio = actual is not None and actual[0] != metodo_pago
                cur.execute(
                    f"""
                    update leads set
                        metodo_pago = %s,
                        estado = case when %s and %s = 'transferencia' then 'esperando_pago' else estado end,
                        {_BORRAR_CONFIRMACION if cambio else "datos_confirmados_en = datos_confirmados_en"},
                        actualizado_en = now()
                    where id = %s
                    """,
                    (metodo_pago, esperar_comprobante, metodo_pago, lead_id),
                )

    @staticmethod
    def actualizar_despacho(lead_id: int, id_pedido_local: int, id_pedido_rocketfy: Optional[int]) -> None:
        """El pedido se creó en Rocketfy: el lead pasa a «despachado» y, por reglas, a «ganado» (misma transacción)."""
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
                fijar_temperatura(cur, lead_id, GANADO, ORIGEN_REGLA, "Pedido despachado por Rocketfy")

    @staticmethod
    def resumen_del_contacto(contacto_id: int, lead_actual_id: int) -> dict:
        """Lo que Victoria necesita saber del pasado de un contacto: sus leads anteriores (el actual se excluye) y cuántas
        veces compró (ventas no canceladas)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select producto_nombre, temperatura, motivo_perdida, creado_en, cerrado_en from leads
                    where contacto_id = %s and id <> %s order by creado_en desc, id desc limit 5
                    """,
                    (contacto_id, lead_actual_id),
                )
                cols = [d[0] for d in cur.description]
                previos = [dict(zip(cols, fila)) for fila in cur.fetchall()]
                cur.execute("select count(*) from ventas where contacto_id = %s and estado <> 'cancelada'", (contacto_id,))
                compras = cur.fetchone()[0]
        return {"previos": previos, "compras": compras}

    @staticmethod
    def existe_pedido_previo(contacto_id: int) -> bool:
        """¿Este contacto ya tiene un pedido cerrado, por el canal que sea? `despachado` (Rocketfy lo creó) o
        `por_gestionar` (producto propio: el dueño lo está gestionando)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select 1 from leads where contacto_id = %s and estado in ('despachado', 'por_gestionar') limit 1",
                    (contacto_id,),
                )
                return cur.fetchone() is not None


class MinimoObservadoRepository:
    """Montos mínimos que Rocketfy exigió al rechazar una confirmación -- ver
    migración 013_ventas_seguras.sql y minimos.py. Sirve para calibrar el
    costo de envío estimado (Fase C del plan de gestión de productos)."""

    @staticmethod
    def guardar(
        sku: Optional[str],
        canton: Optional[str],
        provincia: Optional[str],
        cantidad: Optional[int],
        minimo,
        mensaje: str,
    ) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into rocketfy_minimos_observados
                        (sku, canton, provincia, cantidad, minimo, mensaje)
                    values (%s, %s, %s, %s, %s, %s)
                    """,
                    (sku, canton, provincia, cantidad, minimo, mensaje),
                )
