"""Acceso a datos de las opciones de entrega por producto (tabla `producto_entregas`, migración 020)."""
from typing import Any, Dict, List, Optional

from src.config.database import get_connection

_COLUMNAS = (
    "id, producto_sku, nombre, tipo, costo_cliente, costo_negocio, cantones, provincias, "
    "resto_del_pais, direccion_retiro, tiempo_entrega, activo, orden"
)


def insertar_opciones(cur, sku: str, opciones: List[Dict[str, Any]]) -> None:
    """Crea las opciones en el orden de la lista. Recibe el cursor para poder usarse dentro de otra
    transacción (la creación de un producto propio)."""
    for orden, opcion in enumerate(opciones):
        cur.execute(
            """
            insert into producto_entregas
                (producto_sku, nombre, tipo, costo_cliente, costo_negocio, cantones, provincias,
                 resto_del_pais, direccion_retiro, tiempo_entrega, activo, orden)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                sku, opcion["nombre"], opcion["tipo"], opcion["costo_cliente"], opcion["costo_negocio"],
                opcion["cantones"], opcion["provincias"], opcion["resto_del_pais"],
                opcion["direccion_retiro"], opcion["tiempo_entrega"], opcion["activo"], orden,
            ),
        )


class EntregaRepository:
    @staticmethod
    def listar(sku: str, solo_activas: bool = False) -> List[Dict[str, Any]]:
        filtro = "and activo = true" if solo_activas else ""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select {_COLUMNAS} from producto_entregas where producto_sku = %s {filtro} order by orden, id",
                    (sku,),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, fila)) for fila in cur.fetchall()]

    @staticmethod
    def obtener(opcion_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from producto_entregas where id = %s", (opcion_id,))
                fila = cur.fetchone()
                return dict(zip([d[0] for d in cur.description], fila)) if fila else None

    @staticmethod
    def reemplazar(sku: str, opciones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deja EXACTAMENTE estas opciones en el producto (borra las anteriores y crea las nuevas),
        todo en una sola transacción: nunca queda a medias. El orden es el de la lista."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from producto_entregas where producto_sku = %s", (sku,))
                insertar_opciones(cur, sku, opciones)
        return EntregaRepository.listar(sku)
