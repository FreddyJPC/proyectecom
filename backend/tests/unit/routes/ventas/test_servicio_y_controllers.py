"""Cobrar y cancelar una venta (ADR-012): el servicio con repositorio falso y la capa HTTP."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import responses

from src.app import create_app
from src.routes.ventas.exceptions import AccionDeVentaNoPermitidaError, VentaNoEncontradaError
from src.routes.ventas.servicio import VentasService
from tests.conftest import AUTH_HEADER, mock_login_ok

AHORA = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def _venta(**cambios):
    venta = {
        "id": 5, "estado": "gestionada", "lead_id": 3, "conversacion_id": 7, "total": Decimal("62.00"),
        "cobrada_en": None, "cobrada_por": None, "nota_cobro": None,
        "cancelada_en": None, "cancelada_por": None, "motivo_cancelacion": None, "proveedor_cierre": "manual",
    }
    venta.update(cambios)
    return venta


class RepoFalso:
    def __init__(self, resultado=None, error=None):
        self.resultado, self.error, self.llamadas = resultado or _venta(), error, []

    def _responder(self, nombre, *args):
        self.llamadas.append((nombre, *args))
        if self.error:
            raise self.error
        return self.resultado

    def cobrar(self, venta_id, usuario, nota):
        return self._responder("cobrar", venta_id, usuario, nota)

    def deshacer_cobro(self, venta_id):
        return self._responder("deshacer_cobro", venta_id)

    def cancelar(self, venta_id, usuario, motivo):
        return self._responder("cancelar", venta_id, usuario, motivo)


def _servicio(repo):
    return VentasService(repo=repo, ajustes_service=object())


class TestServicio:
    def test_cobrar_recorta_la_nota_y_traduce_para_la_app(self):
        repo = RepoFalso(_venta(cobrada_en=AHORA, cobrada_por="ana@ejemplo.com", nota_cobro="Transferencia"))

        dto = _servicio(repo).cobrar(5, "ana@ejemplo.com", "  Transferencia  ")

        assert repo.llamadas == [("cobrar", 5, "ana@ejemplo.com", "Transferencia")]
        assert dto["cobrada"] is True and dto["cobrada_en"] == AHORA.isoformat() and dto["total"] == "62.00"
        assert (dto["puede_cobrar"], dto["puede_deshacer_cobro"], dto["puede_cancelar"]) == (False, True, False)

    def test_una_nota_vacia_o_larga(self):
        repo = RepoFalso()
        _servicio(repo).cobrar(5, "a", "   ")
        _servicio(repo).cancelar(5, "a", "x" * 900)
        assert repo.llamadas[0][3] is None and len(repo.llamadas[1][3]) == 500

    def test_cancelar_informa_el_stock_devuelto_y_si_el_producto_sigue_agotado(self):
        repo = RepoFalso(_venta(estado="cancelada", cancelada_en=AHORA, stock_devuelto=2, producto_sigue_agotado=True))

        dto = _servicio(repo).cancelar(5, "ana@ejemplo.com", "Se arrepintió")

        assert dto["estado"] == "cancelada" and dto["stock_devuelto"] == 2 and dto["producto_sigue_agotado"] is True
        assert dto["cancelada_en"] == AHORA.isoformat()
        assert (dto["puede_cobrar"], dto["puede_deshacer_cobro"], dto["puede_cancelar"]) == (False, False, False)

    def test_deshacer_el_cobro(self):
        dto = _servicio(RepoFalso(_venta())).deshacer_cobro(5)
        assert dto["cobrada"] is False and dto["puede_cobrar"] is True

    def test_un_error_del_repositorio_sube_tal_cual(self):
        import pytest

        with pytest.raises(AccionDeVentaNoPermitidaError):
            _servicio(RepoFalso(error=AccionDeVentaNoPermitidaError("ya estaba cancelada"))).cancelar(5, "a", None)


SERVICIO = "src.routes.ventas.controllers.VentasService"


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestHTTP:
    def test_sin_login_no_se_puede_nada(self):
        client = _client()
        for ruta in ("cobrar", "cancelar", "deshacer-cobro"):
            assert client.post(f"/ventas/5/{ruta}", json={}).status_code == 401

    @responses.activate
    def test_cobrar_pasa_el_correo_y_la_nota_y_responde_en_camel_case(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.cobrar.return_value = VentasService._a_dto(_venta(cobrada_en=AHORA, cobrada_por="x"))
            r = _client().post("/ventas/5/cobrar", json={"nota": "Transferencia"}, headers=AUTH_HEADER)

        assert r.status_code == 200
        cuerpo = r.get_json()
        assert cuerpo["cobrada"] is True and cuerpo["cobradaEn"] == AHORA.isoformat() and cuerpo["puedeDeshacerCobro"] is True
        servicio.return_value.cobrar.assert_called_once_with(5, "freddyjavier556@gmail.com", "Transferencia")

    @responses.activate
    def test_cancelar_pasa_el_motivo(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.cancelar.return_value = VentasService._a_dto(
                _venta(estado="cancelada", cancelada_en=AHORA, stock_devuelto=2, producto_sigue_agotado=False)
            )
            r = _client().post("/ventas/5/cancelar", json={"motivo": "Se arrepintió"}, headers=AUTH_HEADER)

        assert r.status_code == 200
        assert r.get_json()["stockDevuelto"] == 2 and r.get_json()["estado"] == "cancelada"
        servicio.return_value.cancelar.assert_called_once_with(5, "freddyjavier556@gmail.com", "Se arrepintió")

    @responses.activate
    def test_deshacer_cobro(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.deshacer_cobro.return_value = VentasService._a_dto(_venta())
            r = _client().post("/ventas/5/deshacer-cobro", headers=AUTH_HEADER)
        assert r.status_code == 200 and r.get_json()["cobrada"] is False

    @responses.activate
    def test_inexistente_es_404_y_una_accion_no_permitida_es_409_con_el_motivo(self):
        for ruta in ("cobrar", "cancelar", "deshacer-cobro"):
            mock_login_ok()
            with patch(SERVICIO) as servicio:
                for metodo in ("cobrar", "cancelar", "deshacer_cobro"):
                    getattr(servicio.return_value, metodo).side_effect = VentaNoEncontradaError(99)
                assert _client().post(f"/ventas/99/{ruta}", json={}, headers=AUTH_HEADER).status_code == 404
            mock_login_ok()
            with patch(SERVICIO) as servicio:
                for metodo in ("cobrar", "cancelar", "deshacer_cobro"):
                    getattr(servicio.return_value, metodo).side_effect = AccionDeVentaNoPermitidaError("Esa venta ya estaba cancelada.")
                r = _client().post(f"/ventas/5/{ruta}", json={}, headers=AUTH_HEADER)
                assert r.status_code == 409 and r.get_json()["error"] == "Esa venta ya estaba cancelada."

    @responses.activate
    def test_un_motivo_demasiado_largo_es_422(self):
        mock_login_ok()
        with patch(SERVICIO):
            r = _client().post("/ventas/5/cancelar", json={"motivo": "x" * 501}, headers=AUTH_HEADER)
        assert r.status_code == 422
