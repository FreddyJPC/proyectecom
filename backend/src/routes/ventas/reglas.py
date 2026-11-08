"""
Reglas de «cobrar» y «cancelar» una venta (ADR-012). Lógica PURA: sin base de datos ni red, se prueba con
diccionarios (tests/unit/routes/ventas/test_reglas.py).

Cada función devuelve el MOTIVO por el que la acción no se puede hacer, o None si se puede. El motivo está
escrito para que lo lea el dueño en la pantalla.

Solo las ventas de un producto con cierre MANUAL (producto propio) se cobran y se cancelan desde aquí: una
venta de Rocketfy ya tiene su pedido real en Rocketfy, que es quien cobra y quien cancela.
"""
from typing import Any, Dict, Optional

ESTADOS_QUE_SE_PUEDEN_CANCELAR = ("por_gestionar", "gestionada")


def _es_manual(venta: Dict[str, Any]) -> bool:
    return venta.get("proveedor_cierre") == "manual"


def motivo_para_no_cobrar(venta: Dict[str, Any]) -> Optional[str]:
    if not _es_manual(venta):
        return "Las ventas de Rocketfy no se marcan aquí: el cobro lo gestiona Rocketfy."
    if venta.get("estado") == "cancelada":
        return "Esa venta está cancelada: no se puede cobrar."
    if venta.get("cobrada_en") is not None:
        return "Esa venta ya estaba marcada como cobrada."
    return None


def motivo_para_no_deshacer_cobro(venta: Dict[str, Any]) -> Optional[str]:
    if not _es_manual(venta):
        return "Las ventas de Rocketfy no se marcan aquí."
    if venta.get("cobrada_en") is None:
        return "Esa venta no estaba marcada como cobrada."
    return None


def motivo_para_no_cancelar(venta: Dict[str, Any]) -> Optional[str]:
    if not _es_manual(venta):
        return "Una venta de Rocketfy se cancela desde su pedido en Rocketfy, no desde aquí."
    if venta.get("estado") == "cancelada":
        return "Esa venta ya estaba cancelada."
    if venta.get("cobrada_en") is not None:
        # Fricción a propósito: un cobro registrado se deshace a mano para no olvidar devolver el dinero.
        return (
            "Esa venta está marcada como cobrada. Si vas a devolver el dinero, deshaz primero el cobro "
            "y luego cancélala."
        )
    if venta.get("estado") not in ESTADOS_QUE_SE_PUEDEN_CANCELAR:
        return f"Una venta en estado «{venta.get('estado')}» no se puede cancelar."
    return None


def acciones_disponibles(venta: Dict[str, Any]) -> Dict[str, bool]:
    """Qué botones muestra la pantalla para esta venta."""
    return {
        "puede_cobrar": motivo_para_no_cobrar(venta) is None,
        "puede_deshacer_cobro": motivo_para_no_deshacer_cobro(venta) is None and venta.get("estado") != "cancelada",
        "puede_cancelar": motivo_para_no_cancelar(venta) is None,
    }
