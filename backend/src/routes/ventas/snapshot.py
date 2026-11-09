"""
La «foto» de una venta al momento de cerrarla (ADR-012): lo que se cobró y lo que costó, congelado.

Los precios y costos de un producto cambian con el tiempo; si el reporte de ganancias los leyera de
la ficha, una venta de hace un mes se calcularía con el precio de hoy. Por eso cada venta guarda sus
propios números. Lógica PURA y con `Decimal`: se prueba con diccionarios.
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from .origen import costo_unitario, flete_estimado

CENTAVO = Decimal("0.01")


def _dinero(valor: Any) -> Decimal:
    return Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _costo_envio_negocio(
    producto: Dict[str, Any], entrega: Optional[Dict[str, Any]], envio_general: Decimal
) -> Optional[Decimal]:
    """Lo que le cuesta el envío al negocio en esta venta (None si no se sabe).

    Si el cliente eligió una opción y esta dice cuánto cuesta, eso. Si el envío va incluido en el precio,
    el flete estimado de este producto (o el general). Si se cobró aparte y no se anotó el costo, no se
    inventa nada: None."""
    if entrega is not None and entrega.get("costo_negocio") is not None:
        return _dinero(entrega["costo_negocio"])
    if producto.get("envio_incluido", True):
        return _dinero(flete_estimado(producto, envio_general))
    return None


def armar_venta(
    lead: Dict[str, Any],
    producto: Dict[str, Any],
    conversacion: Optional[Dict[str, Any]],
    entrega: Optional[Dict[str, Any]],
    estado: str,
    envio_general: Decimal,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """(fila de `ventas`, filas de `ventas_lineas`) a partir del lead cerrado y el producto vendido."""
    cantidad = int(lead.get("cantidad") or 1)
    total = _dinero(lead["total"])
    costo_envio_cliente = _dinero(lead.get("costo_envio") or 0)
    subtotal = _dinero(lead["subtotal"]) if lead.get("subtotal") is not None else total - costo_envio_cliente

    costo = costo_unitario(producto)
    venta = {
        "lead_id": lead["id"],
        "conversacion_id": lead.get("conversacion_id"),
        "contacto_id": lead.get("contacto_id") or (conversacion or {}).get("contacto_id"),
        "proveedor_id": producto.get("proveedor_id") or 1,
        # ORIGEN = cómo llegó el cliente (anuncio | directo); CANAL = por dónde conversa (whatsapp | instagram | messenger).
        "origen": (conversacion or {}).get("origen") or "directo",
        "canal": (conversacion or {}).get("canal") or "whatsapp",
        "id_anuncio": (conversacion or {}).get("id_anuncio"),
        "estado": estado,
        "metodo_pago": lead.get("metodo_pago"),
        "cliente_nombre": lead.get("nombre_cliente"),
        "telefono": lead.get("telefono"),
        "direccion": lead.get("direccion"),
        "canton": lead.get("canton"),
        "provincia": lead.get("provincia"),
        # Sin una opción elegida, el envío va incluido en el precio (solo posible si el producto lo dice).
        "entrega_tipo": lead.get("entrega_tipo") or ("incluido" if producto.get("envio_incluido", True) else None),
        "entrega_nombre": lead.get("entrega_nombre")
        or ("Envío incluido en el precio" if producto.get("envio_incluido", True) else None),
        "subtotal": subtotal,
        "costo_envio_cliente": costo_envio_cliente,
        "total": total,
        "costo_productos": costo * cantidad if costo is not None else None,
        "costo_envio_negocio": _costo_envio_negocio(producto, entrega, envio_general),
        "id_pedido_local": lead.get("id_pedido_local"),
        "id_pedido_rocketfy": lead.get("id_pedido_rocketfy"),
    }
    linea = {
        "producto_sku": producto["sku"],
        "producto_nombre": lead.get("producto_nombre") or producto["nombre"],
        "variante": lead.get("producto_variante"),
        "categoria_id": producto.get("categoria_id"),
        "categoria_nombre": producto.get("categoria_nombre"),
        "cantidad": cantidad,
        "precio_unitario": _dinero(producto["precio"]),
        "costo_unitario": costo,
    }
    return venta, [linea]


def ganancia_de(venta: Dict[str, Any]) -> Optional[Decimal]:
    """Ganancia bruta de la venta: lo cobrado menos el costo de los productos y del envío. None si falta
    algún costo (no se inventa)."""
    if venta.get("costo_productos") is None or venta.get("costo_envio_negocio") is None:
        return None
    return _dinero(venta["total"]) - _dinero(venta["costo_productos"]) - _dinero(venta["costo_envio_negocio"])
