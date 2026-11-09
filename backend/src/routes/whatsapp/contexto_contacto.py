"""
Lo que Victoria sabe del HISTORIAL de un cliente antes de contestarle (docs/PLAN_LEADS_CRM.md §4): es el equivalente a lo que
ve un vendedor humano en la ficha del contacto de un CRM. Sin él, un cliente que ya compró le parecería un desconocido.

Función pura: recibe el resumen que arma el repositorio y devuelve el texto que se añade al «estado del lead».
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.routes.leads.temperaturas import ETIQUETAS, GANADO, MOTIVOS_DE_PERDIDA, PERDIDO

MAXIMO_LEADS_PREVIOS = 5


def _hace(fecha: Optional[datetime], ahora: datetime) -> str:
    if fecha is None:
        return ""
    dias = max((ahora - fecha).days, 0)
    if dias == 0:
        return "hoy"
    if dias == 1:
        return "ayer"
    if dias < 30:
        return f"hace {dias} días"
    meses = dias // 30
    return f"hace {meses} {'mes' if meses == 1 else 'meses'}"


def _resultado(lead: Dict[str, Any], ahora: datetime) -> str:
    cuando = _hace(lead.get("cerrado_en") or lead.get("creado_en"), ahora)
    if lead["temperatura"] == GANADO:
        return f"lo compró {cuando}".strip()
    if lead["temperatura"] == PERDIDO:
        motivo = MOTIVOS_DE_PERDIDA.get(lead.get("motivo_perdida") or "")
        return f"no se concretó ({motivo.lower()})" if motivo else "no se concretó"
    return f"quedó {ETIQUETAS.get(lead['temperatura'], lead['temperatura']).lower()}, {cuando}".strip(", ")


def formatear_historial(
    previos: List[Dict[str, Any]], compras: int, nombre: Optional[str] = None, ahora: Optional[datetime] = None
) -> str:
    """El texto del historial, o «» si el cliente no tiene nada anterior (es la primera vez que se le atiende)."""
    ahora = ahora or datetime.now(timezone.utc)
    if not previos and compras <= 0:
        return ""
    lineas = []
    if compras > 0:
        veces = "una vez" if compras == 1 else f"{compras} veces"
        lineas.append(f"Es un cliente conocido: ya compró {veces} en la tienda.")
    else:
        lineas.append("Es un cliente conocido: ya habló antes con la tienda, aunque todavía no ha comprado.")
    if nombre:
        lineas.append(f"Su nombre es {nombre}.")
    detalle = []
    for lead in previos[:MAXIMO_LEADS_PREVIOS]:
        producto = lead.get("producto_nombre") or "un producto sin definir"
        detalle.append(f"{producto} ({_resultado(lead, ahora)})")
    if detalle:
        lineas.append("Lo que se habló antes: " + "; ".join(detalle) + ".")
    lineas.append(
        "Atiéndelo como a un cliente conocido (agradécele que vuelva y ayúdalo con lo de ahora); lo que sea de un pedido "
        "anterior (envío, reclamos, garantía, devoluciones) lo resuelve una persona: usa escalar_a_humano."
    )
    return "Historial de este cliente: " + " ".join(lineas)
