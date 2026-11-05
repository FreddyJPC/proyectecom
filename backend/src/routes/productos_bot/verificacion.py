"""
Qué le falta a un producto para poder estar activo (que Victoria lo venda), y
qué cosas conviene que el dueño sepa aunque no lo impidan. Lógica pura, sin
base de datos ni red: se prueba con diccionarios (ver
tests/unit/routes/productos_bot/test_verificacion.py).

Dos clases de resultado:
- BLOQUEOS: el producto no puede publicarse (o una edición lo dejaría peor si
  ya está activo). Son errores seguros: precio imposible, datos que faltan,
  SKU que no existe en Rocketfy, sin stock.
- AVISOS: se puede publicar igual, pero con conocimiento de causa.

La parte de "disponibilidad" (el SKU existe, hay stock) se separa del
"contenido" a propósito: editar la descripción de un producto activo que se
quedó sin stock no debe quedar bloqueado por eso.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from src.integrations.rocketfy import RECAUDO_MINIMO_CONTRAENTREGA

METODOS_PAGO_VALIDOS = ("contraentrega", "transferencia")
STOCK_BAJO = 5
LARGO_DESCRIPCION_LARGA = 1200


@dataclass
class Verificacion:
    bloqueos: List[str]
    avisos: List[str]


def metodos_de_pago(texto: Optional[str]) -> List[str]:
    """'contraentrega, transferencia' -> ['contraentrega', 'transferencia']."""
    if not texto:
        return []
    vistos: List[str] = []
    for parte in texto.split(","):
        metodo = parte.strip().lower()
        if metodo and metodo not in vistos:
            vistos.append(metodo)
    return vistos


def piso_de_precio(costo: Optional[Decimal]) -> Decimal:
    """El precio más bajo razonable: no vender por debajo del costo y respetar
    el recaudo mínimo de Rocketfy en contraentrega. Todavía NO suma el envío
    (Rocketfy no tiene cotizador); la calculadora de la Fase C lo afinará."""
    return max(costo or Decimal("0.00"), RECAUDO_MINIMO_CONTRAENTREGA)


def _dinero(valor: Decimal) -> str:
    return f"{valor:.2f}"


def bloqueos_de_contenido(producto: dict) -> List[str]:
    bloqueos: List[str] = []

    if not (producto.get("nombre") or "").strip():
        bloqueos.append("Falta el nombre del producto.")
    if not (producto.get("descripcion") or "").strip():
        bloqueos.append("Falta la descripción de ventas: es lo que Victoria sabe del producto.")
    if not (producto.get("tiempo_entrega") or "").strip():
        bloqueos.append("Falta el tiempo de entrega.")

    metodos = metodos_de_pago(producto.get("metodos_pago_aceptados"))
    if not metodos:
        bloqueos.append("Falta elegir al menos un método de pago.")
    for metodo in metodos:
        if metodo not in METODOS_PAGO_VALIDOS:
            bloqueos.append(f"Método de pago no reconocido: '{metodo}'.")

    if int(producto.get("max_unidades_por_pedido") or 0) < 1:
        bloqueos.append("Las unidades máximas por pedido deben ser al menos 1.")

    precio = producto.get("precio")
    if precio is None or Decimal(str(precio)) <= 0:
        bloqueos.append("El precio de venta debe ser mayor que cero.")
    else:
        precio = Decimal(str(precio))
        costo = producto.get("costo_rocketfy")
        piso = piso_de_precio(Decimal(str(costo)) if costo is not None else None)
        if precio < piso:
            bloqueos.append(
                f"El precio (${_dinero(precio)}) está por debajo del mínimo (${_dinero(piso)}): "
                f"Rocketfy exige al menos ${_dinero(RECAUDO_MINIMO_CONTRAENTREGA)} en contraentrega "
                "y no conviene vender por debajo del costo."
            )

    return bloqueos


def bloqueos_de_disponibilidad(existe_en_rocketfy: Optional[bool], stock: Optional[int]) -> List[str]:
    bloqueos: List[str] = []
    if existe_en_rocketfy is False:
        bloqueos.append("El SKU no existe en el catálogo de Rocketfy: Rocketfy rechazaría los pedidos.")
    if stock is not None and stock <= 0:
        bloqueos.append("No hay stock en Rocketfy (0 unidades).")
    return bloqueos


def avisos_de(producto: dict, stock: Optional[int]) -> List[str]:
    avisos: List[str] = []

    if "transferencia" in metodos_de_pago(producto.get("metodos_pago_aceptados")):
        avisos.append(
            "Incluye pago por transferencia: Victoria no puede ver imágenes, así que pasará la "
            "conversación a una persona para verificar el comprobante."
        )
    if stock is not None and 0 < stock <= STOCK_BAJO:
        avisos.append(f"Quedan pocas unidades en Rocketfy ({stock}).")
    if not (producto.get("preguntas_frecuentes") or "").strip():
        avisos.append(
            "No tiene preguntas frecuentes: si el cliente pregunta algo que no está en la ficha, "
            "Victoria pasará la conversación a una persona."
        )
    if len(producto.get("descripcion") or "") > LARGO_DESCRIPCION_LARGA:
        avisos.append(
            "La descripción es muy larga: va en cada mensaje que procesa Victoria. Conviene acortarla."
        )
    if (producto.get("variantes") or "").strip():
        avisos.append(
            "Tiene variantes: hoy viajan como texto en el nombre de la línea del pedido (el SKU es el "
            "mismo). Revisa tú la primera venta."
        )
    if int(producto.get("max_unidades_por_pedido") or 1) > 1:
        avisos.append(
            "Permite más de una unidad por pedido: el envío de varias unidades puede costar más y bajar "
            "tu ganancia. Conviene probarlo con un pedido de prueba."
        )

    return avisos


def verificar_producto(
    producto: dict, existe_en_rocketfy: Optional[bool] = None, stock: Optional[int] = None
) -> Verificacion:
    """`stock` en vivo (si se consultó Rocketfy ahora); si no, se usa el último
    guardado en el producto. `existe_en_rocketfy=None` significa "no se
    consultó": no bloquea."""
    stock_efectivo = stock if stock is not None else producto.get("stock_ultimo")
    return Verificacion(
        bloqueos=bloqueos_de_contenido(producto) + bloqueos_de_disponibilidad(existe_en_rocketfy, stock_efectivo),
        avisos=avisos_de(producto, stock_efectivo),
    )
