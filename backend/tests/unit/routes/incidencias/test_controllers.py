from unittest.mock import patch

import responses

from src.app import create_app
from tests.conftest import AUTH_HEADER, mock_login_ok


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestEventosWebhook:
    @responses.activate
    def test_lista_eventos_y_pagina(self):
        mock_login_ok()
        with patch("src.routes.incidencias.controllers.IncidenciasService") as MockService:
            MockService.return_value.listar_eventos.return_value = {
                "items": [
                    {
                        "id": 1,
                        "id_rocketfy": 288726,
                        "shopify_order_id": 100245,
                        "status_id": 7,
                        "status_name": "Novedad",
                        "details": "Cliente no contesta",
                        "tracking_code": None,
                        "tracking_url": None,
                        "shipping_company": "Gintracom",
                        "event_date": None,
                        "recibido_en": None,
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20,
            }
            resp = _client().get("/incidencias/eventos", headers=AUTH_HEADER)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total"] == 1
        assert body["items"][0]["statusName"] == "Novedad"
        assert body["items"][0]["idLocal"] == 100245
        MockService.return_value.listar_eventos.assert_called_once_with(
            solo_incidencias=True, page=1, page_size=20
        )

    @responses.activate
    def test_todos_true_pide_el_historial_completo(self):
        mock_login_ok()
        with patch("src.routes.incidencias.controllers.IncidenciasService") as MockService:
            MockService.return_value.listar_eventos.return_value = {
                "items": [], "total": 0, "page": 1, "page_size": 20,
            }
            _client().get("/incidencias/eventos?todos=true", headers=AUTH_HEADER)

        MockService.return_value.listar_eventos.assert_called_once_with(
            solo_incidencias=False, page=1, page_size=20
        )

    def test_sin_token_devuelve_401(self):
        resp = _client().get("/incidencias/eventos")
        assert resp.status_code == 401


class TestAlertasStock:
    @responses.activate
    def test_lista_alertas(self):
        mock_login_ok()
        with patch("src.routes.incidencias.controllers.IncidenciasService") as MockService:
            MockService.return_value.listar_alertas.return_value = {
                "items": [{"id": 1, "sku": "SKU-1", "tipo": "stock_bajo", "detalle": {"stock": 2, "umbral": 5}, "creado_en": None}],
                "total": 1,
                "page": 1,
                "page_size": 20,
            }
            resp = _client().get("/incidencias/stock?sku=SKU-1", headers=AUTH_HEADER)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["items"][0]["sku"] == "SKU-1"
        MockService.return_value.listar_alertas.assert_called_once_with(sku="SKU-1", page=1, page_size=20)
