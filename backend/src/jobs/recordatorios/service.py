"""
Recordatorios al dueño (pendiente #76): vuelve a avisar por Telegram que un chat que Victoria le pasó sigue sin atender.

Por qué existe: al pasar un chat a una persona (escalada, o «en gestión» por una venta de un producto propio) el sistema avisa UNA vez.
Si ese aviso se pierde (duerme, maneja, está ocupado) el cliente espera sin que nadie lo sepa. Este trabajo, que corre cada pocos
minutos, vuelve a avisar mientras el chat siga sin abrir.

«Atendido» = el dueño abrió el chat en el panel (eso marca `vista_en`) o el chat dejó de estar en sus manos (se lo devolvió a Victoria,
lo tomó él, se cerró): en cualquiera de los dos casos deja de salir en la consulta y los recordatorios paran solos.

Valores (todos en Parámetros, grupo «Recordatorios para ti»): primer aviso a los 15 min, luego cada 30, hasta 3, entre las 8 y las 21 h de
Ecuador. Nunca lanza: es una tarea de fondo y un fallo no debe tumbar nada.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.config.parametros import parametros
from src.integrations.canales import etiqueta_de_cliente
from src.integrations.telegram import TelegramNotifier, get_telegram_notifier

from .reglas import tiempo_legible, toca_recordatorio
from .repository import RecordatoriosRepository

logger = logging.getLogger(__name__)

_MAXIMO_DEL_MENSAJE = 140


def _motivo(estado: str) -> str:
    if estado == "en_gestion":
        return "hay una gestión pendiente (un pedido o una venta que debes atender)"
    return "Victoria lo pasó a una persona"


def _recortar(texto: Optional[str]) -> str:
    limpio = " ".join((texto or "").split())
    return limpio if len(limpio) <= _MAXIMO_DEL_MENSAJE else limpio[: _MAXIMO_DEL_MENSAJE - 1] + "…"


class RecordatoriosService:
    def __init__(self, repo: Optional[RecordatoriosRepository] = None, telegram: Optional[TelegramNotifier] = None, ahora=None):
        self._repo = repo or RecordatoriosRepository()
        self._telegram = telegram or get_telegram_notifier()
        self._ahora = ahora or (lambda: datetime.now(timezone.utc))

    def ejecutar(self) -> int:
        """Manda los recordatorios que toquen y devuelve cuántos mandó."""
        if not parametros.valor("recordatorios.activo"):
            return 0
        ahora = self._ahora()
        primero = parametros.valor("recordatorios.minutos_primero")
        entre = parametros.valor("recordatorios.minutos_entre")
        maximo = parametros.valor("recordatorios.maximo")
        desde = parametros.valor("recordatorios.hora_desde")
        hasta = parametros.valor("recordatorios.hora_hasta")

        enviados = 0
        for chat in self._repo.pendientes():
            try:
                if not toca_recordatorio(chat["pendiente_desde"], chat["recordatorios_enviados"], chat["ultimo_recordatorio_en"], ahora, primero, entre, maximo, desde, hasta):
                    continue
                self._avisar(chat, ahora, maximo)
                enviados += 1
            except Exception:
                # Un chat que falla no impide avisar de los demás.
                logger.exception("No se pudo enviar el recordatorio de la conversación %s", chat.get("id"))
        return enviados

    def _avisar(self, chat: Dict[str, Any], ahora: datetime, maximo: int) -> None:
        espera = tiempo_legible((ahora - chat["pendiente_desde"]).total_seconds() / 60)
        # FRONTEND_ORIGIN es la dirección del panel (ya la usa el CORS del servidor); sin ella, la de producción.
        panel = (os.getenv("FRONTEND_ORIGIN") or "https://app.azoshopec.com").rstrip("/")
        enlace = f"{panel}/conversaciones/{chat['id']}"
        self._telegram.notificar_recordatorio(
            conversacion_id=chat["id"],
            cliente=etiqueta_de_cliente(chat["canal"], chat["id_externo"], chat.get("telefono")),
            espera=espera,
            numero=chat["recordatorios_enviados"] + 1,
            maximo=maximo,
            motivo=_motivo(chat["estado"]),
            ultimo_mensaje=_recortar(chat.get("ultimo_mensaje")),
            enlace=enlace,
        )
        # El aviso de Telegram es best-effort (no lanza): se cuenta como enviado igual, para no insistir cada pasada del trabajo.
        self._repo.registrar_envio(chat["id"])
