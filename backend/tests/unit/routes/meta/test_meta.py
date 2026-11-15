"""
Conexión con Meta (ADR-016): el dato del dataset (variable del servidor o el que guarda el botón «Preparar Meta») y la capa HTTP.
El token nunca sale en una respuesta ni en un error. Las pruebas con base usan la desechable de pruebas y restauran lo que tocan.
"""
from unittest.mock import MagicMock, patch

import pytest
import responses

from src.app import create_app
from src.config.database import get_connection
from src.integrations.meta import MetaRechazoError, MetaRespuestaDudosaError, factory
from src.routes.meta.repository import MetaRepository
from tests.conftest import AUTH_HEADER, mock_login_ok

CLIENTE = "src.routes.meta.controllers._cliente_para_dataset"
TOKEN = "token-secreto-de-prueba-meta"


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def dataset_limpio():
    def _borrar():
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update ajustes_negocio set meta_dataset_id = null where id = 1")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select meta_dataset_id from ajustes_negocio where id = 1")
            antes = (cur.fetchone() or [None])[0]
    _borrar()
    yield
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("update ajustes_negocio set meta_dataset_id = %s where id = 1", (antes,))


class TestElDatasetUsado:
    def test_la_variable_del_servidor_manda_sobre_lo_guardado(self, monkeypatch):
        monkeypatch.setenv("META_DATASET_ID", "111")
        assert factory.dataset_id(lambda: "222") == "111"

    def test_sin_variable_se_usa_lo_que_guardo_el_boton(self, monkeypatch):
        monkeypatch.delenv("META_DATASET_ID", raising=False)
        assert factory.dataset_id(lambda: "222") == "222"

    def test_sin_nada_no_hay_dataset(self, monkeypatch):
        monkeypatch.delenv("META_DATASET_ID", raising=False)
        assert factory.dataset_id(lambda: None) is None

    def test_el_cliente_de_avisos_exige_token_cuenta_y_dataset(self, monkeypatch):
        monkeypatch.setenv("META_CAPI_TOKEN", TOKEN)
        monkeypatch.setenv("WHATSAPP_WABA_ID", "555")
        monkeypatch.delenv("META_DATASET_ID", raising=False)
        cliente, ausentes = factory.get_meta_client(lambda: None)
        assert cliente is None and len(ausentes) == 1 and "Preparar Meta" in ausentes[0]
        cliente, ausentes = factory.get_meta_client(lambda: "222")
        assert cliente is not None and ausentes == []

    def test_el_cliente_para_pedir_el_dataset_no_necesita_tenerlo(self, monkeypatch):
        monkeypatch.setenv("META_CAPI_TOKEN", TOKEN)
        monkeypatch.setenv("WHATSAPP_WABA_ID", "555")
        cliente, ausentes = factory.get_cliente_para_dataset()
        assert cliente is not None and ausentes == []

    def test_faltan_el_token_y_la_cuenta(self, monkeypatch):
        monkeypatch.delenv("META_CAPI_TOKEN", raising=False)
        monkeypatch.delenv("WHATSAPP_WABA_ID", raising=False)
        cliente, ausentes = factory.get_cliente_para_dataset()
        assert cliente is None and ausentes == ["META_CAPI_TOKEN", "WHATSAPP_WABA_ID"]


class TestLaCapaHttp:
    def test_sin_login_es_401(self):
        c = _client()
        assert c.get("/meta/estado").status_code == 401
        assert c.post("/meta/preparar").status_code == 401

    @responses.activate
    def test_el_estado_no_incluye_nunca_el_token(self, monkeypatch, dataset_limpio):
        mock_login_ok()
        monkeypatch.setenv("META_CAPI_TOKEN", TOKEN)
        monkeypatch.setenv("WHATSAPP_WABA_ID", "555")
        monkeypatch.delenv("META_DATASET_ID", raising=False)
        resp = _client().get("/meta/estado", headers=AUTH_HEADER)
        datos = resp.get_json()
        assert resp.status_code == 200
        assert datos["tokenConfigurado"] is True and datos["cuentaWhatsappConfigurada"] is True
        assert datos["datasetId"] is None and datos["listo"] is False and datos["avisosActivos"] is False
        assert set(datos["eventos"]) == {"pendiente", "enviando", "enviado", "fallido", "dudoso", "descartado"}
        assert TOKEN not in resp.get_data(as_text=True)

    @responses.activate
    def test_preparar_guarda_el_dataset_y_deja_el_estado_listo(self, monkeypatch, dataset_limpio):
        mock_login_ok()
        monkeypatch.setenv("META_CAPI_TOKEN", TOKEN)
        monkeypatch.setenv("WHATSAPP_WABA_ID", "555")
        monkeypatch.delenv("META_DATASET_ID", raising=False)
        cliente = MagicMock()
        cliente.obtener_o_crear_dataset.return_value = "7788"
        with patch(CLIENTE, return_value=(cliente, [])):
            resp = _client().post("/meta/preparar", headers=AUTH_HEADER)
        assert resp.status_code == 200 and resp.get_json() == {"datasetId": "7788"}
        assert MetaRepository.dataset_id() == "7788"
        estado = _client().get("/meta/estado", headers=AUTH_HEADER).get_json()
        assert estado["datasetId"] == "7788" and estado["listo"] is True

    @responses.activate
    def test_preparar_sin_token_explica_que_falta(self, dataset_limpio):
        mock_login_ok()
        with patch(CLIENTE, return_value=(None, ["META_CAPI_TOKEN"])):
            resp = _client().post("/meta/preparar", headers=AUTH_HEADER)
        assert resp.status_code == 409 and "META_CAPI_TOKEN" in resp.get_json()["error"]
        assert MetaRepository.dataset_id() is None

    @responses.activate
    @pytest.mark.parametrize("error,fragmento", [(MetaRechazoError("Meta rechazó la petición: sin permiso (código 200)"), "sin permiso"), (MetaRespuestaDudosaError("Se cortó la comunicación con Meta (ReadTimeout)"), "volver a intentarlo")])
    def test_si_meta_falla_se_dice_y_no_se_guarda_nada(self, error, fragmento, dataset_limpio):
        mock_login_ok()
        cliente = MagicMock()
        cliente.obtener_o_crear_dataset.side_effect = error
        with patch(CLIENTE, return_value=(cliente, [])):
            resp = _client().post("/meta/preparar", headers=AUTH_HEADER)
        assert resp.status_code == 502 and fragmento in resp.get_json()["error"]
        assert MetaRepository.dataset_id() is None


class TestElRepositorio:
    def test_guardar_y_leer_el_dataset(self, dataset_limpio):
        assert MetaRepository.dataset_id() is None
        MetaRepository.guardar_dataset_id("99887766")
        assert MetaRepository.dataset_id() == "99887766"

    def test_el_resumen_cuenta_todos_los_estados(self):
        resumen = MetaRepository.resumen_eventos()
        assert list(resumen) == ["pendiente", "enviando", "enviado", "fallido", "dudoso", "descartado"]
        assert all(isinstance(n, int) and n >= 0 for n in resumen.values())
