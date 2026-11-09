"""
Capa HTTP de Parámetros. Dos niveles: con el servicio mockeado (formato de la respuesta y
códigos de error) y de punta a punta contra la base de pruebas (guardar de verdad, que el
cambio se note al instante y que restaurar vuelva al respaldo).
"""
from unittest.mock import patch

import pytest
import responses

from src.app import create_app
from src.config.database import get_connection
from src.config.parametros import ParametroDesconocidoError, ValorInvalido, parametros
from src.routes.parametros.dto import CambioDTO, GrupoDTO, OpcionDTO, ParametroDTO, ParametrosRespuestaDTO
from tests.conftest import AUTH_HEADER, mock_login_ok

SERVICIO = "src.routes.parametros.controllers.ParametrosAdminService"
CORREO_DE_PRUEBA = "freddyjavier556@gmail.com"  # el que devuelve mock_login_ok
CLAVE = "bot.max_mensajes_historial"


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _parametro(**cambios):
    datos = dict(
        clave=CLAVE, nombre="Memoria de la conversación", para_que_sirve="Cuántos mensajes se recuerdan.", tipo="entero",
        valor=40, origen="original", valor_original=40, valor_app=None, variable_servidor="BOT_MAX_MENSAJES_HISTORIAL",
        valor_servidor=None, minimo=10, maximo=100, largo_maximo=None, unidad="mensajes", aplica="Desde el siguiente mensaje.",
        sensible=False, aviso="", opciones=[], avisos=[], actualizado_por=None, actualizado_en=None,
    )
    datos.update(cambios)
    return ParametroDTO(**datos)


