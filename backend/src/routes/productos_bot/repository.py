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

from .exceptions import ProductoBotYaExisteError

_COLUMNAS = (
    "id, sku, nombre, descripcion, precio, variantes, tiempo_entrega, "
    "metodos_pago_aceptados, preguntas_frecuentes, temas_no_responder, "
    "max_unidades_por_pedido, estado, activo, rocketfy_product_id, "
    "costo_rocketfy, precio_sugerido_rocketfy, stock_ultimo, stock_actualizado_en, "
    "peso_kg, imagen_url, notas_internas, publicado_en, publicado_por, "
    "precio_competencia, creado_en, actualizado_en"
)

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
    }
)

_COLUMNAS_ROCKETFY = (
    "rocketfy_product_id",
    "costo_rocketfy",
    "precio_sugerido_rocketfy",
    "stock_ultimo",
    "peso_kg",
    "imagen_url",
)


def _fila(cur) -> Optional[Dict[str, Any]]:
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip([d[0] for d in cur.description], row))


class ProductoBotGestionRepository:
    @staticmethod
    def listar(incluir_archivados: bool = False) -> List[dict]:
        filtro = "" if incluir_archivados else "where estado <> 'archivado'"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from productos_bot {filtro} order by actualizado_en desc, nombre")
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    @staticmethod
    def obtener(sku: str) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from productos_bot where sku = %s", (sku,))
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
                        f"""
                        insert into productos_bot
                            (sku, nombre, descripcion, precio, tiempo_entrega, metodos_pago_aceptados,
                             max_unidades_por_pedido, estado, activo,
                             rocketfy_product_id, costo_rocketfy, precio_sugerido_rocketfy,
                             stock_ultimo, stock_actualizado_en, peso_kg, imagen_url)
                        values (%s, %s, %s, %s, '', %s, 1, 'borrador', false, %s, %s, %s, %s, now(), %s, %s)
                        returning {_COLUMNAS}
                        """,
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
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"update productos_bot set {asignaciones}, actualizado_en = now() where sku = %s returning {_COLUMNAS}",
                    (*campos.values(), sku),
                )
                return _fila(cur)

    @staticmethod
    def guardar_datos_rocketfy(sku: str, datos: Dict[str, Any]) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    update productos_bot set
                        rocketfy_product_id = %s, costo_rocketfy = %s, precio_sugerido_rocketfy = %s,
                        stock_ultimo = %s, peso_kg = %s, imagen_url = %s,
                        stock_actualizado_en = now(), actualizado_en = now()
                    where sku = %s
                    returning {_COLUMNAS}
                    """,
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
                    f"""
                    update productos_bot set
                        estado = %s, activo = %s,
                        publicado_en  = case when %s then now() else publicado_en end,
                        publicado_por = case when %s then %s else publicado_por end,
                        actualizado_en = now()
                    where sku = %s
                    returning {_COLUMNAS}
                    """,
                    (estado, activo, activo, activo, usuario, sku),
                )
                return _fila(cur)

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
