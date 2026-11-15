"""Reglas puras del aviso de ventas a Meta (ADR-016): cuándo una venta cuenta como confirmada y cuánto esperar entre reintentos."""
from typing import Any, Dict

# Minutos que se esperan antes del reintento n.º 1, 2, 3...: crece de a poco para no insistir contra un problema que tarda.
_MINUTOS_POR_INTENTO = 15


def venta_confirmada(venta: Dict[str, Any]) -> bool:
    """¿La venta ya está confirmada para avisarle a Meta?

    - Con pedido de Rocketfy: el pedido se crea y se confirma en un solo paso al cerrar (y una transferencia solo cierra cuando el dueño
      confirmó el pago), así que tener `id_pedido_rocketfy` ya es estar confirmada.
    - Producto propio (cierre manual, sin pedido de Rocketfy): cuenta cuando el dueño la marca cobrada (`cobrada_en`).
    - Una venta cancelada nunca cuenta (Meta no permite borrar un evento ya enviado: por eso se espera un rato antes de avisar).
    """
    if venta.get("estado") == "cancelada":
        return False
    return venta.get("id_pedido_rocketfy") is not None or venta.get("cobrada_en") is not None


def minutos_para_reintentar(intentos_hechos: int) -> int:
    return _MINUTOS_POR_INTENTO * max(1, int(intentos_hechos))
