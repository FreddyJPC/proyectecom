import json

import responses
from requests.exceptions import ConnectionError as RequestsConnectionError

from src.integrations.telegram.client import TelegramNotifier


class TestTelegramNotifier:
    @responses.activate
    def test_con_credenciales_hace_el_post_correcto(self):
        responses.add(
            responses.POST,
            "https://api.telegram.org/bot123:ABC/sendMessage",
            json={"ok": True},
            status=200,
        )
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="999")

        notifier.notificar_escalado(conversacion_id=42, telefono="593987654321", motivo="Cliente pidió humano")

        assert len(responses.calls) == 1
        cuerpo = json.loads(responses.calls[0].request.body)
        assert cuerpo["chat_id"] == "999"
        assert "593987654321" in cuerpo["text"]
        assert "Cliente pidió humano" in cuerpo["text"]
        assert "42" in cuerpo["text"]

    @responses.activate
    def test_sin_credenciales_no_hace_ninguna_llamada_ni_lanza(self):
        notifier = TelegramNotifier(bot_token=None, chat_id=None)

        notifier.notificar_escalado(conversacion_id=1, telefono="593999999999", motivo="prueba")

        assert len(responses.calls) == 0

    @responses.activate
    def test_respuesta_ok_false_de_telegram_se_loguea_y_no_lanza(self):
        """Telegram responde HTTP 200 con ok=false para varios errores de
        negocio (chat_id inválido, el bot nunca recibió /start, etc.) --
        no es un RequestException, así que hay que revisar el cuerpo."""
        responses.add(
            responses.POST,
            "https://api.telegram.org/bot123:ABC/sendMessage",
            json={"ok": False, "description": "Bad Request: chat not found"},
            status=200,
        )
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="999")

        notifier.notificar_escalado(conversacion_id=1, telefono="593999999999", motivo="prueba")  # no debe lanzar

    @responses.activate
    def test_fallo_de_red_no_se_propaga(self):
        responses.add(
            responses.POST,
            "https://api.telegram.org/bot123:ABC/sendMessage",
            body=RequestsConnectionError("boom"),
        )
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="999")

        notifier.notificar_escalado(conversacion_id=1, telefono="593999999999", motivo="prueba")  # no debe lanzar
