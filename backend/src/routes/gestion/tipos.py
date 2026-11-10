"""
Los tipos de solicitud de gestión: cada motivo por el que una conversación necesita al dueño (ADR-012).

La lista vive en el código (no en la base) para poder crecer sin migraciones. `prioridad` decide qué
tipo manda cuando una conversación ya tenía una solicitud pendiente: «pedido cerrado» nunca se
degrada a «quiere comprar». `traspasa` dice si la conversación pasa a manos del dueño (Victoria deja
de responder) o si Victoria sigue tomando los datos mientras el dueño ya está avisado.
"""
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class TipoSolicitud:
    clave: str
    etiqueta: str
    prioridad: int
    traspasa: bool
    # True = el modelo de IA puede pedirlo con la herramienta; False = lo genera el propio sistema.
    lo_pide_victoria: bool


TIPOS: Dict[str, TipoSolicitud] = {
    t.clave: t
    for t in (
        TipoSolicitud("quiere_comprar", "Quiere comprar", 1, False, True),
        TipoSolicitud("quiere_pagar", "Quiere pagar", 1, False, True),
        TipoSolicitud("pide_envio", "Pide envío o retiro", 1, False, True),
        TipoSolicitud("quiere_ver_producto", "Quiere ver el producto", 2, True, True),
        TipoSolicitud("quiere_negociar", "Quiere negociar", 2, True, True),
        TipoSolicitud("sin_cobertura", "Destino sin cobertura", 2, True, False),
        TipoSolicitud("pedido_cerrado", "Pedido cerrado", 3, True, False),
        TipoSolicitud("otro", "Otra gestión", 0, True, True),
    )
}

TIPOS_QUE_PIDE_VICTORIA: Tuple[str, ...] = tuple(t.clave for t in TIPOS.values() if t.lo_pide_victoria)
ESTADOS = ("pendiente", "atendida")

# Estados de una conversación en los que una persona está a cargo y Victoria ya no responde: la escaló
# ella misma, está «en gestión» (el dueño atiende una intención de compra o un pedido cerrado) o es «manual» (el dueño
# decidió atenderla él, con el botón «Tomar la conversación» o al escribirle al cliente desde el panel).
ESTADOS_EN_MANOS_DEL_DUENO = ("escalada", "en_gestion", "manual")


def tipo(clave: str) -> TipoSolicitud:
    """El tipo con esa clave; una clave desconocida cae en «otro» (nunca se pierde un aviso)."""
    return TIPOS.get(clave) or TIPOS["otro"]
