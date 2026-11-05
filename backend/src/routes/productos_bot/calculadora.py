"""
Calculadora de precio (Fase C del plan de gestión de productos, sección 7 de
docs/PLAN_GESTION_PRODUCTOS.md). Lógica PURA y solo con `Decimal` (el dinero
nunca es float): se prueba con números, sin base de datos ni red (ver
tests/unit/routes/productos_bot/test_calculadora.py).

Los números los calcula código, no un LLM: esto es lo que la app le muestra al
dueño como "precio recomendado".

Vocabulario:
- Margen = ganancia / precio de venta (no recargo sobre el costo). Con costo
  total $15 y margen 25 %, el precio es 15 / 0.75 = $20.00, no 15 × 1.25.
- Costo por unidad = costo de Rocketfy + envío estimado + otros costos fijos
  + otros costos en % del precio (comisiones, empaques…).
- Piso = el menor precio con el que se puede publicar (ver
  verificacion.piso_de_precio).

Límite honesto: el envío es un ESTIMADO del dueño (Rocketfy no tiene
cotizador de flete). Por eso lo que sale de aquí es una recomendación, no una
promesa de ganancia.
"""
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import List, Optional

from src.routes.ajustes.dto import AjustesNegocio

from .verificacion import piso_de_precio

CENTAVO = Decimal("0.01")
DECIMO = Decimal("0.1")
CIEN = Decimal("100")
NOVENTA_Y_NUEVE = Decimal("0.99")


@dataclass
class Nivel:
    clave: str  # minimo | recomendado | premium
    nombre: str
    precio: Decimal
    ganancia: Decimal
    margen_pct: Decimal


@dataclass
class Evaluacion:
    """Qué pasa con un precio concreto (el que está escribiendo el dueño)."""

    precio: Decimal
    ganancia: Decimal
    margen_pct: Decimal
    bajo_piso: bool
    bajo_margen_minimo: bool


@dataclass
class Recomendacion:
    costo: Optional[Decimal]
    piso: Decimal
    niveles: List[Nivel] = field(default_factory=list)
    evaluacion: Optional[Evaluacion] = None
    avisos: List[str] = field(default_factory=list)


def _dinero(valor: Decimal) -> str:
    return f"{valor.quantize(CENTAVO, rounding=ROUND_HALF_UP):.2f}"


def envio_para_piso(ajustes: AjustesNegocio) -> Optional[Decimal]:
    """El envío que cuenta para BLOQUEAR una publicación: solo el que el dueño
    ya confirmó. El de partida sirve para recomendar, no para impedir."""
    return ajustes.envio_estimado if ajustes.confirmado else None


def siguiente_terminado_99(x: Decimal) -> Decimal:
    """El menor valor de la forma k.99 (k entero) que es mayor o igual que x.
    20.00 -> 20.99; 23.08 -> 23.99; 20.99 -> 20.99; 20.995 -> 21.99."""
    k = (x - NOVENTA_Y_NUEVE).to_integral_value(rounding=ROUND_CEILING)
    if k < 0:
        k = Decimal("0")
    return (k + NOVENTA_Y_NUEVE).quantize(CENTAVO)


def redondear_precio(x: Decimal, redondeo: str) -> Decimal:
    """Siempre hacia ARRIBA: redondear hacia abajo recortaría el margen."""
    x = x.quantize(CENTAVO, rounding=ROUND_CEILING)
    return siguiente_terminado_99(x) if redondeo == "terminado_99" else x


def ganancia_por_unidad(precio: Decimal, costo: Decimal, ajustes: AjustesNegocio) -> Decimal:
    ganancia = (
        precio
        - costo
        - ajustes.envio_estimado
        - ajustes.otros_costos_fijos
        - precio * ajustes.otros_costos_pct / CIEN
    )
    return ganancia.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def margen_pct(precio: Decimal, ganancia: Decimal) -> Decimal:
    if precio <= 0:
        return Decimal("0.0")
    return (ganancia / precio * CIEN).quantize(DECIMO, rounding=ROUND_HALF_UP)


def precio_para_margen(costo: Decimal, ajustes: AjustesNegocio, margen_objetivo_pct: Decimal) -> Optional[Decimal]:
    """Precio SIN redondear con el que, tras todos los costos, queda ese
    margen: (costo + envío + fijos) / (1 − margen − otros %). `None` si los
    porcentajes suman 100 % o más (no habría precio que alcance)."""
    divisor = Decimal("1") - margen_objetivo_pct / CIEN - ajustes.otros_costos_pct / CIEN
    if divisor <= 0:
        return None
    return (costo + ajustes.envio_estimado + ajustes.otros_costos_fijos) / divisor


