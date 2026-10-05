import os

import responses

from src.app import create_app
from tests.conftest import AUTH_HEADER, mock_login_ok

BASE_URL = os.environ["ROCKETFY_BASE_URL"]


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestMetricasGenerales:
    @responses.activate
    def test_traduce_campos_y_agrega_aviso_de_wallet(self):
        mock_login_ok()
        responses.add(
            responses.GET,
            f"{BASE_URL}/statistics/general",
            json={
                "ok": 1,
                "code": 200,
                "message": "OK",
                "content": {
                    "orders_today": 12,
                    "orders_total_amount_today": "540.00",
                    "confirmed_today": 10,
                    "revenue_confirmed": "480.00",
                    "revenue_today": "120.00",
                    "revenue_total": "9800.00",
                    "revenue_transit": "300.00",
                    "revenue_incidence": "40.00",
                    "transit_products_cost": "150.00",
                },
            },
            status=200,
        )

        resp = _client().get("/metricas/generales", headers=AUTH_HEADER)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["pedidosHoy"] == 12
        assert body["ingresoTotal"] == "9800.00"  # sigue siendo string, no float
        assert "avisoImportante" in body
        assert "NO el saldo real" in body["avisoImportante"]

    @responses.activate
    def test_error_de_rocketfy_devuelve_502(self):
        mock_login_ok()
        responses.add(
            responses.GET,
            f"{BASE_URL}/statistics/general",
            json={"ok": 0, "code": 401, "message": "Acceso denegado"},
            status=401,
        )

        resp = _client().get("/metricas/generales", headers=AUTH_HEADER)
        assert resp.status_code == 502
