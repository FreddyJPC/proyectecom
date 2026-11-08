"""
Acceso a datos de las ventas (tablas `ventas` y `ventas_lineas`, migración 020).

Dos caminos:
  - `registrar`: la venta de un producto con cierre automático (Rocketfy). El pedido real ya se creó en
    Rocketfy; esto deja la «foto» para los reportes. Es idempotente por lead.
  - `cerrar_manual`: la venta de un producto propio. Hace TODO en una sola transacción —descontar el stock,
    guardar la venta, marcar el lead, completar la solicitud de gestión y pasar la conversación al
    dueño—, así nunca queda un stock descontado sin venta ni una venta sin aviso.
"""
from typing import Any, Dict, List, Optional

from src.config.database import get_connection
from src.routes.gestion.repository import ResultadoUpsert, upsert_solicitud

from .exceptions import StockInsuficienteError, VentaYaRegistradaError

_COLUMNAS_VENTA = (
    "lead_id", "conversacion_id", "proveedor_id", "canal", "id_anuncio", "estado", "metodo_pago",
    "cliente_nombre", "telefono", "direccion", "canton", "provincia", "entrega_tipo", "entrega_nombre",
    "subtotal", "costo_envio_cliente", "total", "costo_productos", "costo_envio_negocio",
    "id_pedido_local", "id_pedido_rocketfy",
)
_COLUMNAS_LINEA = (
    "producto_sku", "producto_nombre", "variante", "categoria_id", "categoria_nombre",
    "cantidad", "precio_unitario", "costo_unitario",
)


def _insertar_venta(cur, venta: Dict[str, Any], lineas: List[Dict[str, Any]]) -> Optional[int]:
    """Inserta la venta y sus líneas. Devuelve su id, o None si ese lead ya tenía una venta."""
    cur.execute(
        f"insert into ventas ({', '.join(_COLUMNAS_VENTA)}) values ({', '.join(['%s'] * len(_COLUMNAS_VENTA))}) "
        "on conflict (lead_id) do nothing returning id",
        tuple(venta.get(c) for c in _COLUMNAS_VENTA),
    )
    fila = cur.fetchone()
    if fila is None:
        return None
    venta_id = fila[0]
    for linea in lineas:
        cur.execute(
            f"insert into ventas_lineas (venta_id, {', '.join(_COLUMNAS_LINEA)}) "
            f"values (%s, {', '.join(['%s'] * len(_COLUMNAS_LINEA))})",
            (venta_id, *(linea.get(c) for c in _COLUMNAS_LINEA)),
        )
    return venta_id


class VentasRepository:
    @staticmethod
    def registrar(venta: Dict[str, Any], lineas: List[Dict[str, Any]]) -> Optional[int]:
        """Guarda la venta ya cerrada (producto de Rocketfy). None = ese lead ya estaba registrado."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                return _insertar_venta(cur, venta, lineas)

    @staticmethod
    def obtener_por_lead(lead_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select * from ventas where lead_id = %s", (lead_id,))
                fila = cur.fetchone()
                return dict(zip([d[0] for d in cur.description], fila)) if fila else None

    @staticmethod
    def cerrar_manual(
        venta: Dict[str, Any],
        lineas: List[Dict[str, Any]],
        sku: str,
        cantidad: int,
        controla_stock: bool,
        detalle_solicitud: str,
    ) -> Dict[str, Any]:
        """Cierra la venta de un producto propio en una sola transacción (ver el docstring del módulo).

        Lanza `StockInsuficienteError` si el producto lleva control de stock y no alcanza (no se toca
        nada) y `VentaYaRegistradaError` si ese lead ya había cerrado."""
        conversacion_id, lead_id = venta["conversacion_id"], venta["lead_id"]
        with get_connection() as conn:
            with conn.cursor() as cur:
                stock_restante: Optional[int] = None
                pausado = False
                if controla_stock:
                    cur.execute(
                        """
                        update productos_bot set
                            stock_ultimo = stock_ultimo - %s, stock_actualizado_en = now(), actualizado_en = now()
                        where sku = %s and stock_ultimo >= %s
                        returning stock_ultimo
                        """,
                        (cantidad, sku, cantidad),
                    )
                    fila = cur.fetchone()
                    if fila is None:
                        cur.execute("select stock_ultimo from productos_bot where sku = %s", (sku,))
                        actual = cur.fetchone()
                        raise StockInsuficienteError(disponible=actual[0] if actual else None)
                    stock_restante = fila[0]
                    if stock_restante <= 0:
                        # Se vendió la última unidad: el producto deja de ofrecerse solo (reanudar es manual).
                        cur.execute(
                            "update productos_bot set estado = 'agotado', activo = false, actualizado_en = now() "
                            "where sku = %s and estado = 'activo'",
                            (sku,),
                        )
                        pausado = cur.rowcount > 0

                venta_id = _insertar_venta(cur, venta, lineas)
                if venta_id is None:
                    raise VentaYaRegistradaError(lead_id)

                cur.execute(
                    "update leads set estado = 'por_gestionar', actualizado_en = now() where id = %s", (lead_id,)
                )
                solicitud: ResultadoUpsert = upsert_solicitud(
                    cur, conversacion_id, lead_id, "pedido_cerrado", detalle_solicitud, venta_id=venta_id
                )
                cur.execute(
                    "update conversaciones set estado = 'en_gestion', vista_en = null, actualizada_en = now() "
                    "where id = %s",
                    (conversacion_id,),
                )
        return {
            "venta_id": venta_id,
            "solicitud": solicitud,
            "stock_restante": stock_restante,
            "pausado_por_agotado": pausado,
        }
