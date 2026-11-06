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
        texto = (
            "🔴 Victoria escaló una conversación\n\n"
            f"Teléfono: {telefono}\n"
            f"Motivo: {motivo}\n"
            f"Conversación ID: {conversacion_id}"
        )
        self._enviar(texto, {"conversacion_id": conversacion_id}, "el escalado")

    def notificar_aviso(self, titulo: str, detalle: str) -> None:
        """Aviso genérico para el dueño (p. ej. un producto que se pausó solo
        por falta de stock). Igual que el escalado: best-effort, nunca lanza."""
        self._enviar(f"{titulo}\n\n{detalle}", {}, "un aviso")

    def _enviar(self, texto: str, extra: dict, que: str) -> None:
        if not self._bot_token or not self._chat_id:
            if not self._advertido:
                logger.warning(
                    "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID no configurados -- "
                    "no se puede notificar %s (best-effort, no bloquea)", que
                )
                self._advertido = True
            return

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
                    "Telegram respondió sin éxito notificando %s: %s",
                    que, data.get("description", "sin detalle"),
                    extra=extra,
                )
            else:
                logger.info(
                    "Notificación de %s enviada a Telegram (message_id=%s)",
                    que, data.get("result", {}).get("message_id"),
                    extra=extra,
                )
        except Exception:
            # Cualquier fallo acá (red, JSON inválido, lo que sea) es
            # best-effort a propósito -- nunca debe tumbar el flujo que avisa.
            logger.exception("Fallo notificando %s por Telegram -- no se propaga, es best-effort", que)
