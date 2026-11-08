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
from src.routes.ventas.origen import controla_su_stock, costo_unitario, es_de_cierre_manual

METODOS_PAGO_VALIDOS = ("contraentrega", "transferencia")
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


def piso_de_precio(
    costo: Optional[Decimal], envio: Optional[Decimal] = None, recaudo_minimo: Decimal = RECAUDO_MINIMO_CONTRAENTREGA
) -> Decimal:
    """El precio más bajo con el que se puede publicar: el mayor entre
    `costo + envío estimado` y el recaudo mínimo de Rocketfy en contraentrega
    ($10.00). Rocketfy no tiene cotizador de flete, por eso el envío es un
    estimado del dueño (ajustes de precios, Fase C).

    `envio=None` significa "no contar el envío": es lo que se hace mientras el
    dueño no haya confirmado sus ajustes, para que un envío de PARTIDA no
    bloquee publicaciones por un número que nadie revisó.

    `recaudo_minimo`: el de Rocketfy salvo en un producto propio, que no pasa por Rocketfy (ahí es 0:
    solo importa no vender bajo el costo)."""
    return max((costo or Decimal("0.00")) + (envio or Decimal("0.00")), recaudo_minimo)


def _dinero(valor: Decimal) -> str:
    return f"{valor:.2f}"


def bloqueos_de_contenido(
    producto: dict, envio_para_piso: Optional[Decimal] = None, entregas_activas: Optional[int] = None
) -> List[str]:
    """`envio_para_piso`: el envío estimado ya confirmado por el dueño, o None
    si no se debe contar (ver `piso_de_precio`). `entregas_activas`: cuántas opciones de entrega activas
    tiene el producto (None = no se sabe: no se exige)."""
    bloqueos: List[str] = []
    propio = es_de_cierre_manual(producto)

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
        costo = costo_unitario(producto)
        recaudo = Decimal("0.00") if propio else RECAUDO_MINIMO_CONTRAENTREGA
        piso = piso_de_precio(costo, envio_para_piso, recaudo)
        if precio < piso:
            if propio:
                explicacion = (
                    f"no cubre tu costo (${_dinero(costo or Decimal('0'))})"
                    + (f" más el flete estimado (${_dinero(envio_para_piso)})" if envio_para_piso else "")
                    + "."
                )
            elif envio_para_piso:
                explicacion = (
                    f"no cubre tu costo más el envío estimado (${_dinero(envio_para_piso)}), y Rocketfy exige al "
                    f"menos ${_dinero(RECAUDO_MINIMO_CONTRAENTREGA)} en contraentrega."
                )
            else:
                explicacion = (
                    f"Rocketfy exige al menos ${_dinero(RECAUDO_MINIMO_CONTRAENTREGA)} en contraentrega "
                    "y no conviene vender por debajo del costo."
                )
            bloqueos.append(f"El precio (${_dinero(precio)}) está por debajo del mínimo (${_dinero(piso)}): {explicacion}")

    if entregas_activas is not None and not producto.get("envio_incluido", True) and entregas_activas == 0:
        bloqueos.append(
            "Falta definir el envío: agrega al menos una opción de entrega o marca que el envío va incluido en el precio."
        )

    return bloqueos


def bloqueos_de_disponibilidad(existe_en_rocketfy: Optional[bool], stock: Optional[int], propio: bool = False) -> List[str]:
    bloqueos: List[str] = []
    if existe_en_rocketfy is False:
        bloqueos.append("El SKU no existe en el catálogo de Rocketfy: Rocketfy rechazaría los pedidos.")
    if stock is not None and stock <= 0:
        bloqueos.append(
            "No hay stock (0 unidades): carga las unidades que tienes en la ficha."
            if propio
            else "No hay stock en Rocketfy (0 unidades)."
        )
    return bloqueos


def avisos_de(producto: dict, stock: Optional[int], umbral_stock_bajo: int) -> List[str]:
    """`umbral_stock_bajo` es el parámetro «Qué cuenta como stock bajo» (`stock.umbral_bajo`): se
    recibe de quien llama para que esta función siga siendo pura."""
    avisos: List[str] = []
    propio = es_de_cierre_manual(producto)

    if "transferencia" in metodos_de_pago(producto.get("metodos_pago_aceptados")):
        if propio:
            avisos.append(
                "Incluye pago por transferencia: Victoria no da cuentas ni confirma pagos. Te avisa para que "
                "tú pases los datos y verifiques el comprobante."
            )
        else:
            avisos.append(
                "Incluye pago por transferencia: Victoria no puede ver imágenes, así que pasará la "
                "conversación a una persona para verificar el comprobante."
            )
    if stock is not None and 0 < stock <= umbral_stock_bajo:
        avisos.append(f"Quedan pocas unidades ({stock})." if propio else f"Quedan pocas unidades en Rocketfy ({stock}).")
    if propio and not controla_su_stock(producto):
        avisos.append("No llevas el control de stock: Victoria siempre lo ofrecerá como disponible.")
    if propio and costo_unitario(producto) is None:
        avisos.append("No anotaste lo que te cuesta el producto: no se podrá calcular tu ganancia.")
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
        if propio:
            avisos.append(
                "Tiene variantes: el stock es el total del producto, no por talla o color. Al gestionar cada "
                "pedido, verifica tú que esa variante esté disponible."
            )
        else:
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
    producto: dict,
    existe_en_rocketfy: Optional[bool] = None,
    stock: Optional[int] = None,
    envio_para_piso: Optional[Decimal] = None,
    *,
    umbral_stock_bajo: int,
    entregas_activas: Optional[int] = None,
) -> Verificacion:
    """`stock` en vivo (si se consultó Rocketfy ahora); si no, se usa el último
    guardado en el producto. `existe_en_rocketfy=None` significa "no se
    consultó": no bloquea. Un producto propio no se compara con Rocketfy: su stock es el que lleva la
    propia app (y si no lo controla, no hay stock que exigir)."""
    propio = es_de_cierre_manual(producto)
    if propio:
        existe_en_rocketfy = None
        stock_efectivo = producto.get("stock_ultimo") if controla_su_stock(producto) else None
    else:
        stock_efectivo = stock if stock is not None else producto.get("stock_ultimo")
    return Verificacion(
        bloqueos=bloqueos_de_contenido(producto, envio_para_piso, entregas_activas)
        + bloqueos_de_disponibilidad(existe_en_rocketfy, stock_efectivo, propio),
        avisos=avisos_de(producto, stock_efectivo, umbral_stock_bajo),
    )
