"""
Acceso a datos de la GESTIÓN de productos de ventas (dashboard). Es la misma
tabla `productos_bot` que lee el bot (src/routes/whatsapp/repository.py ->
ProductoBotRepository, que se queda tal cual para no tocar el camino de
Victoria), pero con las columnas y operaciones propias de la gestión:
estados, datos de Rocketfy, historial.
"""
import json
from typing import Any, Dict, List, Optional

import psycopg2.errors
from psycopg2.extras import Json

from src.config.database import get_connection

from src.routes.entregas.repository import insertar_opciones
from src.routes.ventas.origen import PREFIJO_SKU_PROPIO, PROVEEDOR_PROPIO_ID, PROVEEDOR_ROCKETFY_ID

from .exceptions import ProductoBotYaExisteError

# Columnas de `productos_bot`. El SELECT completo (`_SELECT`) las junta con el proveedor y la categoría, que
# vienen de otras tablas (ADR-012): `proveedor_clave`, `proveedor_nombre`, `proveedor_cierre`, `categoria_nombre`.
_COLUMNAS_TABLA = (
    "id, sku, nombre, descripcion, precio, variantes, tiempo_entrega, "
    "metodos_pago_aceptados, preguntas_frecuentes, temas_no_responder, "
    "max_unidades_por_pedido, estado, activo, rocketfy_product_id, "
    "costo_rocketfy, precio_sugerido_rocketfy, stock_ultimo, stock_actualizado_en, "
    "peso_kg, imagen_url, notas_internas, publicado_en, publicado_por, "
    "precio_competencia, proveedor_id, categoria_id, costo_propio, controla_stock, "
    "envio_incluido, costo_flete_estimado, creado_en, actualizado_en"
)


def _select(origen: str = "productos_bot") -> str:
    """El SELECT de un producto con su proveedor y categoría. `origen` es la tabla o el CTE de donde
    salen las filas (los UPDATE/INSERT devuelven la fila ya completa envolviéndose en un CTE)."""
    columnas = ", ".join(f"p.{c.strip()}" for c in _COLUMNAS_TABLA.split(","))
    return (
        f"select {columnas}, pr.clave as proveedor_clave, pr.nombre as proveedor_nombre, "
        f"pr.cierre as proveedor_cierre, c.nombre as categoria_nombre "
        f"from {origen} p join proveedores pr on pr.id = p.proveedor_id "
        f"left join categorias_producto c on c.id = p.categoria_id"
    )


def _escribir(sentencia: str) -> str:
    """Envuelve un INSERT/UPDATE (sin `returning`) para que devuelva la fila con proveedor y categoría."""
    return f"with fila_escrita as ({sentencia} returning *) {_select('fila_escrita')}"


# Únicas columnas que la API puede modificar. Se usa como lista blanca al
# armar el UPDATE: ningún nombre de columna llega desde el cliente.
COLUMNAS_EDITABLES = frozenset(
    {
        "nombre",
        "descripcion",
        "precio",
        "variantes",
        "tiempo_entrega",
        "metodos_pago_aceptados",
        "preguntas_frecuentes",
        "temas_no_responder",
        "max_unidades_por_pedido",
        "notas_internas",
        "precio_competencia",
        # ADR-012: válidas para cualquier producto...
        "categoria_id",
        "envio_incluido",
        "costo_flete_estimado",
        # ...y solo de un producto propio (el servicio lo exige): su costo y su stock.
        "costo_propio",
        "controla_stock",
        "stock_ultimo",
    }
)

COLUMNAS_SOLO_DE_PRODUCTO_PROPIO = frozenset({"costo_propio", "controla_stock", "stock_ultimo"})

_COLUMNAS_ROCKETFY = (
    "rocketfy_product_id",
    "costo_rocketfy",
    "precio_sugerido_rocketfy",
    "stock_ultimo",
    "peso_kg",
    "imagen_url",
)


# Entrada del historial cuando una compra de prueba con Victoria se completó de
# punta a punta (Fase E). Alimenta el aviso de la lista de verificación al publicar.
ACCION_SIMULACION_COMPLETA = "simulacion_completa"


def _fila(cur) -> Optional[Dict[str, Any]]:
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip([d[0] for d in cur.description], row))


