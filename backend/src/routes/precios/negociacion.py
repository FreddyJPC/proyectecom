"""
El regateo (ADR-017, regla P1): el CÓDIGO decide, Victoria solo conversa. Lógica pura con `Decimal`.

Cómo regatea por defecto (estrategia «contraoferta»):
  1. El cliente pide un precio dentro del límite -> la primera vez se contraoferta el punto medio entre el precio y lo que pidió
     (redondeado hacia arriba; ej. pide $45 por algo de $50 -> $48). Si vuelve a pedir lo mismo o acepta, se acepta.
  2. Pide menos que el mínimo permitido -> se le ofrece el mínimo (sin decir que es el mínimo).
  3. Tras `rondas_maximas` contraofertas, ya no se baja más: se repite la última oferta.
Con la estrategia «aceptar», lo que pida dentro del límite se acepta directo.

El mínimo nunca se revela a Victoria antes de que haga falta ofrecerlo: así no regala todo el margen de una vez.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .reglas import CENTAVO, REDONDEO_CENTAVO, redondear_arriba

ESTRATEGIA_CONTRAOFERTA = "contraoferta"
ESTRATEGIA_ACEPTAR = "aceptar"

ACEPTA = "acepta"
CONTRAOFERTA = "contraoferta"
MINIMO = "minimo"
FIRME = "firme"
SIN_REGATEO = "sin_regateo"
YA_ES_EL_PRECIO = "ya_es_el_precio"


@dataclass(frozen=True)
class ResultadoNegociacion:
    decision: str
    precio: Decimal  # el precio acordado (acepta) o el que Victoria debe ofrecer
    rondas: int  # contraofertas hechas en total


def _contraoferta(subtotal: Decimal, pedido: Decimal, minimo: Decimal, redondeo: str) -> Decimal:
    medio = (subtotal + pedido) / 2
    propuesta = redondear_arriba(medio, redondeo)
    if propuesta >= subtotal:
        propuesta = redondear_arriba(medio, REDONDEO_CENTAVO)
    return max(propuesta, minimo)


def _oferta_minima(subtotal: Decimal, minimo: Decimal, redondeo: str) -> Decimal:
    redondeado = redondear_arriba(minimo, redondeo)
    return redondeado if redondeado < subtotal else minimo


def negociar(
    subtotal: Decimal,
    minimo: Optional[Decimal],
    pedido: Decimal,
    rondas_hechas: int = 0,
    ultima_contraoferta: Optional[Decimal] = None,
    estrategia: str = ESTRATEGIA_CONTRAOFERTA,
    redondeo: str = "dolar",
    rondas_maximas: int = 3,
) -> ResultadoNegociacion:
    pedido = Decimal(pedido).quantize(CENTAVO)
    if minimo is None or minimo >= subtotal:
        return ResultadoNegociacion(SIN_REGATEO, subtotal, rondas_hechas)
    if pedido >= subtotal:
        return ResultadoNegociacion(YA_ES_EL_PRECIO, subtotal, rondas_hechas)

    if pedido >= minimo:
        ya_contraoferto = rondas_hechas >= 1 or (ultima_contraoferta is not None and pedido >= ultima_contraoferta)
        if estrategia == ESTRATEGIA_ACEPTAR or ya_contraoferto:
            return ResultadoNegociacion(ACEPTA, pedido, rondas_hechas)
        propuesta = _contraoferta(subtotal, pedido, minimo, redondeo)
        if propuesta <= pedido:
            return ResultadoNegociacion(ACEPTA, pedido, rondas_hechas)
        return ResultadoNegociacion(CONTRAOFERTA, propuesta, rondas_hechas + 1)

    # Pide menos de lo permitido.
    if rondas_hechas >= rondas_maximas:
        return ResultadoNegociacion(FIRME, ultima_contraoferta or _oferta_minima(subtotal, minimo, redondeo), rondas_hechas)
    return ResultadoNegociacion(MINIMO, _oferta_minima(subtotal, minimo, redondeo), rondas_hechas + 1)
