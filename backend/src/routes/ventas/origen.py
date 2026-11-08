"""
De dónde viene un producto y cuánto cuesta, sea de Rocketfy o propio (ADR-012).

Los productos se leen siempre con las columnas del proveedor (`proveedor_clave`, `proveedor_cierre`),
que salen del JOIN con `proveedores`. Estas funciones aceptan una fila de `productos_bot` ya leída y
son puras: se prueban con diccionarios.
"""
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

PROVEEDOR_ROCKETFY_ID = 1
PROVEEDOR_PROPIO_ID = 2
CLAVE_ROCKETFY = "rocketfy"
CLAVE_PROPIO = "propio"
CIERRE_ROCKETFY = "rocketfy"
CIERRE_MANUAL = "manual"
PREFIJO_SKU_PROPIO = "PROP-"


def es_de_cierre_manual(producto: Optional[Dict[str, Any]]) -> bool:
    """True si la venta de este producto la gestiona el dueño (no se crea un pedido en Rocketfy).
    Una fila sin datos de proveedor se trata como de Rocketfy: es el comportamiento de siempre."""
    return bool(producto) and producto.get("proveedor_cierre") == CIERRE_MANUAL


def es_propio(producto: Optional[Dict[str, Any]]) -> bool:
    return bool(producto) and producto.get("proveedor_clave") == CLAVE_PROPIO


def _decimal(valor: Any) -> Optional[Decimal]:
    if valor is None or valor == "":
        return None
    try:
        return Decimal(str(valor)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def costo_unitario(producto: Dict[str, Any]) -> Optional[Decimal]:
    """Lo que le cuesta una unidad al dueño: `costo_propio` en un producto propio, `costo_rocketfy` en
    uno de Rocketfy. None si no se conoce."""
    if es_de_cierre_manual(producto):
        return _decimal(producto.get("costo_propio"))
    return _decimal(producto.get("costo_rocketfy"))


def controla_su_stock(producto: Dict[str, Any]) -> bool:
    """True si el stock de este producto lo lleva la propia app (producto propio con control)."""
    return es_de_cierre_manual(producto) and bool(producto.get("controla_stock", True))


def flete_estimado(producto: Dict[str, Any], envio_general: Decimal) -> Decimal:
    """El flete que se resta de la ganancia al calcular precios y margen de este producto.

    - Si el envío se cobra APARTE al cliente, el flete no sale del precio: 0 (la ganancia real de cada
      venta, con lo que se cobró y lo que costó, queda guardada en `ventas`).
    - Si el precio incluye el envío y el dueño anotó el flete de ESTE producto, ese manda (un kit de 4 kg
      no cuesta lo mismo que unos audífonos).
    - Si no anotó nada, el envío estimado general."""
    if not producto.get("envio_incluido", True):
        return Decimal("0.00")
    propio = _decimal(producto.get("costo_flete_estimado"))
    return propio if propio is not None else envio_general