class TestConServicioMockeado:
    def test_sin_login_es_401(self):
        c = _client()
        assert c.get("/parametros").status_code == 401
        assert c.get("/parametros/historial").status_code == 401
        assert c.put(f"/parametros/{CLAVE}", json={"valor": 50}).status_code == 401
        assert c.delete(f"/parametros/{CLAVE}").status_code == 401

    @responses.activate
    def test_lista_en_camel_case_agrupada(self):
        mock_login_ok()
        dto = ParametrosRespuestaDTO(grupos=[GrupoDTO("victoria", "Victoria", "Cómo trabaja.", [
            _parametro(opciones=[OpcionDTO("a", "A", "nota")], valor_app=60, origen="app", valor=60, actualizado_por="ana@x.com", actualizado_en="2026-11-08T10:00:00+00:00"),
        ])])
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.listar.return_value = dto
            resp = _client().get("/parametros", headers=AUTH_HEADER)

        assert resp.status_code == 200
        grupo = resp.get_json()["grupos"][0]
        assert (grupo["clave"], grupo["nombre"], grupo["descripcion"]) == ("victoria", "Victoria", "Cómo trabaja.")
        p = grupo["parametros"][0]
        assert p == {
            "clave": CLAVE, "nombre": "Memoria de la conversación", "paraQueSirve": "Cuántos mensajes se recuerdan.", "tipo": "entero",
            "valor": 60, "origen": "app", "valorOriginal": 40, "valorApp": 60, "variableServidor": "BOT_MAX_MENSAJES_HISTORIAL",
            "valorServidor": None, "minimo": 10, "maximo": 100, "largoMaximo": None, "unidad": "mensajes",
            "aplica": "Desde el siguiente mensaje.", "sensible": False, "aviso": "",
            "opciones": [{"valor": "a", "etiqueta": "A", "nota": "nota"}], "avisos": [],
            "actualizadoPor": "ana@x.com", "actualizadoEn": "2026-11-08T10:00:00+00:00",
        }

    @responses.activate
    def test_guardar_pasa_el_usuario_del_login(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.guardar.return_value = _parametro(valor=50, origen="app", valor_app=50)
            resp = _client().put(f"/parametros/{CLAVE}", json={"valor": 50}, headers=AUTH_HEADER)

        assert resp.status_code == 200 and resp.get_json()["valor"] == 50
        Servicio.return_value.guardar.assert_called_once_with(CLAVE, 50, CORREO_DE_PRUEBA)

    @responses.activate
    def test_guardar_sin_valor_es_422(self):
        mock_login_ok()
        resp = _client().put(f"/parametros/{CLAVE}", json={}, headers=AUTH_HEADER)
        assert resp.status_code == 422 and "valor" in resp.get_json()["detalle"]

    @responses.activate
    def test_valor_invalido_es_422_con_el_mensaje_en_espanol(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.guardar.side_effect = ValorInvalido("Debe ser un número entero entre 10 y 100 mensajes.")
            resp = _client().put(f"/parametros/{CLAVE}", json={"valor": 5}, headers=AUTH_HEADER)

        assert resp.status_code == 422
        assert resp.get_json()["error"] == "Debe ser un número entero entre 10 y 100 mensajes."

    @responses.activate
    def test_clave_desconocida_es_404(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.guardar.side_effect = ParametroDesconocidoError("x")
            resp = _client().put("/parametros/no.existe", json={"valor": 5}, headers=AUTH_HEADER)
        assert resp.status_code == 404

        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.restaurar.side_effect = ParametroDesconocidoError("x")
            resp = _client().delete("/parametros/no.existe", headers=AUTH_HEADER)
        assert resp.status_code == 404

    @responses.activate
    def test_historial_y_su_limite(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.historial.return_value = [CambioDTO(CLAVE, "Memoria", "40", "60", "ana@x.com", "2026-11-08T10:00:00+00:00")]
            resp = _client().get("/parametros/historial?limite=9999", headers=AUTH_HEADER)

        assert resp.status_code == 200
        assert resp.get_json() == [{"clave": CLAVE, "nombre": "Memoria", "valorAnterior": "40", "valorNuevo": "60", "usuario": "ana@x.com", "creadoEn": "2026-11-08T10:00:00+00:00"}]
        Servicio.return_value.historial.assert_called_once_with(200)  # tope máximo

    @responses.activate
    def test_limite_que_no_es_numero_es_422(self):
        mock_login_ok()
        assert _client().get("/parametros/historial?limite=abc", headers=AUTH_HEADER).status_code == 422


@pytest.fixture
def base_limpia():
    def limpiar():
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from parametros_sistema")
                cur.execute("delete from parametros_historial")
        parametros.invalidar()

    limpiar()
    yield
    limpiar()


class TestDePuntaAPunta:
    @responses.activate
    def test_guardar_se_nota_al_instante_y_restaurar_vuelve_al_respaldo(self, base_limpia, monkeypatch):
        monkeypatch.delenv("BOT_MAX_MENSAJES_HISTORIAL", raising=False)
        client = _client()
        mock_login_ok()
        antes = client.get("/parametros", headers=AUTH_HEADER).get_json()
        victoria = next(g for g in antes["grupos"] if g["clave"] == "victoria")
        memoria = next(p for p in victoria["parametros"] if p["clave"] == CLAVE)
        assert (memoria["valor"], memoria["origen"]) == (40, "original")

        mock_login_ok()
        resp = client.put(f"/parametros/{CLAVE}", json={"valor": 55}, headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert (resp.get_json()["valor"], resp.get_json()["origen"], resp.get_json()["actualizadoPor"]) == (55, "app", CORREO_DE_PRUEBA)
        assert parametros.valor(CLAVE) == 55  # lo que lee el resto del sistema, sin esperar la memoria de 30 s

        mock_login_ok()
        resp = client.delete(f"/parametros/{CLAVE}", headers=AUTH_HEADER)
        assert (resp.get_json()["valor"], resp.get_json()["origen"]) == (40, "original")
        assert parametros.valor(CLAVE) == 40

        mock_login_ok()
        historial = client.get("/parametros/historial", headers=AUTH_HEADER).get_json()
        assert [(c["valorAnterior"], c["valorNuevo"]) for c in historial] == [("55", None), (None, "55")]
        assert historial[0]["nombre"] == "Memoria de la conversación"

    @responses.activate
    def test_rechaza_lo_invalido_y_no_guarda_nada(self, base_limpia):
        client = _client()
        for malo in (5, 1000, "abc", True, 40.5):
            mock_login_ok()
            resp = client.put(f"/parametros/{CLAVE}", json={"valor": malo}, headers=AUTH_HEADER)
            assert resp.status_code == 422, malo
        assert parametros.valor(CLAVE) == 40

    @responses.activate
    def test_la_lista_trae_los_veinticuatro_con_sus_explicaciones(self, base_limpia):
        mock_login_ok()
        grupos = _client().get("/parametros", headers=AUTH_HEADER).get_json()["grupos"]
        todos = [p for g in grupos for p in g["parametros"]]
        assert len(todos) == 24 and all(p["paraQueSirve"] and p["aplica"] for p in todos)
        modelo = next(p for p in todos if p["clave"] == "llm.modelo")
        assert modelo["sensible"] and {o["valor"] for o in modelo["opciones"]} >= {"claude-sonnet-5"}
