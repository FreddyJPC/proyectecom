"""
Calibración del costo de envío con lo que Rocketfy ya rechazó.

Cuando Rocketfy rechaza una confirmación por importe insuficiente, su mensaje
dice (mensaje real, PROGRESS.md duda #14): "El importe mínimo del pedido debe
ser el del valor de los productos + el costo del envío ($18.47)". Esa
observación se guarda en `rocketfy_minimos_observados` (Fase A). Como
mínimo = costo de los productos + envío, el ENVÍO que implica cada rechazo es

    envío = mínimo − costo del producto × cantidad

Es la única pista del flete real que hay sin un cotizador (pendiente #5). Es
orientativa: el flete depende del destino y del peso, y el dueño decide si la
adopta. Lógica pura: se prueba con diccionarios.
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Optional

from .dto import CalibracionEnvioDTO

CENTAVO = Decimal("0.01")


def _dinero(valor: Decimal) -> str:
    return f"{valor.quantize(CENTAVO, rounding=ROUND_HALF_UP):.2f}"


def calibrar_envio(observaciones: Iterable[dict]) -> Optional[CalibracionEnvioDTO]:
    """Cada observación: `minimo`, `cantidad` y `costo_rocketfy` (por unidad).
    Se descartan las que no se pueden interpretar o dan un envío que no es
    positivo (el mensaje no era del tipo esperado)."""
    envios = []
    for fila in observaciones:
        minimo, cantidad, costo = fila.get("minimo"), fila.get("cantidad"), fila.get("costo_rocketfy")
        if minimo is None or costo is None or not cantidad or int(cantidad) < 1:
            continue
        envio = Decimal(str(minimo)) - Decimal(str(costo)) * int(cantidad)
        if envio > 0:
            envios.append(envio)

    if not envios:
        return None

    envios.sort()
    medio = len(envios) // 2
    mediana = envios[medio] if len(envios) % 2 else (envios[medio - 1] + envios[medio]) / 2
    return CalibracionEnvioDTO(
        observaciones=len(envios),
        minimo=_dinero(envios[0]),
        mediana=_dinero(mediana),
        maximo=_dinero(envios[-1]),
    )
