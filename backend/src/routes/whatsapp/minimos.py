"""
Extrae el monto del mensaje con el que Rocketfy rechaza una confirmación por
importe insuficiente. Mensaje real recibido (PROGRESS.md, duda #14 al
proveedor):

    "El importe mínimo del pedido debe ser el del valor de los productos +
     el costo del envío ($18.47)"

Ese monto = valor de los productos + costo de envío del destino. Sin
cotizador de flete (pendiente #5) es la única forma de aprender el envío real.
Función pura y tolerante: cualquier mensaje que no calce devuelve None.
"""
import re
from decimal import Decimal
from typing import Optional

# "mínimo"/"minimo" (con o sin tilde) y luego, en cualquier punto del mensaje,
# el primer importe con signo "$".
_PATRON = re.compile(r"m[ií]nimo.*?\$\s*([0-9]+(?:[.,][0-9]{1,2})?)", re.IGNORECASE | re.DOTALL)


def extraer_minimo_rocketfy(mensaje: str) -> Optional[Decimal]:
    if not mensaje:
        return None
    coincidencia = _PATRON.search(mensaje)
    if coincidencia is None:
        return None
    return Decimal(coincidencia.group(1).replace(",", "."))
