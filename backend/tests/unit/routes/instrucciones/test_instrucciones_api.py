"""
La API de las instrucciones de Victoria, de punta a punta contra la base de pruebas: el flujo
borrador → probar → publicar → volver a la original, y que Victoria lea lo publicado.
"""
import pytest
import responses

from src.app import create_app
from src.config.database import get_connection
from src.routes.whatsapp.instrucciones import instrucciones_vigentes, secciones_originales, texto_original
from tests.conftest import AUTH_HEADER, mock_login_ok

CORREO = "freddyjavier556@gmail.com"  # el que devuelve mock_login_ok
BASE = "/instrucciones-victoria"


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def tabla_limpia():
    def vaciar():
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from victoria_instrucciones_versiones")

    vaciar()
    yield
    vaciar()


def _secciones(**cambios):
    return {**secciones_originales(), **cambios}


def _llamar(metodo, ruta, json=None):
    mock_login_ok()
    return getattr(_client(), metodo)(BASE + ruta, json=json, headers=AUTH_HEADER)


class TestSinLogin:
    def test_todas_las_rutas_piden_login(self):
        c = _client()
        for metodo, ruta in (("get", ""), ("put", "/borrador"), ("delete", "/borrador"), ("post", "/publicar"), ("post", "/volver-a-la-original"), ("post", "/versiones/1/cargar")):
            assert getattr(c, metodo)(BASE + ruta).status_code == 401, (metodo, ruta)


class TestVer:
    @responses.activate
    def test_al_principio_rige_el_original_y_se_ven_las_diez_secciones(self):
        cuerpo = _llamar("get", "").get_json()
        assert cuerpo["usando"] == "original" and cuerpo["publicada"] is None and cuerpo["borrador"] is None
        assert [s["id"] for s in cuerpo["secciones"]] == ["intro", "personalidad", "objetivo", "producto", "reglas", "herramientas", "variantes", "clasificacion", "estado", "fecha"]
        assert cuerpo["maximoTotal"] == 10000 and cuerpo["caracteresFijos"] > 0

        personalidad = next(s for s in cuerpo["secciones"] if s["id"] == "personalidad")
        assert personalidad["editable"] is True and personalidad["vigente"] == personalidad["original"] and personalidad["borrador"] is None
        herramientas = next(s for s in cuerpo["secciones"] if s["id"] == "herramientas")
        assert herramientas["editable"] is False and "registrar_producto" in herramientas["vigente"] and herramientas["maximo"] == 0


class TestBorrador:
    @responses.activate
    def test_guardar_el_borrador_no_cambia_lo_que_usa_victoria(self):
        cuerpo = _llamar("put", "/borrador", {"secciones": _secciones(personalidad="Eres de Cuenca."), "nota": "idea"}).get_json()
        assert cuerpo["borrador"]["nota"] == "idea" and cuerpo["borrador"]["creadoPor"] == CORREO
        assert next(s for s in cuerpo["secciones"] if s["id"] == "personalidad")["borrador"] == "Eres de Cuenca."
        assert instrucciones_vigentes.plantilla() == texto_original()  # los clientes siguen viendo lo de siempre

    @responses.activate
    def test_los_errores_vienen_por_seccion_en_espanol_y_no_se_guarda_nada(self):
        resp = _llamar("put", "/borrador", {"secciones": _secciones(reglas="", objetivo="## título")})
        assert resp.status_code == 422
        detalle = resp.get_json()["detalle"]
        assert detalle["reglas"] == ["No puede quedar vacía."] and "No uses títulos" in detalle["objetivo"][0]
        assert _llamar("get", "").get_json()["borrador"] is None

    @responses.activate
    def test_faltan_datos_es_422(self):
        assert _llamar("put", "/borrador", {}).status_code == 422
        assert _llamar("put", "/borrador", {"secciones": {"intro": "solo una"}}).status_code == 422

    @responses.activate
    def test_descartar(self):
        _llamar("put", "/borrador", {"secciones": _secciones(intro="Eres Vera.")})
        assert _llamar("delete", "/borrador").get_json()["borrador"] is None


