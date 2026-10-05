from unittest.mock import patch

import pytest

TOKEN = "token-secreto-de-prueba"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ROCKETFY_WEBHOOK_TOKEN", TOKEN)
    from src.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestAutenticacion:
    def test_token_incorrecto_devuelve_403(self, client):
        resp = client.post("/webhooks/rocketfy/token-equivocado", json={"order_id": 1})
        assert resp.status_code == 403

    def test_token_correcto_pero_cuerpo_vacio_responde_200_ping(self, client):
        resp = client.post(f"/webhooks/rocketfy/{TOKEN}")
        assert resp.status_code == 200
        assert resp.get_json()["ping"] is True

    def test_metodo_get_no_permitido(self, client):
        resp = client.get(f"/webhooks/rocketfy/{TOKEN}")
        assert resp.status_code == 405


class TestProcesamiento:
    def test_evento_valido_delega_al_servicio_y_responde_200(self, client):
        with patch("src.routes.webhooks.controllers.WebhookService") as MockService:
            instancia = MockService.return_value
            resp = client.post(
                f"/webhooks/rocketfy/{TOKEN}",
                json={
                    "order_id": 9315702,
                    "status_id": 8,
                    "event_date": "2026-08-23T19:32:10.000000Z",
                    "shopify_order_id": 100245,
                },
            )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        instancia.procesar_evento.assert_called_once()
