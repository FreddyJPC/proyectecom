"""
Reglas puras de precio (ADR-017): escalas por cantidad, precio por transferencia, límite de regateo, precio mínimo (piso) y
redondeos. Solo `Decimal` (el dinero nunca es float) y sin base de datos: se prueban con números.

Vocabulario:
- «Línea»: un producto con su cantidad, o una oferta (combo/promo) con las veces que se lleva.
- «Precio de lista»: precio del catálogo × cantidad, sin ningún descuento.
- «Piso»: el menor precio de los productos de un pedido con el que el dueño todavía gana su margen mínimo
  (misma fórmula que la calculadora de la ficha: `productos_bot/calculadora.py::precio_para_margen`).
"""
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Iterable, List, Optional, Sequence, Tuple

CENTAVO = Decimal("0.01")
CIEN = Decimal("100")

TIPO_PRECIO = "precio"
TIPO_PORCENTAJE = "porcentaje"
TIPO_MONTO = "monto"
TIPOS_TRANSFERENCIA = (TIPO_PRECIO, TIPO_PORCENTAJE, TIPO_MONTO)
TIPOS_REGATEO = (TIPO_PORCENTAJE, TIPO_MONTO)

REDONDEO_DOLAR = "dolar"
REDONDEO_MEDIO = "medio"
REDONDEO_CENTAVO = "centavo"


def dinero(valor) -> Decimal:
    return Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def dinero_opcional(valor) -> Optional[Decimal]:
    if valor is None or valor == "":
        return None
    return dinero(valor)


def redondear_arriba(valor: Decimal, redondeo: str) -> Decimal:
    """Siempre hacia ARRIBA (a favor del negocio): $47,50 con «dólar» -> $48."""
    if redondeo == REDONDEO_DOLAR:
        return valor.to_integral_value(rounding=ROUND_CEILING).quantize(CENTAVO)
    if redondeo == REDONDEO_MEDIO:
        return ((valor * 2).to_integral_value(rounding=ROUND_CEILING) / 2).quantize(CENTAVO)
    return valor.quantize(CENTAVO, rounding=ROUND_CEILING)


@dataclass(frozen=True)
class Escala:
    """«`cantidad` unidades por `precio_total`»."""

    cantidad: int
    precio_total: Decimal


def precio_por_cantidad(precio_unitario: Decimal, cantidad: int, escalas: Sequence[Escala]) -> Tuple[Decimal, Optional[Escala]]:
    """(precio de la línea, escala usada o None). Se usa la escala de mayor cantidad que no pase de lo pedido; si piden más que
    esa cantidad, se cobra al mismo precio por unidad de la escala. Una escala nunca encarece: si no rebaja, se usa la lista."""
    lista = dinero(Decimal(precio_unitario) * cantidad)
    aplicables = [e for e in escalas if 2 <= e.cantidad <= cantidad]
    if not aplicables:
        return lista, None
    escala = max(aplicables, key=lambda e: e.cantidad)
    if escala.cantidad == cantidad:
        precio = dinero(escala.precio_total)
    else:
        precio = dinero(Decimal(escala.precio_total) / escala.cantidad * cantidad)
    return (precio, escala) if precio < lista else (lista, None)


def precio_transferencia(precio_linea: Decimal, unidades: int, tipo: Optional[str], valor) -> Optional[Decimal]:
    """Precio de la línea si el cliente paga por transferencia, o None si no hay regla.

    - precio: precio fijo por unidad (por vez, en una oferta);
    - porcentaje: tanto por ciento menos;
    - monto: tantos dólares menos por unidad.
    Nunca devuelve más que el precio normal (la transferencia nunca encarece) ni un precio de cero o negativo."""
    if tipo not in TIPOS_TRANSFERENCIA or valor is None:
        return None
    valor = Decimal(str(valor))
    if tipo == TIPO_PRECIO:
        resultado = dinero(valor * unidades)
    elif tipo == TIPO_PORCENTAJE:
        resultado = dinero(precio_linea * (Decimal("1") - valor / CIEN))
    else:
        resultado = dinero(precio_linea - valor * unidades)
    if resultado <= 0:
        return None
    return min(resultado, precio_linea)


def limite_regateo(base: Decimal, unidades: int, tipo: Optional[str], valor) -> Decimal:
    """Cuánto se puede descontar como máximo al regatear, medido desde `base` (el precio de lista en un producto; el precio de la
    oferta en una oferta). 0 = no se regatea."""
    if tipo not in TIPOS_REGATEO or valor is None:
        return Decimal("0.00")
    valor = Decimal(str(valor))
    if tipo == TIPO_PORCENTAJE:
        return dinero(base * valor / CIEN)
    return dinero(valor * unidades)


@dataclass(frozen=True)
class AjustesPiso:
    """Lo que el piso necesita de los Ajustes del negocio."""

    confirmado: bool
    margen_minimo_pct: Decimal
    envio_estimado: Decimal
    otros_costos_fijos: Decimal
    otros_costos_pct: Decimal


def piso_del_pedido(costos: Iterable[Optional[Decimal]], ajustes: Optional[AjustesPiso]) -> Optional[Decimal]:
    """Menor precio de los productos del pedido que todavía deja el margen mínimo: (costos + un envío + fijos) / (1 − margen − otros %).

    None (no se puede saber) si los Ajustes no están confirmados, si falta el costo de algún producto o si los porcentajes suman 100 %
    o más. En ese caso el regateo queda limitado solo por el límite que el dueño puso en el producto (que es explícito)."""
    if ajustes is None or not ajustes.confirmado:
        return None
    lista: List[Optional[Decimal]] = list(costos)
    if not lista or any(c is None for c in lista):
        return None
    divisor = Decimal("1") - ajustes.margen_minimo_pct / CIEN - ajustes.otros_costos_pct / CIEN
    if divisor <= 0:
        return None
    total = sum(lista, Decimal("0")) + ajustes.envio_estimado + ajustes.otros_costos_fijos
    return (total / divisor).quantize(CENTAVO, rounding=ROUND_CEILING)