def _nivel(clave: str, nombre: str, precio: Decimal, costo: Decimal, ajustes: AjustesNegocio) -> Nivel:
    ganancia = ganancia_por_unidad(precio, costo, ajustes)
    return Nivel(clave, nombre, precio, ganancia, margen_pct(precio, ganancia))


def _nivel_por_margen(
    clave: str, nombre: str, costo: Decimal, ajustes: AjustesNegocio, margen: Decimal, piso: Decimal
) -> Optional[Nivel]:
    crudo = precio_para_margen(costo, ajustes, margen)
    if crudo is None:
        return None
    # Nunca por debajo del piso (p. ej. el recaudo mínimo de $10 de Rocketfy).
    precio = redondear_precio(max(crudo, piso), ajustes.redondeo)
    return _nivel(clave, nombre, precio, costo, ajustes)


def recomendar(
    costo: Optional[Decimal],
    precio_sugerido: Optional[Decimal],
    ajustes: AjustesNegocio,
    precio_evaluado: Optional[Decimal] = None,
    precio_competencia: Optional[Decimal] = None,
) -> Recomendacion:
    piso = piso_de_precio(costo, envio_para_piso(ajustes))
    resultado = Recomendacion(costo=costo, piso=piso)

    if costo is None:
        resultado.avisos.append(
            "Todavía no hay costo de Rocketfy guardado para este producto: pulsa «Actualizar desde Rocketfy» "
            "para poder calcular el precio."
        )
        return resultado

    minimo = _nivel_por_margen("minimo", "Mínimo", costo, ajustes, ajustes.margen_minimo_pct, piso)
    recomendado = _nivel_por_margen("recomendado", "Recomendado", costo, ajustes, ajustes.margen_objetivo_pct, piso)
    if minimo is None or recomendado is None:
        resultado.avisos.append(
            "Tus márgenes y otros costos en porcentaje suman 100 % o más: no existe un precio que los alcance. "
            "Revisa tus ajustes de precios."
        )
        return resultado

    resultado.niveles = [minimo, recomendado]

    if precio_sugerido is not None and precio_sugerido > 0:
        if precio_sugerido > recomendado.precio:
            resultado.niveles.append(_nivel("premium", "Premium", precio_sugerido, costo, ajustes))
        elif minimo.precio > precio_sugerido:
            resultado.avisos.append(
                f"Aun con tu margen mínimo, el precio (${_dinero(minimo.precio)}) queda por encima del sugerido por "
                f"Rocketfy (${_dinero(precio_sugerido)}): vendiendo al sugerido ganarías menos de tu margen mínimo."
            )
        elif recomendado.precio > precio_sugerido:
            resultado.avisos.append(
                f"Para tu margen objetivo el precio recomendado (${_dinero(recomendado.precio)}) queda por encima del "
                f"sugerido por Rocketfy (${_dinero(precio_sugerido)}): puede costarte competitividad."
            )

    if precio_evaluado is not None and precio_evaluado > 0:
        ganancia = ganancia_por_unidad(precio_evaluado, costo, ajustes)
        margen = margen_pct(precio_evaluado, ganancia)
        bajo_piso = precio_evaluado < piso
        bajo_margen = (ganancia / precio_evaluado * CIEN) < ajustes.margen_minimo_pct
        resultado.evaluacion = Evaluacion(precio_evaluado, ganancia, margen, bajo_piso, bajo_margen)

        if bajo_piso:
            resultado.avisos.append(
                f"Con ${_dinero(precio_evaluado)} no se podrá publicar: el mínimo para publicar es ${_dinero(piso)}."
            )
        if ganancia <= 0:
            resultado.avisos.append(f"Con este precio pierdes ${_dinero(-ganancia)} por unidad (con el envío estimado).")
        elif bajo_margen:
            resultado.avisos.append(
                f"Con este precio tu margen ({margen} %) queda por debajo de tu mínimo ({ajustes.margen_minimo_pct} %)."
            )

    if precio_competencia is not None and precio_competencia > 0:
        if precio_evaluado is not None and precio_evaluado > precio_competencia:
            resultado.avisos.append(
                f"Tu precio (${_dinero(precio_evaluado)}) es mayor que el de la competencia que anotaste "
                f"(${_dinero(precio_competencia)})."
            )
        elif minimo.precio > precio_competencia:
            resultado.avisos.append(
                f"La competencia que anotaste (${_dinero(precio_competencia)}) está por debajo de tu precio mínimo "
                f"(${_dinero(minimo.precio)}): igualarla te dejaría por debajo de tu margen mínimo."
            )

    return resultado
