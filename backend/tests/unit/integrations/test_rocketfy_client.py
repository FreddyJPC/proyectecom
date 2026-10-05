import hashlib

import pytest
import responses
from requests.exceptions import ConnectionError as RequestsConnectionError

from src.integrations.rocketfy import (
    RocketfyAuthError,
    RocketfyBusinessError,
    RocketfyClient,
    RocketfyRequestError,
)

BASE_URL = "https://rocket-e.com/api"
EMAIL = "vendedor@ejemplo.com"
TOKEN = "token-de-prueba"


@pytest.fixture
def client():
    return RocketfyClient(BASE_URL, EMAIL, TOKEN, max_retries=2)


def _auth_headers_match(request):
    expected_user = hashlib.sha256(EMAIL.encode()).hexdigest()
    return (
        request.headers.get("Auth-user") == expected_user
        and request.headers.get("Auth-token") == TOKEN
    )


class TestAuthHeaders:
    @responses.activate
    def test_envia_auth_user_como_sha256_del_correo(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={"ok": 1, "code": 200, "message": "ok", "id": 1, "products_stock": []},
            status=200,
        )
        client.crear_pedido({"id": 1})
        enviado = responses.calls[0].request
        assert _auth_headers_match(enviado)


class TestCrearPedido:
    @responses.activate
    def test_exito_devuelve_id_y_products_stock(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={
                "ok": 1,
                "code": 200,
                "message": "El pedido se ha creado correctamente",
                "products_stock": [{"id": 4821, "stock": 137}],
                "id": 9315702,
            },
            status=200,
        )
        data = client.crear_pedido({"id": 100245, "name": "Maria"})
        assert data["id"] == 9315702
        assert data["products_stock"] == [{"id": 4821, "stock": 137}]

    @responses.activate
    def test_error_interno_405_lanza_business_error(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={"ok": 0, "code": 405, "message": "Error interno al crear el pedido"},
            status=200,
        )
        with pytest.raises(RocketfyBusinessError) as exc_info:
            client.crear_pedido({"id": 100245})
        assert exc_info.value.code == 405


class TestConfirmarPedido:
    @responses.activate
    def test_sin_cobertura_lanza_business_error_con_mensaje(self, client):
        mensaje = "No es posible confirmar este pedido con la transportadora seleccionada ya que no tiene cobertura a: Quilanga"
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/confirm",
            json={"ok": 0, "code": 401, "message": mensaje},
            status=200,
        )
        with pytest.raises(RocketfyBusinessError) as exc_info:
            client.confirmar_pedido(order_id=9315702)
        assert "cobertura" in exc_info.value.message.lower()

    @responses.activate
    def test_exito(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/confirm",
            json={"ok": 1, "code": 200, "message": "Confirmado"},
            status=200,
        )
        data = client.confirmar_pedido(order_id=9315702)
        assert data["ok"] == 1


class TestConsultarPedido:
    @responses.activate
    def test_respuesta_sin_content_expone_order(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/getInfo/9315702",
            json={
                "code": 200,
                "ok": 1,
                "order": {"id": 9315702, "order_status": "Entregado"},
                "status_record": [],
                "incidence_details": None,
            },
            status=200,
        )
        data = client.consultar_pedido(9315702)
        assert data["order"]["id"] == 9315702
        assert "content" not in data


class TestListarProductos:
    @responses.activate
    def test_desenvuelve_content(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/products/list",
            json={
                "ok": 1,
                "code": 200,
                "message": "OK",
                "content": {
                    "data": [{"id": 4821, "sku": "RLJ-DEP-001", "stock": 137}],
                    "pagination": {"total": 1, "per_page": 20, "current_page": 1, "last_page": 1},
                },
            },
            status=200,
        )
        content = client.listar_productos(q="RLJ-DEP-001")
        assert content["data"][0]["sku"] == "RLJ-DEP-001"
        assert content["pagination"]["total"] == 1


class TestErroresTransporte:
    @responses.activate
    def test_401_lanza_auth_error(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/products/list",
            json={"ok": 0, "code": 401, "message": "Acceso denegado: su usuario no tiene permisos"},
            status=401,
        )
        with pytest.raises(RocketfyAuthError):
            client.listar_productos()

    @responses.activate
    def test_respuesta_no_json_lanza_request_error(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/products/list",
            body="<html>no soy json</html>",
            status=200,
        )
        with pytest.raises(RocketfyRequestError):
            client.listar_productos()

    @responses.activate
    def test_timeout_lanza_request_error(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/products/list",
            body=RequestsConnectionError("timeout simulado"),
        )
        with pytest.raises(RocketfyRequestError):
            client.listar_productos()

    @responses.activate
    def test_mantenimiento_reintenta_y_luego_falla(self, client, monkeypatch):
        monkeypatch.setattr("src.integrations.rocketfy.client.time.sleep", lambda _: None)
        mensaje = "El servicio está temporalmente en mantenimiento"
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/confirm",
            json={"ok": 0, "code": 500, "message": mensaje},
            status=200,
        )
        with pytest.raises(RocketfyBusinessError):
            client.confirmar_pedido(order_id=1)
        # max_retries=2 -> 1 intento inicial + 2 reintentos = 3 llamadas
        assert len(responses.calls) == 3

    @responses.activate
    def test_mantenimiento_se_recupera_en_segundo_intento(self, client, monkeypatch):
        monkeypatch.setattr("src.integrations.rocketfy.client.time.sleep", lambda _: None)
        mensaje = "El servicio está temporalmente en mantenimiento"
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/confirm",
            json={"ok": 0, "code": 500, "message": mensaje},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/confirm",
            json={"ok": 1, "code": 200, "message": "Confirmado"},
            status=200,
        )
        data = client.confirmar_pedido(order_id=1)
        assert data["ok"] == 1
        assert len(responses.calls) == 2
