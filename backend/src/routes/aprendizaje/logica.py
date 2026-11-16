"""
«Aprendizaje de Victoria» (entrada 0.0.140): qué se guarda cada vez que Victoria se traba, no entiende, pasa la conversación a un
asesor o algo falla, para revisarlo después y mejorarla (lógica pura, sin base de datos).

Por qué se guarda así:
- `tipo` es una lista CERRADA: sirve para agrupar y medir («este mes 12 no entendió, 8 preguntas sin respuesta»).
- `motivo` es el porqué en palabras, de Victoria o del código.
- `mensaje_cliente` y un extracto de los últimos mensajes se COPIAN: los mensajes se pueden depurar y el caso debe poder
  entenderse meses después.
- `etapa` dice en qué paso de la venta pasó: muestra dónde se pierden más clientes.
"""
from typing import Any, Dict, List, Optional

# Lo que puede pasar. Los que elige Victoria al pasar a un asesor van en TIPOS_DE_VICTORIA (los demás los pone el código).
TIPOS = {
    "no_entendio": "No entendió al cliente",
    "sin_respuesta": "No tenía la respuesta",
    "fuera_de_reglas": "Pidió algo fuera de las reglas",
    "pidio_asesor": "El cliente pidió un asesor",
    "cliente_molesto": "Cliente molesto",
    "problema_pago": "Problema con el pago",
    "problema_entrega": "Problema con la entrega",
    "agencia_por_definir": "Falta definir la agencia",
    "gestion": "Producto de cierre manual",
    "cierre_frenado": "El cierre se frenó",
    "error_proveedor": "Falló el proveedor de envíos",
    "error_sistema": "Falló el sistema",
    "dueno_intervino": "El dueño tuvo que intervenir",
    "otro": "Otro motivo",
}
TIPOS_DE_VICTORIA = (
    "no_entendio", "sin_respuesta", "fuera_de_reglas", "pidio_asesor", "cliente_molesto", "problema_pago", "problema_entrega", "otro",
)
ORIGENES = ("victoria", "sistema", "dueno")
ESTADOS = ("pendiente", "revisado", "resuelto", "descartado")
ACCIONES = {
    "instrucciones": "Se cambiaron las instrucciones de Victoria",
    "ficha": "Se completó la ficha del producto",
    "parametro": "Se ajustó un parámetro",
    "sistema": "Hace falta un cambio en el sistema",
    "ninguna": "No hacía falta cambiar nada",
}

MENSAJES_DE_CONTEXTO = 8
LARGO_MAXIMO_MENSAJE = 400
LARGO_MAXIMO_MOTIVO = 1000

_ESTADOS_CERRADOS = {"despachado", "en_gestion", "cancelado"}


def tipo_valido(tipo: Optional[str], por_defecto: str = "otro") -> str:
    return tipo if tipo in TIPOS else por_defecto


def recortar(texto: Any, largo: int = LARGO_MAXIMO_MENSAJE) -> Optional[str]:
    if texto is None:
        return None
    limpio = str(texto).strip()
    if not limpio:
        return None
    return limpio if len(limpio) <= largo else limpio[: largo - 1] + "…"


def etapa_de_venta(lead: Optional[Dict[str, Any]]) -> Optional[str]:
    """En qué paso de la venta estaba la conversación (el primero que falta, en el orden natural de una venta)."""
    if not lead:
        return "producto"
    if lead.get("estado") in _ESTADOS_CERRADOS:
        return "postventa"
    if not lead.get("producto_sku"):
        return "producto"
    agencia = lead.get("tipo_entrega") == "agencia"
    if not lead.get("nombre_cliente") or not lead.get("canton") or not lead.get("provincia") or (not agencia and not lead.get("direccion")):
        return "datos"
    if agencia and not lead.get("agencia_definida_en"):
        return "entrega"
    if not lead.get("metodo_pago") or (lead.get("metodo_pago") == "transferencia" and lead.get("estado_pago") != "confirmado"):
        return "pago"
    if not lead.get("datos_confirmados_en"):
        return "confirmacion"
    return "cierre"


def extracto(mensajes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Los últimos mensajes de la conversación, recortados (sin archivos: solo lo que se dijo)."""
    salida = []
    for fila in mensajes[-MENSAJES_DE_CONTEXTO:]:
        creado = fila.get("creado_en")
        salida.append(
            {
                "rol": fila.get("rol"),
                "texto": recortar(fila.get("contenido")) or "",
                "en": creado.isoformat() if hasattr(creado, "isoformat") else creado,
            }
        )
    return salida


def ultimo_del_cliente(mensajes: List[Dict[str, Any]]) -> Optional[str]:
    for fila in reversed(mensajes):
        if fila.get("rol") == "cliente":
            return recortar(fila.get("contenido"))
    return None
