"""
Reglas puras de los recordatorios al dueño (pendiente #76): cuándo toca volver a avisarle que un chat que Victoria le pasó sigue sin
atender. Sin base de datos ni parámetros: todo entra como valor y sale como valor, para probarlo a fondo.

«Sin atender» = el dueño no ha abierto el chat (lo decide la consulta del repositorio con `vista_en`); estas reglas solo deciden el
momento: el primer recordatorio a los N minutos de quedar pendiente, los siguientes cada M minutos, con un máximo y solo dentro del
horario de Ecuador. Si un recordatorio le toca de madrugada, no se pierde: sale apenas empieza el horario.
"""
from datetime import datetime
from typing import Optional

from src.jobs.seguimiento.reglas import dentro_del_horario


def toca_recordatorio(
    pendiente_desde: datetime,
    enviados: int,
    ultimo_en: Optional[datetime],
    ahora: datetime,
    minutos_primero: int,
    minutos_entre: int,
    maximo: int,
    hora_desde: int,
    hora_hasta: int,
) -> bool:
    if enviados >= maximo:
        return False
    if not dentro_del_horario(ahora, hora_desde, hora_hasta):
        return False
    if enviados == 0 or ultimo_en is None:
        return (ahora - pendiente_desde).total_seconds() >= minutos_primero * 60
    return (ahora - ultimo_en).total_seconds() >= minutos_entre * 60


def tiempo_legible(minutos: float) -> str:
    """'20 min', '1 h 5 min', '3 h', '2 días': cuánto lleva esperando el cliente, para leerlo de un vistazo."""
    total = max(int(minutos), 0)
    if total < 60:
        return f"{total} min"
    horas, resto = divmod(total, 60)
    if horas < 24:
        return f"{horas} h" if resto == 0 else f"{horas} h {resto} min"
    dias = horas // 24
    return f"{dias} día" if dias == 1 else f"{dias} días"
