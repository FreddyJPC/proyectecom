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

    def notificar_escalado(self, conversacion_id: int, cliente: str, motivo: str, origen: str = "") -> None:
        """`cliente` ya viene listo para leer: el canal y su teléfono o identificador («WhatsApp · 593987654321»)."""
        texto = (
            "🔴 Victoria escaló una conversación\n\n"
            f"Cliente: {cliente}\n"
            f"Motivo: {motivo}\n"
            + (f"Origen: {origen}\n" if origen else "")
            + f"Conversación ID: {conversacion_id}"
        )
        self._enviar(texto, {"conversacion_id": conversacion_id}, "el escalado")

    def notificar_aviso(self, titulo: str, detalle: str) -> None:
        """Aviso genérico para el dueño (p. ej. un producto que se pausó solo
        por falta de stock). Igual que el escalado: best-effort, nunca lanza."""
        self._enviar(f"{titulo}\n\n{detalle}", {}, "un aviso")

    def notificar_gestion(self, etiqueta: str, conversacion_id: int, cliente: str, detalle: str = "", origen: str = "") -> None:
        """«Cierre previo»: el cliente mostró una intención de compra y el dueño tiene que intervenir
        (ADR-012). El registro que no se pierde es la solicitud en la base («Por gestionar»); este aviso
        es solo el timbre, por eso es best-effort como todos."""
        partes = [f"🟡 Cierre previo: {etiqueta}", "", f"Cliente: {cliente}"]
        if detalle:
            partes.append(f"Detalle: {detalle}")
        if origen:
            partes.append(f"Origen: {origen}")
        partes += [f"Conversación ID: {conversacion_id}", "", "Míralo en la app: Por gestionar."]
        self._enviar("\n".join(partes), {"conversacion_id": conversacion_id}, "una gestión pendiente")

    def notificar_pedido_cerrado(self, datos: dict) -> None:
        """El cliente cerró la compra de un producto propio: el pedido no se crea solo, hay que gestionar
        el envío. `datos` ya viene con textos listos (ver `VictoriaTools._avisar_pedido_cerrado`)."""
        lineas = [
            "🟢 Pedido cerrado, gestionar envío",
            "",
            f"Cliente: {datos.get('cliente', '—')}",
            f"Teléfono: {datos.get('telefono', '—')}",
            f"Dirección: {datos.get('direccion', '—')}",
            f"Producto: {datos.get('producto', '—')}",
            f"Entrega: {datos.get('entrega', '—')}",
            f"Total a cobrar: ${datos.get('total', '—')}",
            f"Pago: {datos.get('pago', '—')}",
        ]
        if datos.get("origen"):
            lineas.append(f"Origen: {datos['origen']}")
        if datos.get("aviso"):
            lineas.append(f"⚠️ {datos['aviso']}")
        lineas += ["", f"Conversación ID: {datos.get('conversacion_id', '—')}", "Míralo en la app: Por gestionar."]
        self._enviar("\n".join(lineas), {"conversacion_id": datos.get("conversacion_id")}, "un pedido cerrado")

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
