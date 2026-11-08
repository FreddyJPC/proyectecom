"""Categorías de producto (ADR-012): repositorio contra la base real y capa HTTP."""
import pytest
import responses

from src.app import create_app
from src.config.database import get_connection
from src.routes.categorias.repository import CategoriaRepository as Repo, CategoriaYaExisteError
from tests.conftest import AUTH_HEADER, mock_login_ok

PREFIJO = "TEST-CAT "


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from productos_bot where nombre like %s", (PREFIJO + "%",))
            cur.execute("delete from categorias_producto where nombre like %s", (PREFIJO + "%",))


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestRepositorio:
    def test_crear_y_listar_con_conteo_de_productos(self):
        categoria = Repo.crear(PREFIJO + "Calzado")
        asignadas = [c for c in Repo.listar() if c["id"] == categoria["id"]]
        assert asignadas == [{"id": categoria["id"], "nombre": PREFIJO + "Calzado", "activo": True, "productos": 0}]

    def test_el_nombre_no_se_repite_ni_con_otras_mayusculas_o_espacios(self):
        Repo.crear(PREFIJO + "Calzado")
        with pytest.raises(CategoriaYaExisteError):
            Repo.crear("  " + (PREFIJO + "calzado").upper() + " ")

    def test_desactivar_la_oculta_de_la_lista_normal(self):
        categoria = Repo.crear(PREFIJO + "Vieja")
        Repo.actualizar(categoria["id"], None, False)
        assert categoria["id"] not in [c["id"] for c in Repo.listar()]
        assert categoria["id"] in [c["id"] for c in Repo.listar(incluir_inactivas=True)]

    def test_renombrar_a_un_nombre_que_ya_existe_falla(self):
        Repo.crear(PREFIJO + "Uno")
        dos = Repo.crear(PREFIJO + "Dos")
        with pytest.raises(CategoriaYaExisteError):
            Repo.actualizar(dos["id"], PREFIJO + "uno", None)

    def test_actualizar_una_inexistente(self):
        assert Repo.actualizar(999_999_999, "x", None) is None


class TestHTTP:
    def test_sin_login_no(self):
        assert _client().get("/categorias-producto").status_code == 401

    @responses.activate
    def test_crear_listar_renombrar(self):
        mock_login_ok()
        c = _client()
        creada = c.post("/categorias-producto", json={"nombre": f" {PREFIJO}Ropa "}, headers=AUTH_HEADER)
        assert creada.status_code == 201 and creada.get_json()["nombre"] == PREFIJO + "Ropa"
        id_ = creada.get_json()["id"]

        mock_login_ok()
        assert any(x["id"] == id_ for x in c.get("/categorias-producto", headers=AUTH_HEADER).get_json())

        mock_login_ok()
        editada = c.patch(f"/categorias-producto/{id_}", json={"nombre": PREFIJO + "Ropa y moda"}, headers=AUTH_HEADER)
        assert editada.status_code == 200 and editada.get_json()["nombre"] == PREFIJO + "Ropa y moda"

    @responses.activate
    def test_duplicada_es_409_vacia_es_422_y_editar_inexistente_es_404(self):
        mock_login_ok()
        c = _client()
        c.post("/categorias-producto", json={"nombre": PREFIJO + "Dup"}, headers=AUTH_HEADER)
        mock_login_ok()
        assert c.post("/categorias-producto", json={"nombre": PREFIJO + "dup"}, headers=AUTH_HEADER).status_code == 409
        mock_login_ok()
        assert c.post("/categorias-producto", json={"nombre": "   "}, headers=AUTH_HEADER).status_code == 422
        mock_login_ok()
        assert c.patch("/categorias-producto/999999999", json={"nombre": "x"}, headers=AUTH_HEADER).status_code == 404
