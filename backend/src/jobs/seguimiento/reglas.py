"""
Reglas puras del seguimiento automático (docs/PLAN_LEADS_CRM.md §6): cuándo es el momento de escribirle a un cliente, en qué
horario y cuántos mensajes caben hoy. Sin base de datos ni parámetros: todo entra como valor y sale como valor, para poder
probarlo a fondo.

Las dos formas de escribir, según la regla de WhatsApp (ver routes/anuncios/ventana.py):
- EMPUJÓN: texto libre. Solo se puede dentro de las 24 h siguientes al último mensaje del cliente (gratis).
- PLANTILLA: mensaje aprobado por Meta. Lo único que se puede enviar pasadas las 24 h.
"""
import re
from datetime import datetime, timedelta, timezone

TIPO_EMPUJON = "empujon"
TIPO_PLANTILLA = "plantilla"

HORAS_VENTANA_DE_SERVICIO = 24
# El empujón se deja de enviar una hora antes de que se cierre la ventana: un envío que cae justo en el cierre puede fallar.
MARGEN_ANTES_DEL_CIERRE_HORAS = 1
# La ventana gratuita de anuncio dura hasta 7 días desde que respondimos: pasados ~9 días del último mensaje del cliente ya no
# puede estar abierta (la respuesta nuestra fue como mucho un día después de su último mensaje). Solo acota la búsqueda; la
# decisión exacta la toma `ventana_gratuita`.
DIAS_MAXIMOS_DESDE_EL_ULTIMO_MENSAJE = 9

# Ecuador no tiene horario de verano: un desfase fijo de UTC-5 basta (igual que el resto del sistema).
ZONA_ECUADOR = timezone(timedelta(hours=-5))

_NOMBRE_DE_PLANTILLA = re.compile(r"^[a-z0-9_]{1,100}$")


def hora_de_ecuador(ahora: datetime) -> int:
    return ahora.astimezone(ZONA_ECUADOR).hour


def dentro_del_horario(ahora: datetime, desde: int, hasta: int) -> bool:
    """¿Es hora de escribir? `desde` y `hasta` son horas de Ecuador (hasta no incluida). Si el rango está al revés o vacío (un
    parámetro mal puesto), NO se escribe: ante la duda, el sistema calla."""
    if desde >= hasta:
        return False
    return desde <= hora_de_ecuador(ahora) < hasta


def inicio_del_dia_de_ecuador(ahora: datetime) -> datetime:
    """Las 00:00 de Ecuador del día de `ahora`, en UTC: desde ahí se cuenta el tope diario."""
    local = ahora.astimezone(ZONA_ECUADOR).replace(hour=0, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.utc)


def horas_de_silencio(ultimo_mensaje_del_cliente: datetime, ahora: datetime) -> float:
    return (ahora - ultimo_mensaje_del_cliente).total_seconds() / 3600


def es_momento_del_empujon(ultimo_mensaje_del_cliente: datetime, ahora: datetime, horas_de_espera: int) -> bool:
    """¿Ya pasó el tiempo de espera y todavía queda ventana de 24 h (con su margen) para escribir texto libre?"""
    horas = horas_de_silencio(ultimo_mensaje_del_cliente, ahora)
    return horas_de_espera <= horas <= HORAS_VENTANA_DE_SERVICIO - MARGEN_ANTES_DEL_CIERRE_HORAS


def es_momento_de_la_plantilla(ultimo_mensaje_del_cliente: datetime, ahora: datetime) -> bool:
    """La plantilla solo se usa cuando la ventana de 24 h ya se cerró (dentro de ella basta el texto libre, que es gratis)."""
    return horas_de_silencio(ultimo_mensaje_del_cliente, ahora) > HORAS_VENTANA_DE_SERVICIO


def nombre_de_plantilla_valido(nombre: str) -> bool:
    """Meta solo admite minúsculas, números y guion bajo en el nombre de una plantilla."""
    return bool(_NOMBRE_DE_PLANTILLA.match(nombre or ""))


def cupo_restante(tope_diario: int, enviados_hoy: int) -> int:
    return max(0, tope_diario - enviados_hoy)
