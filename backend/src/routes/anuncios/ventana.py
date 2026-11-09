"""
Las dos «ventanas» de WhatsApp de una conversación, según la regla ACTUAL de Meta (documentación de precios de la
plataforma de WhatsApp Business, vigente desde las actualizaciones del 1 de octubre de 2026):

1. **Ventana de servicio (24 h):** se abre (y se renueva a 24 h) cada vez que el cliente escribe. Solo mientras
   está abierta se puede mandar TEXTO LIBRE; fuera de ella, únicamente plantillas aprobadas.

2. **Ventana gratuita de anuncio (FEP, hasta 7 días):** si el cliente escribió tocando un anuncio de Click-to-WhatsApp
   y NOSOTROS respondemos dentro de la ventana de servicio, esa respuesta abre una ventana en la que Meta no cobra
   los mensajes (plantillas incluidas) y que puede durar hasta 7 días desde que respondimos. Es un beneficio de COSTO:
   no permite mandar texto libre fuera de las 24 h.

Antes el sistema trataba la ventana de anuncio como «72 h desde el primer mensaje» y como permiso para escribir
texto libre: eso era la regla anterior de Meta (precios por conversación, ya obsoleta). Estas funciones son PURAS
(reciben las fechas y los mensajes ya leídos): se prueban sin base de datos.

Honestidad sobre lo que no sabemos: la documentación no dice qué pasa si el cliente vuelve a tocar OTRO anuncio con
la ventana abierta. Aquí se toma la última llegada por anuncio como referencia; es solo informativo (no se usa para
decidir nada que Meta pueda rechazar).
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

HORAS_VENTANA_SERVICIO = 24
DIAS_VENTANA_GRATUITA_MAXIMA = 7

ROLES_DE_RESPUESTA = ("bot", "humano")

# Estados de la ventana gratuita
SIN_ANUNCIO = "sin_anuncio"  # el cliente nunca llegó por un anuncio
PENDIENTE = "pendiente"  # llegó por anuncio y todavía no le respondemos: la respuesta la abrirá
ABIERTA = "abierta"
CERRADA = "cerrada"  # ya venció, o no se respondió a tiempo (dentro de las 24 h de servicio)


def ventana_de_servicio(mensajes: Iterable[Dict[str, Any]], ahora: datetime) -> Tuple[bool, Optional[datetime]]:
    """(¿abierta?, cuándo se cierra). Cuenta desde el ÚLTIMO mensaje del cliente."""
    del_cliente = [m["creado_en"] for m in mensajes if m.get("rol") == "cliente"]
    if not del_cliente:
        return False, None
    cierre = max(del_cliente) + timedelta(hours=HORAS_VENTANA_SERVICIO)
    return (True, cierre) if cierre > ahora else (False, None)


def ventana_gratuita(
    llegadas_por_anuncio: Iterable[datetime], mensajes: Iterable[Dict[str, Any]], ahora: datetime
) -> Dict[str, Any]:
    """Estado de la ventana gratuita tomando la ÚLTIMA llegada por anuncio.

    Devuelve `{"estado", "expira_en", "responder_antes_de"}`:
    - `abierta`: `expira_en` = cuando respondimos + 7 días (como máximo: Meta dice «hasta 7 días»).
    - `pendiente`: aún sin responder; `responder_antes_de` = cuando se cierra la ventana de servicio.
    - `cerrada` / `sin_anuncio`: sin fechas.
    """
    llegadas: List[datetime] = sorted(llegadas_por_anuncio)
    if not llegadas:
        return {"estado": SIN_ANUNCIO, "expira_en": None, "responder_antes_de": None}
    ultima_llegada = llegadas[-1]
    mensajes_ordenados = sorted(mensajes, key=lambda m: m["creado_en"])
    del_cliente = [m["creado_en"] for m in mensajes_ordenados if m.get("rol") == "cliente"]

    # La primera respuesta nuestra desde esa llegada, SI cayó dentro de una ventana de servicio abierta
    # (a menos de 24 h del último mensaje del cliente justo antes de responder).
    for m in mensajes_ordenados:
        if m.get("rol") not in ROLES_DE_RESPUESTA or m["creado_en"] < ultima_llegada:
            continue
        respuesta = m["creado_en"]
        previos = [c for c in del_cliente if c <= respuesta]
        dentro_de_servicio = bool(previos) and respuesta - max(previos) <= timedelta(hours=HORAS_VENTANA_SERVICIO)
        if not dentro_de_servicio:
            return {"estado": CERRADA, "expira_en": None, "responder_antes_de": None}
        expira = respuesta + timedelta(days=DIAS_VENTANA_GRATUITA_MAXIMA)
        if expira > ahora:
            return {"estado": ABIERTA, "expira_en": expira, "responder_antes_de": None}
        return {"estado": CERRADA, "expira_en": None, "responder_antes_de": None}

    # Todavía no le respondemos.
    limite = max([c for c in del_cliente if c >= ultima_llegada] or [ultima_llegada]) + timedelta(hours=HORAS_VENTANA_SERVICIO)
    if limite > ahora:
        return {"estado": PENDIENTE, "expira_en": None, "responder_antes_de": limite}
    return {"estado": CERRADA, "expira_en": None, "responder_antes_de": None}
