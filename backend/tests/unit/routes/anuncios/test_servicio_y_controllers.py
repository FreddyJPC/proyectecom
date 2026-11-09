"""El servicio de anuncios con repositorio falso, y la API HTTP (/anuncios)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import responses

from src.app import create_app
from src.routes.anuncios.exceptions import (
    AnuncioInvalidoError,
    AnuncioNoVinculadoError,
    AnuncioYaVinculadoError,
    ProductoNoExisteError,
)
from src.routes.anuncios.servicio import TEXTO_DIRECTO, AnuncioServicio, desde_de_periodo, validar_id_anuncio
from tests.conftest import AUTH_HEADER, mock_login_ok

AHORA = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


class RepoFalso:
    def __init__(self, llegadas=None, vinculo=None):
        self.llegadas = llegadas or []
        self.vinculo = vinculo
        self.vinculados = []
        self.desvinculados = []

    def llegadas_de(self, conversacion_id):
        return self.llegadas

    def vinculo_de(self, id_anuncio):
        return self.vinculo

    def vincular(self, id_anuncio, sku, nombre):
        self.vinculados.append((id_anuncio, sku, nombre))

    def desvincular(self, id_anuncio):
        self.desvinculados.append(id_anuncio)
        return self.vinculo is not None


def _servicio(repo=None, producto="existe"):
    productos = MagicMock()
    productos.obtener_por_sku.return_value = {"sku": "AUD-1", "nombre": "Audífonos Pro"} if producto == "existe" else None
    return AnuncioServicio(repo=repo or RepoFalso(), productos=productos)


class TestIdYPeriodo:
    @pytest.mark.parametrize("valido", ["23847382910", "abc-123_x.y", "A" * 64])
    def test_ids_validos(self, valido):
        assert validar_id_anuncio(f"  {valido} ") == valido

    @pytest.mark.parametrize("malo", ["", "   ", "con espacio", "a/b", "x" * 65, "ñandú", "a;drop table"])
    def test_ids_invalidos(self, malo):
        with pytest.raises(AnuncioInvalidoError):
            validar_id_anuncio(malo)

    def test_periodo(self):
        assert desde_de_periodo(None) is None and desde_de_periodo(0) is None
        assert desde_de_periodo(30, AHORA) == AHORA - timedelta(days=30)


class TestDescribirOrigen:
    def test_sin_llegadas_es_directo(self):
        assert _servicio(RepoFalso()).describir_origen(1) == TEXTO_DIRECTO

    def test_con_anuncio_muestra_titulo_e_id(self):
        repo = RepoFalso(llegadas=[{"titulo": "Audífonos Pro", "id_anuncio": "123", "creado_en": AHORA}])
        assert _servicio(repo).describir_origen(1) == "Viene de un anuncio «Audífonos Pro» (ID 123)"

    def test_si_llego_varias_veces_lo_dice(self):
        repo = RepoFalso(llegadas=[{"titulo": None, "id_anuncio": "123", "creado_en": AHORA}, {"titulo": "x", "id_anuncio": "9", "creado_en": AHORA}])
        assert "llegó 2 veces por anuncio" in _servicio(repo).describir_origen(1)

    def test_si_la_base_falla_no_lanza_y_devuelve_vacio(self):
        repo = MagicMock()
        repo.llegadas_de.side_effect = RuntimeError("sin base")
        assert _servicio(repo).describir_origen(1) == ""


class TestVincular:
    def test_vincula_un_anuncio_a_un_producto_existente(self):
        repo = RepoFalso()
        resultado = _servicio(repo).vincular(" 123 ", "AUD-1", "  Video principal ")
        assert repo.vinculados == [("123", "AUD-1", "Video principal")]
        assert resultado == {"id_anuncio": "123", "producto_sku": "AUD-1", "producto_nombre": "Audífonos Pro"}

    def test_producto_inexistente(self):
        with pytest.raises(ProductoNoExisteError):
            _servicio(producto="no existe").vincular("123", "XXX")

    def test_si_ya_esta_vinculado_a_otro_producto_pide_confirmar(self):
        repo = RepoFalso(vinculo={"producto_sku": "OTRO", "producto_nombre": "Otro producto"})
        with pytest.raises(AnuncioYaVinculadoError) as info:
            _servicio(repo).vincular("123", "AUD-1")
        assert (info.value.sku_actual, info.value.nombre_actual) == ("OTRO", "Otro producto")
        assert repo.vinculados == []

    def test_con_reasignar_cambia_el_producto(self):
        repo = RepoFalso(vinculo={"producto_sku": "OTRO", "producto_nombre": "Otro"})
        _servicio(repo).vincular("123", "AUD-1", reasignar=True)
        assert repo.vinculados == [("123", "AUD-1", None)]

    def test_vincular_al_mismo_producto_no_pide_confirmar(self):
        repo = RepoFalso(vinculo={"producto_sku": "AUD-1", "producto_nombre": "Audífonos Pro"})
        _servicio(repo).vincular("123", "AUD-1", "Nuevo nombre")
        assert repo.vinculados == [("123", "AUD-1", "Nuevo nombre")]

    def test_desvincular(self):
        _servicio(RepoFalso(vinculo={"producto_sku": "AUD-1"})).desvincular("123")
        with pytest.raises(AnuncioNoVinculadoError):
            _servicio(RepoFalso(vinculo=None)).desvincular("123")


class TestResumen:
    def test_arma_el_resumen_con_ceros_si_no_hay_datos(self):
        repo = MagicMock()
        repo.resumen_por_origen.return_value = {
            "base": None, "ventas_anuncio": {"ventas": 0, "ingresos": 0, "ganancia": 0}, "ventas_directo": {"ventas": 0, "ingresos": 0, "ganancia": 0},
        }
        resumen = _servicio(repo).resumen(30)
        assert resumen["anuncio"]["conversaciones"] == 0 and resumen["anuncios_sin_vincular"] == 0
        repo.resumen_por_origen.assert_called_once()
        assert repo.resumen_por_origen.call_args.args[0] is not None  # 30 días -> hay fecha de inicio


@pytest.fixture
def cliente():
    app = create_app()
    app.testing = True
    return app.test_client()


def _con_servicio(servicio):
    return patch("src.routes.anuncios.controllers._build_service", return_value=servicio)


class TestHttp:
    @responses.activate
    def test_toda_ruta_exige_sesion(self, cliente):
        assert cliente.get("/anuncios").status_code == 401
        assert cliente.get("/anuncios/resumen").status_code == 401
        assert cliente.put("/anuncios/123/producto", json={"sku": "A"}).status_code == 401
        assert cliente.delete("/anuncios/123/producto").status_code == 401

    @responses.activate
    def test_listar_devuelve_camelcase_y_dinero_como_texto(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.listar.return_value = [
            {
                "id_anuncio": "123", "producto_sku": None, "producto_nombre": None, "nombre_vinculo": None, "titulo": "Audífonos",
                "texto": "t", "url_anuncio": "https://fb.me/x", "tipo_origen": "ad", "tipo_media": "image", "imagen_url": None,
                "miniatura_url": None, "primera_llegada": AHORA, "ultima_llegada": AHORA, "llegadas": 2, "conversaciones": 2,
                "ventas": 1, "ingresos": Decimal("60"), "ganancia": Decimal("24.5"), "ventas_sin_costo": 0,
            }
        ]
        with _con_servicio(servicio):
            r = cliente.get("/anuncios?dias=30", headers=AUTH_HEADER)

        assert r.status_code == 200
        a = r.get_json()[0]
        assert (a["idAnuncio"], a["productoSku"], a["urlAnuncio"], a["ventasSinCosto"]) == ("123", None, "https://fb.me/x", 0)
        assert (a["ingresos"], a["ganancia"]) == ("60.00", "24.50")  # texto con 2 decimales, nunca float
        assert a["ultimaLlegada"] == AHORA.isoformat()
        servicio.listar.assert_called_once_with(30)

    @responses.activate
    def test_periodo_invalido_da_422(self, cliente):
        mock_login_ok()
        with _con_servicio(MagicMock()):
            for malo in ("45", "abc", "-7"):
                assert cliente.get(f"/anuncios?dias={malo}", headers=AUTH_HEADER).status_code == 422

    @responses.activate
    def test_sin_periodo_o_todo_es_todo_el_tiempo(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.listar.return_value = []
        with _con_servicio(servicio):
            assert cliente.get("/anuncios", headers=AUTH_HEADER).status_code == 200
            assert cliente.get("/anuncios?dias=todo", headers=AUTH_HEADER).status_code == 200
        assert [c.args[0] for c in servicio.listar.call_args_list] == [None, None]

    @responses.activate
    def test_resumen(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.resumen.return_value = {
            "anuncio": {"conversaciones": 3, "ventas": 1, "ingresos": Decimal("60"), "ganancia": Decimal("24")},
            "directo": {"conversaciones": 5, "ventas": 0, "ingresos": 0, "ganancia": 0},
            "llegadas": 4, "anuncios_activos": 2, "anuncios_sin_vincular": 1,
        }
        with _con_servicio(servicio):
            r = cliente.get("/anuncios/resumen?dias=7", headers=AUTH_HEADER)

        cuerpo = r.get_json()
        assert r.status_code == 200
        assert cuerpo["anuncio"] == {"conversaciones": 3, "ventas": 1, "ingresos": "60.00", "ganancia": "24.00"}
        assert cuerpo["directo"]["ingresos"] == "0.00"
        assert (cuerpo["llegadas"], cuerpo["anunciosActivos"], cuerpo["anunciosSinVincular"]) == (4, 2, 1)

    @responses.activate
    def test_vincular_ok(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.vincular.return_value = {"id_anuncio": "123", "producto_sku": "AUD-1", "producto_nombre": "Audífonos"}
        with _con_servicio(servicio):
            r = cliente.put("/anuncios/123/producto", json={"sku": "AUD-1", "nombre": "Video 1"}, headers=AUTH_HEADER)

        assert r.status_code == 200
        assert r.get_json() == {"idAnuncio": "123", "productoSku": "AUD-1", "productoNombre": "Audífonos"}
        servicio.vincular.assert_called_once_with("123", "AUD-1", "Video 1", False)

    @responses.activate
    def test_vincular_errores(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        with _con_servicio(servicio):
            assert cliente.put("/anuncios/123/producto", json={}, headers=AUTH_HEADER).status_code == 422
            assert cliente.put("/anuncios/123/producto", json={"sku": "A" * 70}, headers=AUTH_HEADER).status_code == 422

            servicio.vincular.side_effect = AnuncioInvalidoError("ID inválido")
            assert cliente.put("/anuncios/123/producto", json={"sku": "A"}, headers=AUTH_HEADER).status_code == 422

            servicio.vincular.side_effect = ProductoNoExisteError("XXX")
            assert cliente.put("/anuncios/123/producto", json={"sku": "XXX"}, headers=AUTH_HEADER).status_code == 404

            servicio.vincular.side_effect = AnuncioYaVinculadoError("123", "OTRO", "Otro producto")
            r = cliente.put("/anuncios/123/producto", json={"sku": "A"}, headers=AUTH_HEADER)
            assert r.status_code == 409
            assert r.get_json()["vinculadoA"] == {"sku": "OTRO", "nombre": "Otro producto"}

    @responses.activate
    def test_reasignar_llega_al_servicio(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.vincular.return_value = {"id_anuncio": "123", "producto_sku": "A", "producto_nombre": "A"}
        with _con_servicio(servicio):
            cliente.put("/anuncios/123/producto", json={"sku": "A", "reasignar": True}, headers=AUTH_HEADER)
        assert servicio.vincular.call_args.args[3] is True

    @responses.activate
    def test_desvincular(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        with _con_servicio(servicio):
            r = cliente.delete("/anuncios/123/producto", headers=AUTH_HEADER)
            assert r.status_code == 200 and r.get_json() == {"ok": True}
            servicio.desvincular.side_effect = AnuncioNoVinculadoError("123")
            assert cliente.delete("/anuncios/123/producto", headers=AUTH_HEADER).status_code == 404
