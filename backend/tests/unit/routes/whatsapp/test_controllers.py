from unittest.mock import patch

import pytest

VERIFY_TOKEN = "token-secreto-de-prueba"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", VERIFY_TOKEN)
    from src.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class _HiloSincronoFalso:
    """Sustituye threading.Thread en los tests: corre el target al toque,
    en el mismo hilo, para no tener que sincronizar con un hilo real de
    verdad solo para poder afirmar sobre el mock del servicio."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


def _payload_mensaje_texto(wamid="wamid.HBgLNTkzOTg3NjU0MzIx", telefono="593987654321", texto="Hola"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "2300889040712457",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "1315663381632803"},
                            "messages": [
                                {
                                    "id": wamid,
                                    "from": telefono,
                                    "timestamp": "1234567890",
                                    "type": "text",
                                    "text": {"body": texto},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


class TestVerificacionWebhook:
    def test_token_correcto_devuelve_challenge(self, client):
        resp = client.get(
            "/webhooks/whatsapp",
            query_string={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "12345"},
        )
        assert resp.status_code == 200
        assert resp.get_data(as_text=True) == "12345"

    def test_token_incorrecto_devuelve_403(self, client):
        resp = client.get(
            "/webhooks/whatsapp",
            query_string={"hub.mode": "subscribe", "hub.verify_token": "token-equivocado", "hub.challenge": "12345"},
        )
        assert resp.status_code == 403

    def test_sin_parametros_devuelve_403(self, client):
        resp = client.get("/webhooks/whatsapp")
        assert resp.status_code == 403


class TestRecepcionDeMensajes:
    @patch("src.routes.whatsapp.controllers.threading.Thread", _HiloSincronoFalso)
    @patch("src.routes.whatsapp.controllers.WebhookService")
    def test_payload_valido_responde_200_y_delega_al_servicio(self, MockService, client):
        resp = client.post("/webhooks/whatsapp", json=_payload_mensaje_texto())

        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
        MockService.return_value.procesar_mensaje_entrante.assert_called_once()
        dto_enviado = MockService.return_value.procesar_mensaje_entrante.call_args.args[0]
        assert dto_enviado.wamid == "wamid.HBgLNTkzOTg3NjU0MzIx"
        assert dto_enviado.telefono == "593987654321"
        assert dto_enviado.contenido == "Hola"

    @patch("src.routes.whatsapp.controllers.threading.Thread", _HiloSincronoFalso)
    @patch("src.routes.whatsapp.controllers.WebhookService")
    def test_mismo_payload_dos_veces_responde_200_las_dos_veces(self, MockService, client):
        # La idempotencia real (no reprocesar un wamid ya visto) es
        # responsabilidad de WebhookService y está probada en
        # test_services.py -- acá solo se confirma que el controller no se
        # rompe ni deja de responder 200 ante una entrega repetida de Meta.
        payload = _payload_mensaje_texto()
        resp1 = client.post("/webhooks/whatsapp", json=payload)
        resp2 = client.post("/webhooks/whatsapp", json=payload)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert MockService.return_value.procesar_mensaje_entrante.call_count == 2

    def test_payload_vacio_responde_200_sin_errores(self, client):
        resp = client.post("/webhooks/whatsapp", json={})
        assert resp.status_code == 200

    def test_payload_malformado_responde_200_sin_errores(self, client):
        resp = client.post("/webhooks/whatsapp", json={"entry": [{"changes": [{"value": "no-es-un-dict"}]}]})
        assert resp.status_code == 200

    def test_sin_cuerpo_responde_200_sin_errores(self, client):
        resp = client.post("/webhooks/whatsapp", data="", content_type="application/json")
        assert resp.status_code == 200
