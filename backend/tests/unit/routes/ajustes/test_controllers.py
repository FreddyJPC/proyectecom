"""Capa HTTP de los ajustes del negocio: servicio mockeado."""
from decimal import Decimal
from unittest.mock import patch

import responses

from src.app import create_app
from src.routes.ajustes.dto import AjustesRespuestaDTO, CalibracionEnvioDTO
from src.routes.ajustes.exceptions import AjustesInvalidosError
from tests.conftest import AUTH_HEADER, mock_login_ok

SERVICIO = "src.routes.ajustes.controllers.AjustesService"
CORREO_DE_PRUEBA = "freddyjavier556@gmail.com"  # el que devuelve mock_login_ok

VALIDO = {
    "margenMinimoPct": "25", "margenObjetivoPct": "35", "envioEstimado": "5.5",
    "otrosCostosFijos": "0", "otrosCostosPct": "2.5", "redondeo": "terminado_99",
}


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _respuesta(**cambios):
    datos = dict(
        margen_minimo_pct="25.00", margen_objetivo_pct="35.00", envio_estimado="5.50", otros_costos_fijos="0.00",
        otros_costos_pct="2.50", redondeo="terminado_99", tope_redacciones_dia=20, confirmado=True,
        actualizado_por="ana@ejemplo.com",
        actualizado_en="2026-11-05T22:00:00+00:00",
        calibracion_envio=CalibracionEnvioDTO(observaciones=2, minimo="7.00", mediana="8.00", maximo="9.00"),
    )
    datos.update(cambios)
    return AjustesRespuestaDTO(**datos)


class TestVer:
    def test_sin_login_es_401(self):
        assert _client().get("/ajustes/negocio").status_code == 401
        assert _client().put("/ajustes/negocio", json=VALIDO).status_code == 401

    @responses.activate
    def test_devuelve_los_ajustes_en_camel_case_con_la_calibracion(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.obtener.return_value = _respuesta()
            resp = _client().get("/ajustes/negocio", headers=AUTH_HEADER)

        assert resp.status_code == 200
        assert resp.get_json() == {
            "margenMinimoPct": "25.00", "margenObjetivoPct": "35.00", "envioEstimado": "5.50", "otrosCostosFijos": "0.00",
            "otrosCostosPct": "2.50", "redondeo": "terminado_99", "topeRedaccionesDia": 20, "confirmado": True,
            "actualizadoPor": "ana@ejemplo.com",
            "actualizadoEn": "2026-11-05T22:00:00+00:00",
            "calibracionEnvio": {"observaciones": 2, "minimo": "7.00", "mediana": "8.00", "maximo": "9.00"},
        }

    @responses.activate
    def test_sin_calibracion_es_null(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.obtener.return_value = _respuesta(calibracion_envio=None, confirmado=False, actualizado_por=None)
            resp = _client().get("/ajustes/negocio", headers=AUTH_HEADER)
        assert resp.get_json()["calibracionEnvio"] is None and resp.get_json()["confirmado"] is False


class TestGuardar:
    @responses.activate
    def test_traduce_a_columnas_con_decimal_y_pasa_el_correo(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.guardar.return_value = _respuesta()
            resp = _client().put("/ajustes/negocio", json=VALIDO, headers=AUTH_HEADER)

        assert resp.status_code == 200
        Servicio.return_value.guardar.assert_called_once_with(
            {
                "margen_minimo_pct": Decimal("25.00"), "margen_objetivo_pct": Decimal("35.00"),
                "envio_estimado": Decimal("5.50"), "otros_costos_fijos": Decimal("0.00"),
                "otros_costos_pct": Decimal("2.50"), "redondeo": "terminado_99",
            },
            CORREO_DE_PRUEBA,
        )

    @responses.activate
    def test_el_tope_de_redacciones_es_opcional_y_se_pasa_si_viene(self):
        for cuerpo, esperado in (
            (VALIDO, None),  # un frontend viejo no lo manda: se conserva el guardado
            ({**VALIDO, "topeRedaccionesDia": 35}, 35),
        ):
            mock_login_ok()
            with patch(SERVICIO) as Servicio:
                Servicio.return_value.guardar.return_value = _respuesta(tope_redacciones_dia=esperado or 20)
                resp = _client().put("/ajustes/negocio", json=cuerpo, headers=AUTH_HEADER)
            assert resp.status_code == 200
            datos = Servicio.return_value.guardar.call_args.args[0]
            assert datos.get("tope_redacciones_dia") == esperado
            assert ("tope_redacciones_dia" in datos) == (esperado is not None)

    @responses.activate
    def test_tope_de_redacciones_fuera_de_rango_es_422(self):
        for valor in (0, -1, 201, "abc", 2.5):
            mock_login_ok()
            with patch(SERVICIO) as Servicio:
                resp = _client().put("/ajustes/negocio", json={**VALIDO, "topeRedaccionesDia": valor}, headers=AUTH_HEADER)
            assert resp.status_code == 422, valor
            Servicio.return_value.guardar.assert_not_called()

    @responses.activate
    def test_validaciones_de_entrada(self):
        invalidos = [
            {**VALIDO, "margenMinimoPct": "-1"},
            {**VALIDO, "margenMinimoPct": "100"},
            {**VALIDO, "margenObjetivoPct": "20"},  # menor que el mínimo (25)
            {**VALIDO, "margenObjetivoPct": "90", "otrosCostosPct": "10"},  # suman 100 %
            {**VALIDO, "envioEstimado": "-0.01"},
            {**VALIDO, "envioEstimado": "1001"},
            {**VALIDO, "otrosCostosFijos": "abc"},
            {**VALIDO, "otrosCostosPct": "100"},
            {**VALIDO, "redondeo": "al_dolar"},
            {k: v for k, v in VALIDO.items() if k != "envioEstimado"},  # falta un campo
        ]
        for cuerpo in invalidos:
            mock_login_ok()
            with patch(SERVICIO) as Servicio:
                resp = _client().put("/ajustes/negocio", json=cuerpo, headers=AUTH_HEADER)
            assert resp.status_code == 422, cuerpo
            assert "detalle" in resp.get_json()
            Servicio.return_value.guardar.assert_not_called()

    @responses.activate
    def test_el_mensaje_de_coherencia_apunta_al_campo(self):
        mock_login_ok()
        resp = _client().put("/ajustes/negocio", json={**VALIDO, "margenObjetivoPct": "20"}, headers=AUTH_HEADER)
        assert "margenObjetivoPct" in resp.get_json()["detalle"]

    @responses.activate
    def test_cero_es_un_valor_valido_para_envio_y_otros_costos(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.guardar.return_value = _respuesta()
            resp = _client().put(
                "/ajustes/negocio", json={**VALIDO, "envioEstimado": "0", "otrosCostosFijos": "0", "otrosCostosPct": "0"},
                headers=AUTH_HEADER,
            )
        assert resp.status_code == 200

    @responses.activate
    def test_si_la_base_rechaza_es_422_no_500(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.guardar.side_effect = AjustesInvalidosError(["Los ajustes no cumplen las reglas."])
            resp = _client().put("/ajustes/negocio", json=VALIDO, headers=AUTH_HEADER)
        assert resp.status_code == 422
