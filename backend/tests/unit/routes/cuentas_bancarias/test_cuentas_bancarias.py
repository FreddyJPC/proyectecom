"""Cuentas para transferir (pendiente #76): repositorio contra la base real y capa HTTP. Las cuentas de prueba son ficticias."""
import pytest
import responses

from src.app import create_app
from src.config.database import get_connection
from src.routes.cuentas_bancarias.repository import CuentaBancariaRepository as Repo, CuentaYaExisteError
from tests.conftest import AUTH_HEADER, mock_login_ok

PREFIJO = "TEST-CTA "


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from cuentas_bancarias where banco like %s", (PREFIJO + "%",))


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _datos(banco="Uno", numero="000111", **extra):
    return {"banco": PREFIJO + banco, "tipoCuenta": "Ahorros", "numero": numero, "titular": "Ana Prueba", "identificacion": "0900000000", **extra}


class TestRepositorio:
    def test_crear_y_listar_en_orden(self):
        a = Repo.crear(PREFIJO + "A", "Ahorros", "1", "Ana", "0900000000", True, None)
        b = Repo.crear(PREFIJO + "B", "Ahorros", "2", "Ana", None, True, None)
        nuestras = [c for c in Repo.listar() if c["banco"].startswith(PREFIJO)]
        assert [c["id"] for c in nuestras] == [a["id"], b["id"]]
        assert b["orden"] > a["orden"] and b["identificacion"] is None

    def test_solo_activas_deja_fuera_las_apagadas(self):
        a = Repo.crear(PREFIJO + "A", "Ahorros", "1", "Ana", None, True, None)
        Repo.actualizar(a["id"], {"activa": False})
        assert a["id"] not in [c["id"] for c in Repo.listar(solo_activas=True)]
        assert a["id"] in [c["id"] for c in Repo.listar()]

    def test_no_se_repite_banco_y_numero(self):
        Repo.crear(PREFIJO + "A", "Ahorros", "1", "Ana", None, True, None)
        with pytest.raises(CuentaYaExisteError):
            Repo.crear(PREFIJO + "A", "Corriente", "1", "Otra", None, True, None)

    def test_actualizar_solo_lo_pedido_y_quitar_la_identificacion(self):
        a = Repo.crear(PREFIJO + "A", "Ahorros", "1", "Ana", "0900000000", True, None)
        c = Repo.actualizar(a["id"], {"titular": "Ana María", "identificacion": None})
        assert c["titular"] == "Ana María" and c["identificacion"] is None and c["numero"] == "1"
        assert Repo.actualizar(999999999, {"titular": "x"}) is None

    def test_borrar(self):
        a = Repo.crear(PREFIJO + "A", "Ahorros", "1", "Ana", None, True, None)
        assert Repo.borrar(a["id"]) is True and Repo.obtener(a["id"]) is None and Repo.borrar(a["id"]) is False


class TestHTTP:
    @responses.activate
    def test_requiere_sesion(self):
        assert _client().get("/cuentas-bancarias").status_code == 401

    @responses.activate
    def test_crear_listar_editar_borrar(self):
        mock_login_ok()
        c = _client()
        r = c.post("/cuentas-bancarias", json=_datos(), headers=AUTH_HEADER)
        assert r.status_code == 201
        cuenta = r.get_json()
        assert cuenta["tipoCuenta"] == "Ahorros" and cuenta["activa"] is True
        assert any(x["id"] == cuenta["id"] for x in c.get("/cuentas-bancarias", headers=AUTH_HEADER).get_json())
        r = c.patch(f"/cuentas-bancarias/{cuenta['id']}", json={"activa": False, "identificacion": ""}, headers=AUTH_HEADER)
        assert r.status_code == 200 and r.get_json()["activa"] is False and r.get_json()["identificacion"] is None
        assert c.delete(f"/cuentas-bancarias/{cuenta['id']}", headers=AUTH_HEADER).status_code == 200
        assert c.delete(f"/cuentas-bancarias/{cuenta['id']}", headers=AUTH_HEADER).status_code == 404

    @responses.activate
    def test_datos_invalidos_y_duplicadas(self):
        mock_login_ok()
        c = _client()
        assert c.post("/cuentas-bancarias", json={"banco": "x"}, headers=AUTH_HEADER).status_code == 422
        assert c.post("/cuentas-bancarias", json={**_datos(), "banco": "  "}, headers=AUTH_HEADER).status_code == 422
        assert c.post("/cuentas-bancarias", json=_datos(), headers=AUTH_HEADER).status_code == 201
        assert c.post("/cuentas-bancarias", json=_datos(), headers=AUTH_HEADER).status_code == 409

    @responses.activate
    def test_editar_inexistente(self):
        mock_login_ok()
        assert _client().patch("/cuentas-bancarias/999999999", json={"titular": "x"}, headers=AUTH_HEADER).status_code == 404
