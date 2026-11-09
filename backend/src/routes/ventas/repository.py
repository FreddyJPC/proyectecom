"""
Acceso a datos de las ventas (tablas `ventas` y `ventas_lineas`, migración 020).

Dos caminos:
  - `registrar`: la venta de un producto con cierre automático (Rocketfy). El pedido real ya se creó en
    Rocketfy; esto deja la «foto» para los reportes. Es idempotente por lead.
  - `cerrar_manual`: la venta de un producto propio. Hace TODO en una sola transacción —descontar el stock,
    guardar la venta, marcar el lead, completar la solicitud de gestión y pasar la conversación al
    dueño—, así nunca queda un stock descontado sin venta ni una venta sin aviso.
  - `cobrar` / `deshacer_cobro` / `cancelar`: lo que el dueño hace DESPUÉS con esa venta. Cada una bloquea la
    fila de la venta y decide con las reglas puras de `reglas.py`, así que dos toques seguidos no
    devuelven el stock dos veces. `cancelar` también es todo-o-nada: stock devuelto, venta cancelada, lead,
    solicitud pendiente y conversación.
"""
from typing import Any, Dict, List, Optional

from src.config.database import get_connection
from src.routes.gestion.repository import ResultadoUpsert, upsert_solicitud
from src.routes.leads.sql import fijar_temperatura
from src.routes.leads.temperaturas import GANADO, ORIGEN_REGLA, PERDIDO

from .exceptions import AccionDeVentaNoPermitidaError, StockInsuficienteError, VentaNoEncontradaError, VentaYaRegistradaError
from .reglas import motivo_para_no_cancelar, motivo_para_no_cobrar, motivo_para_no_deshacer_cobro

