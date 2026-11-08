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


class TestNotificarAviso:
    @responses.activate
    def test_manda_titulo_y_detalle(self):
        responses.add(responses.POST, "https://api.telegram.org/bot123:ABC/sendMessage", json={"ok": True}, status=200)
        TelegramNotifier(bot_token="123:ABC", chat_id="999").notificar_aviso("🟠 Producto sin stock", "DEMO-1 tiene 0 unidades")

        cuerpo = json.loads(responses.calls[0].request.body)
        assert cuerpo["chat_id"] == "999"
        assert cuerpo["text"] == "🟠 Producto sin stock\n\nDEMO-1 tiene 0 unidades"

    @responses.activate
    def test_sin_credenciales_no_llama_ni_lanza(self):
        TelegramNotifier(bot_token=None, chat_id=None).notificar_aviso("t", "d")
        assert len(responses.calls) == 0

    @responses.activate
    def test_los_fallos_no_se_propagan(self):
        responses.add(responses.POST, "https://api.telegram.org/bot123:ABC/sendMessage", body=RequestsConnectionError("boom"))
        TelegramNotifier(bot_token="123:ABC", chat_id="999").notificar_aviso("t", "d")  # no debe lanzar

    @responses.activate
    def test_ok_false_de_telegram_no_lanza(self):
        responses.add(responses.POST, "https://api.telegram.org/bot123:ABC/sendMessage", json={"ok": False, "description": "chat not found"}, status=200)
        TelegramNotifier(bot_token="123:ABC", chat_id="999").notificar_aviso("t", "d")  # no debe lanzar


class TestAvisosDeGestion:
    """ADR-012: el timbre para el dueño cuando un cliente quiere comprar un producto propio."""

    @responses.activate
    def test_cierre_previo_dice_que_quiere_el_cliente_y_donde_verlo(self):
        responses.add(responses.POST, "https://api.telegram.org/bot123:ABC/sendMessage", json={"ok": True}, status=200)
        TelegramNotifier(bot_token="123:ABC", chat_id="999").notificar_gestion(
            "Quiere ver el producto", conversacion_id=42, telefono="593987654321", detalle="quiere verlos mañana"
        )

        texto = json.loads(responses.calls[0].request.body)["text"]
        assert texto.startswith("🟡 Cierre previo: Quiere ver el producto")
        assert "593987654321" in texto and "quiere verlos mañana" in texto and "42" in texto and "Por gestionar" in texto

    @responses.activate
    def test_pedido_cerrado_trae_todo_lo_necesario_para_gestionar_el_envio(self):
        responses.add(responses.POST, "https://api.telegram.org/bot123:ABC/sendMessage", json={"ok": True}, status=200)
        TelegramNotifier(bot_token="123:ABC", chat_id="999").notificar_pedido_cerrado(
            {
                "cliente": "Ana", "telefono": "593987654321", "direccion": "Calle 1, Cuenca, Azuay",
                "producto": "2 x Zapatos (talla 40)", "entrega": "Envío en Cuenca", "total": "62.00",
                "pago": "transferencia", "conversacion_id": 42, "aviso": "Verifica el comprobante.",
            }
        )

        texto = json.loads(responses.calls[0].request.body)["text"]
        assert texto.startswith("🟢 Pedido cerrado, gestionar envío")
        for esperado in ("Ana", "593987654321", "Calle 1, Cuenca, Azuay", "2 x Zapatos (talla 40)", "Envío en Cuenca", "$62.00", "transferencia", "Verifica el comprobante.", "42"):
            assert esperado in texto

    @responses.activate
    def test_sin_credenciales_o_con_telegram_caido_no_lanza(self):
        TelegramNotifier(bot_token=None, chat_id=None).notificar_gestion("x", 1, "593")
        TelegramNotifier(bot_token=None, chat_id=None).notificar_pedido_cerrado({})
        responses.add(responses.POST, "https://api.telegram.org/bot123:ABC/sendMessage", body=RequestsConnectionError("sin red"))
        TelegramNotifier(bot_token="123:ABC", chat_id="999").notificar_pedido_cerrado({"cliente": "Ana"})  # no debe lanzar
