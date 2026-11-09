"""API de leads: forma JSON (camelCase, dinero como texto), filtros, errores y que toda ruta exija sesión."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import responses

from src.app import create_app
from src.routes.leads.exceptions import (
    ContactoNoEncontradoError,
    DatosInvalidosError,
    LeadNoEncontradoError,
    OtroLeadAbiertoError,
    VentaYaCerradaError,
)
from tests.conftest import AUTH_HEADER, mock_login_ok

AHORA = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def cliente():
    app = create_app()
    app.testing = True
    return app.test_client()


def _servicio(servicio):
    return patch("src.routes.leads.controllers._servicio", return_value=servicio)


def _fila(**cambios):
    base = {
        "id": 7, "contacto_id": 3, "conversacion_id": 5, "canal": "whatsapp", "id_externo": "593987654321",
        "estado_conversacion": "activa", "telefono": "593987654321", "contacto_nombre": "Ana", "nombre_perfil": "Ana P.",
        "nombre_cliente": None, "producto_sku": "AUD-1", "producto_nombre": "Audífonos", "producto_variante": "Negro",
        "cantidad": 2, "total": Decimal("49.9"), "etapa": "recopilando_datos", "temperatura": "caliente",
        "temperatura_motivo": "Pidió cómo pagar", "temperatura_origen": "ia", "temperatura_en": AHORA,
        "temperatura_fijada_hasta": None, "motivo_perdida": None, "origen": "anuncio", "id_anuncio": "123",
        "titulo_anuncio": "Audífonos 2x1", "creado_en": AHORA, "actualizado_en": AHORA, "cerrado_en": None,
        "no_contactar": False, "no_contactar_motivo": None, "ultimo_rol": "cliente", "ultimo_contenido": "Hola",
        "ultimo_en": AHORA, "ultimo_cliente_en": AHORA,
    }
    base.update(cambios)
    return base


def _contacto():
    return {
        "id": 3, "nombre": "Ana", "telefono": "593987654321", "tipo": "cliente", "no_contactar": False, "no_contactar_motivo": None,
        "no_contactar_en": None, "no_contactar_por": None, "creado_en": AHORA,
        "conversaciones": [{"id": 5, "canal": "whatsapp", "id_externo": "593987654321", "estado": "activa", "creada_en": AHORA}],
        "leads": [{"id": 7, "conversacion_id": 5, "producto_nombre": "Audífonos", "temperatura": "caliente", "etapa": "recopilando_datos",
                   "total": Decimal("49.9"), "origen": "anuncio", "creado_en": AHORA, "cerrado_en": None}],
        "compras": {"compras": 1, "total_gastado": Decimal("40"), "ganancia": Decimal("15"), "compras_sin_costo": 0, "ultima_compra": AHORA},
        "anuncios": {"llegadas": 1, "primera": AHORA, "ultima": AHORA},
        "primer_anuncio": {"id_anuncio": "123", "titulo": "Audífonos 2x1"},
    }


class TestSesion:
    @responses.activate
    def test_toda_ruta_exige_sesion(self, cliente):
        assert cliente.get("/leads").status_code == 401
        assert cliente.get("/leads/resumen").status_code == 401
        assert cliente.get("/leads/7").status_code == 401
        assert cliente.patch("/leads/7", json={"temperatura": "frio"}).status_code == 401
        assert cliente.put("/contactos/3/no-contactar", json={"noContactar": True}).status_code == 401


class TestListar:
    @responses.activate
    def test_devuelve_camelcase_dinero_como_texto_y_el_ultimo_mensaje(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.listar.return_value = {"items": [_fila()], "total": 1, "page": 1, "page_size": 20}
        with _servicio(servicio):
            r = cliente.get("/leads", headers=AUTH_HEADER)
        assert r.status_code == 200
        cuerpo = r.get_json()
        assert (cuerpo["total"], cuerpo["pageSize"]) == (1, 20)
        lead = cuerpo["items"][0]
        assert (lead["nombre"], lead["temperatura"], lead["temperaturaEtiqueta"], lead["total"], lead["canal"]) == ("Ana", "caliente", "Caliente", "49.90", "whatsapp")
        assert lead["ultimoMensaje"] == {"rol": "cliente", "contenido": "Hola", "creadoEn": AHORA.isoformat()}
        assert (lead["origen"], lead["tituloAnuncio"], lead["noContactar"]) == ("anuncio", "Audífonos 2x1", False)

    @responses.activate
    def test_la_lista_trae_el_ultimo_seguimiento_enviado(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.listar.return_value = {
            "items": [_fila(), _fila(id=8, seguimiento_tipo="empujon", seguimiento_en=AHORA)], "total": 2, "page": 1, "page_size": 20,
        }
        with _servicio(servicio):
            sin, con = cliente.get("/leads", headers=AUTH_HEADER).get_json()["items"]
        assert sin["ultimoSeguimiento"] is None
        assert con["ultimoSeguimiento"] == {"tipo": "empujon", "enviadoEn": AHORA.isoformat()}

    @responses.activate
    def test_pasa_los_filtros_al_servicio(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.listar.return_value = {"items": [], "total": 0, "page": 2, "page_size": 10}
        with _servicio(servicio):
            cliente.get(
                "/leads?temperatura=caliente,tibio&etapa=esperando_pago&origen=anuncio&canal=instagram&producto=AUD-1&q=ana"
                "&noContactar=false&sinRespuestaDias=5&orden=valor&page=2&pageSize=10", headers=AUTH_HEADER,
            )
        assert servicio.listar.call_args.kwargs == {
            "temperaturas": ["caliente", "tibio"], "etapa": "esperando_pago", "origen": "anuncio", "canal": "instagram",
            "producto_sku": "AUD-1", "q": "ana", "no_contactar": False, "sin_respuesta_dias": 5, "orden": "valor", "page": 2, "page_size": 10,
        }

    @responses.activate
    def test_un_filtro_invalido_es_422(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.listar.side_effect = DatosInvalidosError("Temperatura desconocida: hirviendo.")
        with _servicio(servicio):
            r = cliente.get("/leads?temperatura=hirviendo", headers=AUTH_HEADER)
        assert r.status_code == 422 and "hirviendo" in r.get_json()["error"]


class TestResumen:
    @responses.activate
    def test_devuelve_los_numeros_de_arriba_de_la_pantalla(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.resumen.return_value = {
            "calientes": 1, "tibios": 2, "frios": 3, "valor_en_juego": Decimal("150"), "nuevos": 9, "ganados": 3,
            "perdidos": 1, "ingresos_ganados": Decimal("90"), "tasa_de_cierre": Decimal("75.0"), "no_contactar": 2,
            "motivos_de_perdida": [{"motivo": "precio", "etiqueta": "El precio", "leads": 1}],
        }
        with _servicio(servicio):
            r = cliente.get("/leads/resumen?dias=30", headers=AUTH_HEADER)
        assert r.status_code == 200
        c = r.get_json()
        assert (c["valorEnJuego"], c["ingresosGanados"], c["tasaDeCierre"], c["noContactar"]) == ("150.00", "90.00", "75.0", 2)
        assert servicio.resumen.call_args.args == (30,)

    @responses.activate
    def test_un_periodo_raro_es_422_y_todo_el_tiempo_es_valido(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.resumen.return_value = {
            "calientes": 0, "tibios": 0, "frios": 0, "valor_en_juego": 0, "nuevos": 0, "ganados": 0, "perdidos": 0,
            "ingresos_ganados": 0, "tasa_de_cierre": None, "no_contactar": 0, "motivos_de_perdida": [],
        }
        with _servicio(servicio):
            assert cliente.get("/leads/resumen?dias=45", headers=AUTH_HEADER).status_code == 422
            r = cliente.get("/leads/resumen?dias=todo", headers=AUTH_HEADER)
        assert r.status_code == 200 and r.get_json()["tasaDeCierre"] is None


class TestDetalleYCambios:
    @responses.activate
    def test_el_detalle_trae_historial_y_ficha_del_contacto(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.detalle.return_value = {
            "lead": _fila(),
            "historial": [{"id": 1, "de": "tibio", "a": "caliente", "origen": "ia", "motivo": "Pidió cómo pagar", "usuario": None, "creado_en": AHORA}],
            "contacto": _contacto(),
        }
        with _servicio(servicio):
            r = cliente.get("/leads/7", headers=AUTH_HEADER)
        assert r.status_code == 200
        c = r.get_json()
        assert c["historial"][0]["a"] == "caliente" and c["contacto"]["tipo"] == "cliente"
        assert c["contacto"]["compras"] == {"cantidad": 1, "totalGastado": "40.00", "ganancia": "15.00", "comprasSinCosto": 0, "ultimaCompra": AHORA.isoformat()}
        assert c["contacto"]["anuncios"]["primerAnuncio"] == {"idAnuncio": "123", "titulo": "Audífonos 2x1"}
        assert c["contacto"]["conversaciones"][0]["idExterno"] == "593987654321"

    @responses.activate
    def test_el_detalle_trae_los_seguimientos_automaticos_enviados_y_fallidos(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.detalle.return_value = {
            "lead": _fila(), "historial": [], "contacto": _contacto(),
            "seguimientos": [
                {"id": 2, "tipo": "plantilla", "estado": "fallido", "contenido": "Hola", "plantilla": "retomar_conversacion",
                 "error": "Plantilla no aprobada", "creado_en": AHORA, "enviado_en": None},
                {"id": 1, "tipo": "empujon", "estado": "enviado", "contenido": "¿Sigue interesado(a)?", "plantilla": None,
                 "error": None, "creado_en": AHORA, "enviado_en": AHORA},
            ],
        }
        with _servicio(servicio):
            c = cliente.get("/leads/7", headers=AUTH_HEADER).get_json()
        assert [s["tipo"] for s in c["seguimientos"]] == ["plantilla", "empujon"]
        assert c["seguimientos"][0] == {
            "id": 2, "tipo": "plantilla", "estado": "fallido", "contenido": "Hola", "plantilla": "retomar_conversacion",
            "error": "Plantilla no aprobada", "creadoEn": AHORA.isoformat(), "enviadoEn": None,
        }
        assert c["seguimientos"][1]["enviadoEn"] == AHORA.isoformat()

    @responses.activate
    def test_un_detalle_sin_seguimientos_los_trae_vacios(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.detalle.return_value = {"lead": _fila(), "historial": [], "contacto": None}
        with _servicio(servicio):
            assert cliente.get("/leads/7", headers=AUTH_HEADER).get_json()["seguimientos"] == []

    @responses.activate
    def test_lead_inexistente_es_404(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.detalle.side_effect = LeadNoEncontradoError("No existe el lead 9.")
        with _servicio(servicio):
            assert cliente.get("/leads/9", headers=AUTH_HEADER).status_code == 404

    @responses.activate
    def test_cambiar_la_temperatura_pasa_los_datos_y_el_usuario(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        servicio.cambiar_temperatura.return_value = {"lead": _fila(temperatura="perdido"), "historial": [], "contacto": None}
        with _servicio(servicio):
            r = cliente.patch("/leads/7", json={"temperatura": "perdido", "motivoPerdida": "precio", "motivo": "Muy caro"}, headers=AUTH_HEADER)
        assert r.status_code == 200 and r.get_json()["lead"]["temperatura"] == "perdido" and r.get_json()["contacto"] is None
        args = servicio.cambiar_temperatura.call_args.args
        assert args[:4] == (7, "perdido", "precio", "Muy caro") and args[4] == "freddyjavier556@gmail.com"

    @responses.activate
    def test_datos_invalidos_422_y_conflictos_409_y_no_encontrado_404(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        with _servicio(servicio):
            assert cliente.patch("/leads/7", json={}, headers=AUTH_HEADER).status_code == 422
            assert cliente.patch("/leads/7", json={"temperatura": "templado"}, headers=AUTH_HEADER).status_code == 422
            assert cliente.patch("/leads/7", json={"temperatura": "perdido", "motivoPerdida": "inventado"}, headers=AUTH_HEADER).status_code == 422
            servicio.cambiar_temperatura.side_effect = VentaYaCerradaError("Este lead ya tiene una venta cerrada.")
            assert cliente.patch("/leads/7", json={"temperatura": "frio"}, headers=AUTH_HEADER).status_code == 409
            servicio.cambiar_temperatura.side_effect = OtroLeadAbiertoError("otro abierto")
            assert cliente.patch("/leads/7", json={"temperatura": "tibio"}, headers=AUTH_HEADER).status_code == 409
            servicio.cambiar_temperatura.side_effect = LeadNoEncontradoError("no")
            assert cliente.patch("/leads/7", json={"temperatura": "frio"}, headers=AUTH_HEADER).status_code == 404
            servicio.cambiar_temperatura.side_effect = DatosInvalidosError("motivo")
            assert cliente.patch("/leads/7", json={"temperatura": "perdido"}, headers=AUTH_HEADER).status_code == 422


class TestNoContactar:
    @responses.activate
    def test_marca_y_quita(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        with _servicio(servicio):
            r = cliente.put("/contactos/3/no-contactar", json={"noContactar": True, "motivo": "Lo pidió"}, headers=AUTH_HEADER)
            assert r.status_code == 200 and r.get_json() == {"ok": True}
            cliente.put("/contactos/3/no-contactar", json={"noContactar": False}, headers=AUTH_HEADER)
        assert servicio.marcar_no_contactar.call_args_list[0].args[:3] == (3, True, "Lo pidió")
        assert servicio.marcar_no_contactar.call_args_list[1].args[:3] == (3, False, None)

    @responses.activate
    def test_validacion_y_contacto_inexistente(self, cliente):
        mock_login_ok()
        servicio = MagicMock()
        with _servicio(servicio):
            assert cliente.put("/contactos/3/no-contactar", json={}, headers=AUTH_HEADER).status_code == 422
            servicio.marcar_no_contactar.side_effect = ContactoNoEncontradoError("no")
            assert cliente.put("/contactos/3/no-contactar", json={"noContactar": True}, headers=AUTH_HEADER).status_code == 404