_COLUMNAS_VENTA = (
    "lead_id", "conversacion_id", "contacto_id", "proveedor_id", "origen", "canal", "id_anuncio", "estado", "metodo_pago",
    "cliente_nombre", "telefono", "direccion", "canton", "provincia", "entrega_tipo", "entrega_nombre",
    "subtotal", "costo_envio_cliente", "total", "costo_productos", "costo_envio_negocio",
    "id_pedido_local", "id_pedido_rocketfy",
)
_COLUMNAS_LINEA = (
    "producto_sku", "producto_nombre", "variante", "categoria_id", "categoria_nombre",
    "cantidad", "precio_unitario", "costo_unitario", "stock_descontado",
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

                # Cada línea recuerda cuántas unidades se descontaron DE VERDAD: es lo que devolverá cancelar.
                lineas = [{**linea, "stock_descontado": cantidad if controla_stock else None} for linea in lineas]
                venta_id = _insertar_venta(cur, venta, lineas)
                if venta_id is None:
                    raise VentaYaRegistradaError(lead_id)

                cur.execute(
                    "update leads set estado = 'por_gestionar', actualizado_en = now() where id = %s", (lead_id,)
                )
                fijar_temperatura(cur, lead_id, GANADO, ORIGEN_REGLA, "Venta cerrada (producto propio)")
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

    # ------------------------------------------------------------------
    # Después de cerrar: cobrar y cancelar (solo ventas de productos propios)
    # ------------------------------------------------------------------
    @staticmethod
    def obtener(venta_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                return _leer_venta(cur, venta_id)

    @staticmethod
    def cobrar(venta_id: int, usuario: Optional[str], nota: Optional[str]) -> Dict[str, Any]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                venta = _bloquear(cur, venta_id)
                motivo = motivo_para_no_cobrar(venta)
                if motivo:
                    raise AccionDeVentaNoPermitidaError(motivo)
                cur.execute(
                    "update ventas set cobrada_en = now(), cobrada_por = %s, nota_cobro = %s where id = %s",
                    (usuario, nota, venta_id),
                )
                return _leer_venta(cur, venta_id)

    @staticmethod
    def deshacer_cobro(venta_id: int) -> Dict[str, Any]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                venta = _bloquear(cur, venta_id)
                motivo = motivo_para_no_deshacer_cobro(venta)
                if motivo:
                    raise AccionDeVentaNoPermitidaError(motivo)
                cur.execute(
                    "update ventas set cobrada_en = null, cobrada_por = null, nota_cobro = null where id = %s", (venta_id,)
                )
                return _leer_venta(cur, venta_id)

    @staticmethod
    def cancelar(venta_id: int, usuario: Optional[str], motivo: Optional[str]) -> Dict[str, Any]:
        """Cancela la venta de un producto propio en una sola transacción: devuelve el stock que se descontó,
        la marca cancelada, deja el lead como «cancelado», da por atendida la solicitud pendiente de esa
        venta (ya no hay nada que gestionar) y, si el chat estaba en manos del dueño, lo devuelve a «activa».

        Devuelve la venta ya actualizada más `stock_devuelto` (unidades) y `producto_sigue_agotado` (el producto
        recuperó unidades pero sigue en estado «agotado»: reanudar es manual, igual que al agotarse)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                venta = _bloquear(cur, venta_id)
                razon = motivo_para_no_cancelar(venta)
                if razon:
                    raise AccionDeVentaNoPermitidaError(razon)

                cur.execute(
                    "select producto_sku, stock_descontado from ventas_lineas where venta_id = %s order by id", (venta_id,)
                )
                devuelto = 0
                sigue_agotado = False
                for sku, descontado in cur.fetchall():
                    if not descontado:
                        continue
                    cur.execute(
                        """
                        update productos_bot set
                            stock_ultimo = coalesce(stock_ultimo, 0) + %s, stock_actualizado_en = now(), actualizado_en = now()
                        where sku = %s
                        returning stock_ultimo, estado
                        """,
                        (descontado, sku),
                    )
                    fila = cur.fetchone()
                    if fila is not None:
                        devuelto += descontado
                        sigue_agotado = sigue_agotado or (fila[1] == "agotado" and fila[0] > 0)

                cur.execute(
                    """
                    update ventas set estado = 'cancelada', cancelada_en = now(), cancelada_por = %s, motivo_cancelacion = %s
                    where id = %s
                    """,
                    (usuario, motivo, venta_id),
                )
                if venta["lead_id"] is not None:
                    cur.execute("update leads set estado = 'cancelado', actualizado_en = now() where id = %s", (venta["lead_id"],))
                    fijar_temperatura(
                        cur, venta["lead_id"], PERDIDO, ORIGEN_REGLA, motivo or "Venta cancelada", usuario, motivo_perdida="otro"
                    )

                nota = "Venta cancelada" + (f": {motivo}" if motivo else ".")
                cur.execute(
                    """
                    update solicitudes_gestion set
                        estado = 'atendida', atendida_por = %s, nota_atencion = %s, atendida_en = now(), actualizada_en = now()
                    where venta_id = %s and estado = 'pendiente'
                    returning conversacion_id
                    """,
                    (usuario, nota, venta_id),
                )
                for (conversacion_id,) in cur.fetchall():
                    cur.execute(
                        "update conversaciones set estado = 'activa', actualizada_en = now() "
                        "where id = %s and estado = 'en_gestion'",
                        (conversacion_id,),
                    )

                resultado = _leer_venta(cur, venta_id)
                resultado["stock_devuelto"] = devuelto
                resultado["producto_sigue_agotado"] = sigue_agotado
                return resultado


_COLUMNAS_RESUMEN = (
    "v.id, v.estado, v.lead_id, v.conversacion_id, v.total, v.cobrada_en, v.cobrada_por, v.nota_cobro, "
    "v.cancelada_en, v.cancelada_por, v.motivo_cancelacion, pr.cierre as proveedor_cierre"
)


def _leer_venta(cur, venta_id: int) -> Optional[Dict[str, Any]]:
    cur.execute(
        f"select {_COLUMNAS_RESUMEN} from ventas v join proveedores pr on pr.id = v.proveedor_id where v.id = %s",
        (venta_id,),
    )
    fila = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], fila)) if fila else None


def _bloquear(cur, venta_id: int) -> Dict[str, Any]:
    """Lee la venta bloqueando su fila hasta que termine la transacción: dos acciones a la vez sobre la misma
    venta se hacen una tras otra (la segunda ya ve el resultado de la primera)."""
    cur.execute(
        f"select {_COLUMNAS_RESUMEN} from ventas v join proveedores pr on pr.id = v.proveedor_id "
        "where v.id = %s for update of v",
        (venta_id,),
    )
    fila = cur.fetchone()
    if fila is None:
        raise VentaNoEncontradaError(venta_id)
    return dict(zip([d[0] for d in cur.description], fila))
