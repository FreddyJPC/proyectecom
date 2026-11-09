"""
El resumen que se le muestra al cliente para que confirme sus datos de envío antes de cerrar la venta (lógica pura).

Lo arma el CÓDIGO con los datos guardados, no Victoria: así lo que el cliente confirma es exactamente lo que se va a
enviar (el total, la dirección…), sin que la IA invente, redondee o cambie algo al redactarlo. El dinero se muestra con
`Decimal`, nunca con `float`.
"""
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from .ubicacion import nombre_para_mostrar

_ETIQUETAS_QUE_FALTAN = (
    ("nombre_cliente", "el nombre del cliente"),
    ("direccion", "la dirección"),
    ("canton", "la ciudad (cantón)"),
    ("provincia", "la provincia"),
    ("producto_sku", "el producto"),
    ("metodo_pago", "la forma de pago"),
    ("telefono", "el teléfono"),
)

_PAGO = {"contraentrega": "Contra entrega (paga al recibir)", "transferencia": "Transferencia"}


def datos_que_faltan(lead: Dict[str, Any], producto: Optional[Dict[str, Any]]) -> List[str]:
    """Lo que todavía hay que pedirle al cliente antes de poder mostrarle el resumen."""
    faltan = [texto for campo, texto in _ETIQUETAS_QUE_FALTAN if not lead.get(campo)]
    if producto is not None and not producto.get("envio_incluido", True) and lead.get("entrega_opcion_id") is None:
        faltan.append("la opción de entrega")
    return faltan


def _dinero(valor: Any) -> str:
    try:
        return f"${Decimal(str(valor)).quantize(Decimal('0.01'))}"
    except (InvalidOperation, ValueError):
        return str(valor)


def _telefono(telefono: str) -> str:
    """593987654321 -> 0987654321 (como lo escribe un ecuatoriano)."""
    if telefono.startswith("593") and len(telefono) == 12:
        return "0" + telefono[3:]
    return telefono


def texto_de_confirmacion(lead: Dict[str, Any]) -> str:
    cantidad = int(lead.get("cantidad") or 1)
    producto = lead.get("producto_nombre") or lead.get("producto_sku") or ""
    if lead.get("producto_variante"):
        producto = f"{producto} ({lead['producto_variante']})"
    ubicacion = ", ".join(p for p in (nombre_para_mostrar(lead.get("canton")), nombre_para_mostrar(lead.get("provincia"))) if p)

    lineas = [
        "Para dejar listo su pedido, ¿me confirma por favor que estos datos están correctos para el envío?",
        "",
        f"• Nombre: {lead.get('nombre_cliente')}",
        f"• Dirección: {lead.get('direccion')} — {ubicacion}",
        f"• Teléfono: {_telefono(str(lead.get('telefono') or ''))}",
        f"• Producto: {cantidad} × {producto}",
    ]
    if lead.get("entrega_nombre"):
        costo = Decimal(str(lead.get("costo_envio") or 0))
        lineas.append(f"• Entrega: {lead['entrega_nombre']}" + (f" ({_dinero(costo)})" if costo > 0 else ""))
    lineas += [
        f"• Total a pagar: {_dinero(lead.get('total'))}",
        f"• Forma de pago: {_PAGO.get(str(lead.get('metodo_pago')), lead.get('metodo_pago'))}",
        "",
        "Si todo está bien, respóndame «sí»; si hay algo que corregir, dígame qué.",
    ]
    return "\n".join(lineas)
