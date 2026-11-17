"""Reglas puras sobre el método de pago (ADR-017). Sin base de datos: se prueban con diccionarios."""
from typing import Any, Dict

METODO_TRANSFERENCIA = "transferencia"
METODO_CONTRAENTREGA = "contraentrega"


def pago_confirmado(lead: Dict[str, Any]) -> bool:
    """¿El dueño ya confirmó que el cliente pagó por transferencia?"""
    return lead.get("metodo_pago") == METODO_TRANSFERENCIA and lead.get("estado_pago") == "confirmado"


def pedido_prepagado(lead: Dict[str, Any]) -> bool:
    """¿El pedido de Rocketfy va como YA PAGADO (`not_COD = 1`)?

    Solo cuando el cliente pagó por transferencia y el dueño lo confirmó. Si no, es contra entrega y el repartidor cobra el total.
    Mandarlo como contra entrega con el pago ya hecho haría que el cliente pague dos veces (hallazgo H0, ADR-017, regla 17)."""
    return pago_confirmado(lead)
