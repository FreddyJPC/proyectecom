"""
TelegramNotifier: aviso al dueño del negocio cuando Victoria escala una
conversación a atención humana.

MUY IMPORTANTE: notificar es siempre best-effort. Ni la ausencia de
credenciales (Telegram todavía no configurado) ni un fallo de red deben
propagarse -- este notificador nunca puede tumbar el flujo principal de
escalado, que es lo que de verdad importa para el negocio.
"""
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_URL_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    def __init__(self, bot_token: Optional[str], chat_id: Optional[str]):
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._advertido = False

    def notificar_escalado(self, conversacion_id: int, telefono: str, motivo: str) -> None:
        if not self._bot_token or not self._chat_id:
            if not self._advertido:
                logger.warning(
                    "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID no configurados -- "
                    "no se puede notificar el escalado (best-effort, no bloquea)"
                )
                self._advertido = True
            return

        texto = (
            "🔴 Victoria escaló una conversación\n\n"
            f"Teléfono: {telefono}\n"
            f"Motivo: {motivo}\n"
            f"Conversación ID: {conversacion_id}"
        )
        try:
            resp = requests.post(
                _URL_TEMPLATE.format(token=self._bot_token),
                json={"chat_id": self._chat_id, "text": texto},
                timeout=10,
            )
            data = resp.json()
            if not data.get("ok"):
                # Telegram responde 200 con ok=false para varios errores de
                # negocio (chat_id inválido, el bot nunca recibió /start,
                # etc.) -- no es un RequestException, hay que revisar el
                # cuerpo para no dar por enviado algo que en realidad falló.
                logger.warning(
                    "Telegram respondió sin éxito notificando el escalado: %s",
                    data.get("description", "sin detalle"),
                    extra={"conversacion_id": conversacion_id},
                )
            else:
                logger.info(
                    "Notificación de escalado enviada a Telegram (message_id=%s)",
                    data.get("result", {}).get("message_id"),
                    extra={"conversacion_id": conversacion_id},
                )
        except Exception:
            # Cualquier fallo acá (red, JSON inválido, lo que sea) es
            # best-effort a propósito -- nunca debe tumbar el escalado.
            logger.exception("Fallo notificando escalado por Telegram -- no se propaga, es best-effort")