class TestPublicar:
    @responses.activate
    def test_publicar_cambia_lo_que_usa_victoria_al_instante(self):
        _llamar("put", "/borrador", {"secciones": _secciones(personalidad="Hablas como guayaquileña.")})
        cuerpo = _llamar("post", "/publicar", {"nota": "tono costeño"}).get_json()

        assert cuerpo["usando"] == "publicada" and cuerpo["borrador"] is None
        assert (cuerpo["publicada"]["nota"], cuerpo["publicada"]["creadoPor"]) == ("tono costeño", CORREO)
        assert "Hablas como guayaquileña." in instrucciones_vigentes.plantilla()  # sin esperar los 30 s
        # el prompt publicado se puede rellenar como siempre
        instrucciones_vigentes.plantilla().format(contexto_producto="x", contexto_lead_actual="y", fecha_actual="z")

    @responses.activate
    def test_publicar_sin_borrador_es_409(self):
        assert _llamar("post", "/publicar", {}).status_code == 409

    @responses.activate
    def test_publicar_otra_vez_archiva_la_anterior_y_quedan_en_el_historial(self):
        _llamar("put", "/borrador", {"secciones": _secciones(objetivo="Vender A")})
        _llamar("post", "/publicar", {})
        _llamar("put", "/borrador", {"secciones": _secciones(objetivo="Vender B")})
        cuerpo = _llamar("post", "/publicar", {}).get_json()

        assert [v["estado"] for v in cuerpo["versiones"]] == ["publicada", "archivada"]
        assert next(s for s in cuerpo["secciones"] if s["id"] == "objetivo")["vigente"] == "Vender B"

    @responses.activate
    def test_las_llaves_en_lo_publicado_no_rompen_a_victoria(self):
        _llamar("put", "/borrador", {"secciones": _secciones(reglas="Nunca uses {llaves} ni } sueltas.")})
        _llamar("post", "/publicar", {})
        listo = instrucciones_vigentes.plantilla().format(contexto_producto="FICHA", contexto_lead_actual="LEAD", fecha_actual="HOY")
        assert "{llaves}" in listo and "FICHA" in listo


class TestVolverALaOriginal:
    @responses.activate
    def test_victoria_vuelve_al_archivo_del_codigo_al_instante(self):
        _llamar("put", "/borrador", {"secciones": _secciones(personalidad="Texto raro.")})
        _llamar("post", "/publicar", {})
        assert "Texto raro." in instrucciones_vigentes.plantilla()

        cuerpo = _llamar("post", "/volver-a-la-original").get_json()
        assert cuerpo["usando"] == "original" and cuerpo["publicada"] is None
        assert instrucciones_vigentes.plantilla() == texto_original()
        assert cuerpo["versiones"][0]["estado"] == "archivada"  # no se pierde: se puede volver a cargar


class TestCargarUnaVersion:
    @responses.activate
    def test_una_version_archivada_vuelve_al_borrador_para_probarla(self):
        _llamar("put", "/borrador", {"secciones": _secciones(objetivo="Vender A")})
        primera = _llamar("post", "/publicar", {}).get_json()["publicada"]["id"]
        _llamar("post", "/volver-a-la-original")

        cuerpo = _llamar("post", f"/versiones/{primera}/cargar").get_json()
        assert cuerpo["borrador"]["nota"] == f"Cargada desde la versión {primera}"
        assert next(s for s in cuerpo["secciones"] if s["id"] == "objetivo")["borrador"] == "Vender A"
        assert cuerpo["usando"] == "original"  # cargarla no la publica

    @responses.activate
    def test_version_que_no_existe_es_404(self):
        assert _llamar("post", "/versiones/999999/cargar").status_code == 404
