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
        # El origen y el anuncio son los DEL LEAD (atribución por intención de compra): un cliente que compró por un anuncio
        # y meses después vuelve solo no convierte la venta nueva en venta del anuncio. Sin esos datos en el lead (leads
        # anteriores a la migración 025), se usa lo que tenía la conversación.
        "origen": (lead.get("origen") if "origen" in lead else (conversacion or {}).get("origen")) or "directo",
        "canal": (conversacion or {}).get("canal") or "whatsapp",
        "id_anuncio": lead.get("id_anuncio") if "origen" in lead else (conversacion or {}).get("id_anuncio"),
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
        # ADR-017: sin cotización guardada (un producto a precio de lista) no hubo descuentos.
        "subtotal_lista": subtotal,
        "descuento_total": Decimal("0.00"),
        "descuentos": None,
        "cotizacion": None,
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
        "oferta_id": None,
        "precio_lista_unitario": _dinero(producto["precio"]),
    }
    return venta, [linea]


def armar_venta_cotizada(
    lead: Dict[str, Any],
    cotizacion: Dict[str, Any],
    productos: Dict[str, Dict[str, Any]],
    producto_principal: Dict[str, Any],
    conversacion: Optional[Dict[str, Any]],
    entrega: Optional[Dict[str, Any]],
    estado: str,
    envio_general: Decimal,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """La foto de una venta con la COTIZACIÓN guardada en el lead (ADR-017): varias líneas, ofertas y descuentos.

    Cada línea guarda su precio de lista y un precio «real» por unidad: lo cobrado por los productos repartido en proporción a su
    precio de lista (así la ganancia por producto refleja los descuentos). El envío al negocio se estima con el producto principal."""
    venta, _ = armar_venta(lead, producto_principal, conversacion, entrega, estado, envio_general)
    items = [i for linea in cotizacion.get("lineas") or [] for i in linea.get("items") or []]
    cobrado = _dinero(venta["subtotal"])
    lista_total = sum((_dinero(i["precio_lista_unitario"]) * int(i["cantidad"]) for i in items), Decimal("0"))
    factor = cobrado / lista_total if lista_total > 0 else Decimal("1")

    lineas: List[Dict[str, Any]] = []
    costo_total: Optional[Decimal] = Decimal("0.00")
    for item in items:
        producto = productos.get(item["sku"]) or {}
        cantidad = int(item["cantidad"])
        lista = _dinero(item["precio_lista_unitario"])
        costo = costo_unitario(producto) if producto else None
        if costo is None or costo_total is None:
            costo_total = None
        else:
            costo_total += costo * cantidad
        lineas.append(
            {
                "producto_sku": item["sku"],
                "producto_nombre": item.get("nombre") or producto.get("nombre") or item["sku"],
                "variante": item.get("variante"),
                "categoria_id": producto.get("categoria_id"),
                "categoria_nombre": producto.get("categoria_nombre"),
                "cantidad": cantidad,
                "precio_unitario": _dinero(lista * factor),
                "costo_unitario": costo,
                "oferta_id": item.get("oferta_id"),
                "precio_lista_unitario": lista,
            }
        )
    descuentos = cotizacion.get("descuentos") or []
    venta.update(
        costo_productos=costo_total,
        subtotal_lista=_dinero(cotizacion.get("subtotal_lista") or venta["subtotal"]),
        descuento_total=sum((_dinero(d["monto"]) for d in descuentos), Decimal("0.00")),
        descuentos=descuentos or None,
        cotizacion=cotizacion,
    )
    return venta, lineas


def ganancia_de(venta: Dict[str, Any]) -> Optional[Decimal]:
    """Ganancia bruta de la venta: lo cobrado menos el costo de los productos y del envío. None si falta
    algún costo (no se inventa)."""
    if venta.get("costo_productos") is None or venta.get("costo_envio_negocio") is None:
        return None
    return _dinero(venta["total"]) - _dinero(venta["costo_productos"]) - _dinero(venta["costo_envio_negocio"])
