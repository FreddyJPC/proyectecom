import json

import pytest
import responses
from requests.exceptions import ConnectionError as RequestsConnectionError

from src.integrations.whatsapp import (
    WhatsAppAuthError,
    WhatsAppBusinessError,
    WhatsAppClient,
    WhatsAppRequestError,
)

PHONE_NUMBER_ID = "1315663381632803"
TOKEN = "token-de-prueba"
URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"


@pytest.fixture
def client():
    return WhatsAppClient(PHONE_NUMBER_ID, TOKEN)


class TestEnviarTexto:
    @responses.activate
    def test_request_generado_correctamente(self, client):
        responses.add(responses.POST, URL, json={"messages": [{"id": "wamid.HBg"}]}, status=200)

        client.enviar_texto(telefono="593987654321", mensaje="Hola, soy Victoria")

        enviado = responses.calls[0].request
        assert enviado.url == URL
        assert enviado.headers["Authorization"] == f"Bearer {TOKEN}"
        assert enviado.headers["Content-Type"] == "application/json"
        body = json.loads(enviado.body)
        assert body == {
            "messaging_product": "whatsapp",
            "to": "593987654321",
            "type": "text",
            "text": {"body": "Hola, soy Victoria"},
        }

    @responses.activate
    def test_respuesta_exitosa_parseada(self, client):
        responses.add(
            responses.POST,
            URL,
            json={
                "messaging_product": "whatsapp",
                "contacts": [{"input": "593987654321", "wa_id": "593987654321"}],
                "messages": [{"id": "wamid.HBgLNTkzOTg3NjU0MzIxFQIAERgS"}],
            },
            status=200,
        )
        data = client.enviar_texto(telefono="593987654321", mensaje="Hola")
        assert data["messages"][0]["id"] == "wamid.HBgLNTkzOTg3NjU0MzIxFQIAERgS"

    @responses.activate
    def test_401_lanza_auth_error(self, client):
        responses.add(
            responses.POST,
            URL,
            json={"error": {"message": "Error validating access token", "code": 190}},
            status=401,
        )
        with pytest.raises(WhatsAppAuthError):
            client.enviar_texto(telefono="593987654321", mensaje="Hola")

    @responses.activate
    def test_400_lanza_business_error_con_mensaje_de_meta(self, client):
        responses.add(
            responses.POST,
            URL,
            json={"error": {"message": "Recipient phone number not in allowed list", "code": 131030}},
            status=400,
        )
        with pytest.raises(WhatsAppBusinessError) as exc_info:
            client.enviar_texto(telefono="000", mensaje="Hola")
        assert exc_info.value.code == 131030
        assert "allowed list" in exc_info.value.message

    @responses.activate
    def test_timeout_lanza_request_error(self, client):
        responses.add(responses.POST, URL, body=RequestsConnectionError("timeout simulado"))
        with pytest.raises(WhatsAppRequestError):
            client.enviar_texto(telefono="593987654321", mensaje="Hola")

    @responses.activate
    def test_respuesta_no_json_lanza_request_error(self, client):
        responses.add(responses.POST, URL, body="<html>no soy json</html>", status=200)
        with pytest.raises(WhatsAppRequestError):
            client.enviar_texto(telefono="593987654321", mensaje="Hola")

    @responses.activate
    def test_5xx_lanza_request_error(self, client):
        responses.add(responses.POST, URL, json={"error": {"message": "Internal error"}}, status=500)
        with pytest.raises(WhatsAppRequestError):
            client.enviar_texto(telefono="593987654321", mensaje="Hola")


class TestEnviarPlantilla:
    @responses.activate
    def test_request_generado_correctamente(self, client):
        responses.add(responses.POST, URL, json={"messages": [{"id": "wamid.abc"}]}, status=200)

        client.enviar_plantilla(
            telefono="593987654321",
            nombre_plantilla="confirmacion_pedido_web",
            variables=["Juan", "Mouse óptico LED"],
        )

        body = json.loads(responses.calls[0].request.body)
        assert body["type"] == "template"
        assert body["template"]["name"] == "confirmacion_pedido_web"
        assert body["template"]["language"] == {"code": "es"}
        assert body["template"]["components"][0]["parameters"] == [
            {"type": "text", "text": "Juan"},
            {"type": "text", "text": "Mouse óptico LED"},
        ]


class TestMarcarComoLeido:
    @responses.activate
    def test_request_generado_correctamente(self, client):
        responses.add(responses.POST, URL, json={"success": True}, status=200)

        client.marcar_como_leido(wamid="wamid.HBgLNTkzOTg3NjU0MzIxFQIAERgS")

        body = json.loads(responses.calls[0].request.body)
        assert body == {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": "wamid.HBgLNTkzOTg3NjU0MzIxFQIAERgS",
        }
