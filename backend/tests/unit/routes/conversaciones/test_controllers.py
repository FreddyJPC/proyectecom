"""
Tests de la capa HTTP del módulo de Conversaciones: mockean
ConversacionesService por completo (mismo patrón que
tests/unit/routes/incidencias/test_controllers.py) para verificar solo
el ruteo, los códigos de estado, y el mapeo camelCase de los schemas.
"""
from unittest.mock import patch

import responses

from src.app import create_app
from src.routes.conversaciones.exceptions import (
    SinMaterialError,
    SinPedidoEnCursoError,
    ArchivoNoDisponibleError,
    ConversacionNoEncontradaError,
    EnvioWhatsAppFallidoError,
    VentanaMensajeriaCerradaError,
)
from src.routes.conversaciones.dto import (
    ConversacionDetalleDTO,
    DetalleCompletoDTO,
    ListaConversacionesDTO,
    MensajeDTO,
    TotalesPorFiltroRapidoDTO,
)
from tests.conftest import AUTH_HEADER, mock_login_ok


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestListarConversaciones:
    @responses.activate
    def test_lista_y_totales(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.listar_conversaciones.return_value = ListaConversacionesDTO(
                items=[], total=0, page=1, page_size=20,
                totales_por_filtro_rapido=TotalesPorFiltroRapidoDTO(escaladas=2, escaladas_sin_revisar=1, esperando_pago=1),
            )
            resp = _client().get("/conversaciones?estado=escalada", headers=AUTH_HEADER)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["totalesPorFiltroRapido"]["escaladasSinRevisar"] == 1
        MockService.return_value.listar_conversaciones.assert_called_once_with(
            estado="escalada", origen=None, q=None, page=1, page_size=20, canal=None
        )


class TestVerConversacion:
    @responses.activate
    def test_404_si_no_existe(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.obtener_detalle.side_effect = ConversacionNoEncontradaError("no existe")
            resp = _client().get("/conversaciones/999", headers=AUTH_HEADER)

        assert resp.status_code == 404

    @responses.activate
    def test_200_con_lead_null(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.obtener_detalle.return_value = DetalleCompletoDTO(
                conversacion=ConversacionDetalleDTO(
                    id=1, contacto_id=1, canal="whatsapp", id_externo="593987654321", telefono="593987654321", nombre=None,
                    origen="directo", estado="activa",
                    id_anuncio=None, notas_internas=None, ventana_abierta=True,
                    ventana_expira_en=None, creada_en=None, actualizada_en=None,
                ),
                lead=None,
                mensajes=[],
            )
            resp = _client().get("/conversaciones/1", headers=AUTH_HEADER)

        assert resp.status_code == 200
        assert resp.get_json()["lead"] is None


class TestEnviarMensaje:
    @responses.activate
    def test_409_ventana_cerrada(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.enviar_mensaje_manual.side_effect = VentanaMensajeriaCerradaError("cerrada")
            resp = _client().post("/conversaciones/1/mensajes", json={"contenido": "hola"}, headers=AUTH_HEADER)

        assert resp.status_code == 409

    @responses.activate
    def test_422_contenido_vacio(self):
        mock_login_ok()
        resp = _client().post("/conversaciones/1/mensajes", json={"contenido": ""}, headers=AUTH_HEADER)
        assert resp.status_code == 422

    @responses.activate
    def test_502_fallo_de_envio(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.enviar_mensaje_manual.side_effect = EnvioWhatsAppFallidoError("(#131047)")
            resp = _client().post("/conversaciones/1/mensajes", json={"contenido": "hola"}, headers=AUTH_HEADER)

        assert resp.status_code == 502

    @responses.activate
    def test_200_ok(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.enviar_mensaje_manual.return_value = MensajeDTO(
                id=1, rol="humano", contenido="hola", tipo="texto", creado_en="2026-09-27T00:00:00+00:00"
            )
            resp = _client().post("/conversaciones/1/mensajes", json={"contenido": "hola"}, headers=AUTH_HEADER)

        assert resp.status_code == 200
        assert resp.get_json()["contenido"] == "hola"


class TestReactivarYNotas:
    @responses.activate
    def test_reactivar_ok(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService"):
            resp = _client().post("/conversaciones/1/reactivar", headers=AUTH_HEADER)
        assert resp.status_code == 200

    @responses.activate
    def test_continuar_ok_y_pasa_el_pago_y_la_nota(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.continuar_venta.return_value = {"victoriaContinua": True}
            resp = _client().post("/conversaciones/4/continuar", json={"pagoConfirmado": True, "nota": "pide la cédula"}, headers=AUTH_HEADER)
        assert resp.status_code == 200 and resp.get_json()["victoriaContinua"] is True
        MockService.return_value.continuar_venta.assert_called_once_with(4, True, "pide la cédula")

    @responses.activate
    def test_continuar_sin_cuerpo_es_continuar_sin_confirmar_pago(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.continuar_venta.return_value = {"victoriaContinua": False}
            resp = _client().post("/conversaciones/4/continuar", headers=AUTH_HEADER)
        assert resp.status_code == 200
        MockService.return_value.continuar_venta.assert_called_once_with(4, False, None)

    @responses.activate
    def test_continuar_errores(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.continuar_venta.side_effect = SinPedidoEnCursoError("no hay pago")
            assert _client().post("/conversaciones/4/continuar", json={"pagoConfirmado": True}, headers=AUTH_HEADER).status_code == 409
            MockService.return_value.continuar_venta.side_effect = ConversacionNoEncontradaError("no existe")
            assert _client().post("/conversaciones/4/continuar", headers=AUTH_HEADER).status_code == 404
        assert _client().post("/conversaciones/4/continuar", json={"nota": "x" * 600}, headers=AUTH_HEADER).status_code in (401, 422)

    @responses.activate
    def test_tomar_ok(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            resp = _client().post("/conversaciones/1/tomar", headers=AUTH_HEADER)
        assert resp.status_code == 200
        MockService.return_value.tomar.assert_called_once_with(1)

    @responses.activate
    def test_tomar_inexistente_da_404(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.tomar.side_effect = ConversacionNoEncontradaError("no existe")
            resp = _client().post("/conversaciones/9/tomar", headers=AUTH_HEADER)
        assert resp.status_code == 404

    @responses.activate
    def test_notas_ok(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            resp = _client().patch("/conversaciones/1/notas", json={"notasInternas": "nota"}, headers=AUTH_HEADER)

        assert resp.status_code == 200
        MockService.return_value.actualizar_notas.assert_called_once_with(1, "nota")

    @responses.activate
    def test_notas_404(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.actualizar_notas.side_effect = ConversacionNoEncontradaError("no existe")
            resp = _client().patch("/conversaciones/1/notas", json={"notasInternas": "nota"}, headers=AUTH_HEADER)

        assert resp.status_code == 404


class TestArchivoDeUnMensaje:
    @responses.activate
    def test_entrega_el_archivo_con_su_tipo_y_sin_cache_ni_sniffing(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.obtener_archivo.return_value = (b"JPGDATA", "image/jpeg")
            resp = _client().get("/conversaciones/1/mensajes/10/archivo", headers=AUTH_HEADER)
        assert resp.status_code == 200 and resp.data == b"JPGDATA"
        assert resp.mimetype == "image/jpeg"
        assert resp.headers["X-Content-Type-Options"] == "nosniff" and "no-store" in resp.headers["Cache-Control"]

    @responses.activate
    def test_un_tipo_con_parametros_se_limpia(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.obtener_archivo.return_value = (b"x", "audio/ogg; codecs=opus")
            resp = _client().get("/conversaciones/1/mensajes/10/archivo", headers=AUTH_HEADER)
        assert resp.mimetype == "audio/ogg"

    @responses.activate
    def test_404_si_no_hay_archivo_o_la_conversacion(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.obtener_archivo.side_effect = ArchivoNoDisponibleError("Meta ya no entrega este archivo")
            assert _client().get("/conversaciones/1/mensajes/10/archivo", headers=AUTH_HEADER).status_code == 404

    def test_sin_iniciar_sesion_no_se_entrega_nada(self):
        assert _client().get("/conversaciones/1/mensajes/10/archivo").status_code == 401


class TestEnviarMaterial:
    @responses.activate
    def test_envia_y_devuelve_cuantos(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.enviar_material.return_value = {"fotos": 2, "videos": 1}
            resp = _client().post("/conversaciones/5/material", json={"sku": "SET-1", "imagenIds": [3, 4]}, headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.get_json() == {"fotos": 2, "videos": 1}
        MockService.return_value.enviar_material.assert_called_once_with(5, "SET-1", [3, 4])

    @responses.activate
    def test_errores(self):
        mock_login_ok()
        casos = [
            (SinMaterialError("sin fotos"), 422),
            (VentanaMensajeriaCerradaError("cerrada"), 409),
            (EnvioWhatsAppFallidoError("falló"), 502),
            (ConversacionNoEncontradaError("no"), 404),
        ]
        for error, codigo in casos:
            with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
                MockService.return_value.enviar_material.side_effect = error
                resp = _client().post("/conversaciones/5/material", json={"sku": "SET-1"}, headers=AUTH_HEADER)
            assert resp.status_code == codigo

    @responses.activate
    def test_sin_sku_es_422(self):
        mock_login_ok()
        resp = _client().post("/conversaciones/5/material", json={}, headers=AUTH_HEADER)
        assert resp.status_code == 422


class TestEnviarFotoPropia:
    @responses.activate
    def test_envia_el_archivo_al_servicio(self):
        import io

        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
            MockService.return_value.enviar_foto_propia.return_value = {"mensajeId": 5}
            resp = _client().post(
                "/conversaciones/1/foto",
                data={"archivo": (io.BytesIO(b"\xff\xd8\xffJPG"), "foto.jpg", "image/jpeg"), "descripcion": "Su guía"},
                content_type="multipart/form-data",
                headers=AUTH_HEADER,
            )
        assert resp.status_code == 200 and resp.get_json() == {"mensajeId": 5}
        args = MockService.return_value.enviar_foto_propia.call_args.args
        assert args == (1, b"\xff\xd8\xffJPG", "image/jpeg", "Su guía")

    @responses.activate
    def test_sin_archivo(self):
        mock_login_ok()
        resp = _client().post("/conversaciones/1/foto", data={}, content_type="multipart/form-data", headers=AUTH_HEADER)
        assert resp.status_code == 422

    @responses.activate
    def test_errores(self):
        import io

        from src.routes.conversaciones.exceptions import FotoInvalidaError

        mock_login_ok()
        for error, codigo in [(FotoInvalidaError("no"), 422), (VentanaMensajeriaCerradaError("x"), 409),
                              (EnvioWhatsAppFallidoError("x"), 502), (ConversacionNoEncontradaError("x"), 404)]:
            with patch("src.routes.conversaciones.controllers.ConversacionesService") as MockService:
                MockService.return_value.enviar_foto_propia.side_effect = error
                resp = _client().post("/conversaciones/1/foto", data={"archivo": (io.BytesIO(b"x"), "f.jpg")},
                                      content_type="multipart/form-data", headers=AUTH_HEADER)
            assert resp.status_code == codigo, error