class ProductoBotGestionRepository:
    @staticmethod
    def listar(incluir_archivados: bool = False) -> List[dict]:
        filtro = "" if incluir_archivados else "where p.estado <> 'archivado'"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"{_select()} {filtro} order by p.actualizado_en desc, p.nombre")
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    @staticmethod
    def obtener(sku: str) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"{_select()} where p.sku = %s", (sku,))
                return _fila(cur)

    @staticmethod
    def crear_borrador(
        sku: str,
        nombre: str,
        descripcion: str,
        precio,
        metodos_pago_aceptados: str,
        datos_rocketfy: Dict[str, Any],
    ) -> dict:
        """Siempre nace como 'borrador' y con activo = false: Victoria no lo ve
        hasta que el dueño lo publique."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        _escribir(
                            """
                            insert into productos_bot
                                (sku, nombre, descripcion, precio, tiempo_entrega, metodos_pago_aceptados,
                                 max_unidades_por_pedido, estado, activo,
                                 rocketfy_product_id, costo_rocketfy, precio_sugerido_rocketfy,
                                 stock_ultimo, stock_actualizado_en, peso_kg, imagen_url)
                            values (%s, %s, %s, %s, '', %s, 1, 'borrador', false, %s, %s, %s, %s, now(), %s, %s)
                            """
                        ),
                        (
                            sku, nombre, descripcion, precio, metodos_pago_aceptados,
                            datos_rocketfy["rocketfy_product_id"], datos_rocketfy["costo_rocketfy"],
                            datos_rocketfy["precio_sugerido_rocketfy"], datos_rocketfy["stock_ultimo"],
                            datos_rocketfy["peso_kg"], datos_rocketfy["imagen_url"],
                        ),
                    )
                    return _fila(cur)
        except psycopg2.errors.UniqueViolation as exc:
            raise ProductoBotYaExisteError(f"Ya existe un producto con el SKU '{sku}'.") from exc

    @staticmethod
    def actualizar_campos(sku: str, campos: Dict[str, Any]) -> Optional[dict]:
        desconocidos = set(campos) - COLUMNAS_EDITABLES
        if desconocidos:
            raise ValueError(f"Columnas no editables: {sorted(desconocidos)}")
        if not campos:
            return ProductoBotGestionRepository.obtener(sku)

        asignaciones = ", ".join(f"{columna} = %s" for columna in campos)  # nombres de la lista blanca
        if "stock_ultimo" in campos:
            asignaciones += ", stock_actualizado_en = now()"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    _escribir(f"update productos_bot set {asignaciones}, actualizado_en = now() where sku = %s"),
                    (*campos.values(), sku),
                )
                return _fila(cur)

    @staticmethod
    def guardar_datos_rocketfy(sku: str, datos: Dict[str, Any]) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    _escribir(
                        """
                        update productos_bot set
                            rocketfy_product_id = %s, costo_rocketfy = %s, precio_sugerido_rocketfy = %s,
                            stock_ultimo = %s, peso_kg = %s, imagen_url = %s,
                            stock_actualizado_en = now(), actualizado_en = now()
                        where sku = %s
                        """
                    ),
                    (*[datos[c] for c in _COLUMNAS_ROCKETFY], sku),
                )
                return _fila(cur)

    @staticmethod
    def cambiar_estado(sku: str, estado: str, usuario: Optional[str] = None) -> Optional[dict]:
        """Único lugar donde cambia `estado`. `activo` se escribe a la vez y con
        el mismo criterio (la base además lo exige con una restricción). Al
        activar se anota cuándo y quién."""
        activo = estado == "activo"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    _escribir(
                        """
                        update productos_bot set
                            estado = %s, activo = %s,
                            publicado_en  = case when %s then now() else publicado_en end,
                            publicado_por = case when %s then %s else publicado_por end,
                            actualizado_en = now()
                        where sku = %s
                        """
                    ),
                    (estado, activo, activo, activo, usuario, sku),
                )
                return _fila(cur)

    @staticmethod
    def pausar_por_agotado(sku: str) -> Optional[dict]:
        """Pasa un producto de `activo` a `agotado` SOLO si sigue activo en este
        instante (`where estado = 'activo'`): si una persona lo pausó o lo
        archivó mientras corría la sincronización, no se pisa su decisión. Devuelve
        la fila nueva, o None si ya no estaba activo."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    _escribir(
                        """
                        update productos_bot set estado = 'agotado', activo = false, actualizado_en = now()
                        where sku = %s and estado = 'activo'
                        """
                    ),
                    (sku,),
                )
                return _fila(cur)

    @staticmethod
    def contar_pedidos_por_sku(dias: int = 30) -> Dict[str, int]:
        """Pedidos creados en Rocketfy en los últimos `dias` días, por SKU (en
        mayúsculas). Un pedido con varias líneas del mismo SKU cuenta una vez.
        No cuentan los que fallaron al crearse ni los rechazados."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select upper(l ->> 'sku') as sku, count(distinct p.id_local)
                      from pedidos p
                      cross join lateral jsonb_array_elements(
                          case when jsonb_typeof(p.payload_creacion -> 'lineas') = 'array'
                               then p.payload_creacion -> 'lineas' else '[]'::jsonb end
                      ) as l
                     where p.creado_en >= now() - (%s || ' days')::interval
                       and p.estado_local in ('creado', 'confirmado')
                       and l ->> 'sku' is not null
                     group by 1
                    """,
                    (dias,),
                )
                conteo = {fila[0]: int(fila[1]) for fila in cur.fetchall()}
                # Los productos propios no crean pedidos en Rocketfy: sus ventas están en `ventas`.
                cur.execute(
                    """
                    select upper(vl.producto_sku), count(distinct v.id)
                      from ventas v join ventas_lineas vl on vl.venta_id = v.id
                     where v.cerrada_en >= now() - (%s || ' days')::interval
                       and v.estado <> 'cancelada' and v.proveedor_id <> %s
                     group by 1
                    """,
                    (dias, PROVEEDOR_ROCKETFY_ID),
                )
                for sku, cantidad in cur.fetchall():
                    conteo[sku] = conteo.get(sku, 0) + int(cantidad)
                return conteo

    @staticmethod
    def registrar_historial(sku: str, accion: str, usuario: Optional[str], cambios: Optional[dict] = None) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into productos_bot_historial (sku, accion, usuario, cambios) values (%s, %s, %s, %s)",
                    (
                        sku,
                        accion,
                        usuario,
                        Json(cambios, dumps=lambda o: json.dumps(o, default=str)) if cambios is not None else None,
                    ),
                )

    @staticmethod
    def ultima_fecha_de(sku: str, accion: str):
        """Cuándo fue la última vez que ocurrió `accion` en este producto (o None).
        Es una consulta propia (no el historial recortado a 20) para que un
        producto con mucha actividad no «olvide» su última simulación."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select max(creado_en) from productos_bot_historial where sku = %s and accion = %s",
                    (sku, accion),
                )
                return cur.fetchone()[0]

    @staticmethod
    def listar_historial(sku: str, limite: int = 20) -> List[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select accion, usuario, cambios, creado_en from productos_bot_historial
                    where sku = %s order by creado_en desc, id desc limit %s
                    """,
                    (sku, limite),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    @staticmethod
    def crear_propio(datos: Dict[str, Any], entregas: List[Dict[str, Any]]) -> dict:
        """Crea un producto PROPIO (ADR-012) como borrador, con su envío, en una sola transacción. El SKU
        lo genera la base (`PROP-0001`…): nunca choca con uno de Rocketfy. Nace con activo = false:
        Victoria no lo ve hasta que el dueño lo publique."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select nextval('productos_propios_seq')")
                sku = f"{PREFIJO_SKU_PROPIO}{cur.fetchone()[0]:04d}"
                cur.execute(
                    _escribir(
                        """
                        insert into productos_bot
                            (sku, nombre, descripcion, precio, variantes, tiempo_entrega, metodos_pago_aceptados,
                             preguntas_frecuentes, temas_no_responder, max_unidades_por_pedido, estado, activo,
                             proveedor_id, categoria_id, costo_propio, controla_stock, stock_ultimo,
                             stock_actualizado_en, envio_incluido, costo_flete_estimado)
                        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'borrador', false,
                                %s, %s, %s, %s, %s, now(), %s, %s)
                        """
                    ),
                    (
                        sku, datos["nombre"], datos["descripcion"], datos["precio"], datos.get("variantes"),
                        datos["tiempo_entrega"], datos["metodos_pago_aceptados"], datos.get("preguntas_frecuentes"),
                        datos.get("temas_no_responder"), datos["max_unidades_por_pedido"],
                        PROVEEDOR_PROPIO_ID, datos.get("categoria_id"), datos.get("costo_propio"),
                        datos["controla_stock"], datos.get("stock_ultimo"),
                        datos["envio_incluido"], datos.get("costo_flete_estimado"),
                    ),
                )
                fila = _fila(cur)
                insertar_opciones(cur, sku, entregas)
                return fila
