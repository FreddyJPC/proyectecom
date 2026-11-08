"""
Capa HTTP de la gestión de productos: se mockea el servicio completo (mismo
patrón que tests/unit/routes/conversaciones/test_controllers.py) para verificar
ruteo, códigos de estado, validación de entrada y el mapeo a camelCase.
"""
from decimal import Decimal
from unittest.mock import patch

import responses

from src.app import create_app
from src.integrations.rocketfy import RocketfyRequestError
from src.routes.productos.exceptions import SkuNoExisteEnRocketfyError
from src.routes.productos_bot.dto import (
    AlertaContenidoDTO,
    AvisoSimuladoDTO,
    BorradorContenidoDTO,
    CamposContenidoDTO,
    EvaluacionPrecioDTO,
    HistorialDTO,
    LlamadaHerramientaDTO,
    NivelPrecioDTO,
    PedidoSimuladoDTO,
    ProductoBotDetalleDTO,
    ProductoBotResumenDTO,
    RecomendacionPrecioDTO,
    TurnoSimuladoDTO,
    UsoIADTO,
    UsoPruebasDTO,
    VerificacionDTO,
)
from src.routes.productos_bot.exceptions import (
    IAFalloError,
    IANoDisponibleError,
    ProductoBotNoEncontradoError,
    ProductoBotYaExisteError,
    PruebaInvalidaError,
    PublicacionBloqueadaError,
    SkuInvalidoError,
    TopeDeIAAlcanzadoError,
    TopeDePruebasAlcanzadoError,
    TransicionInvalidaError,
)
from src.routes.productos_bot.redaccion import NotasDelDueno
from tests.conftest import AUTH_HEADER, mock_login_ok

SERVICIO = "src.routes.productos_bot.controllers.ProductosBotService"
SERVICIO_IA = "src.routes.productos_bot.controllers.ContenidoIAService"
SERVICIO_PRUEBAS = "src.routes.productos_bot.controllers.PruebasService"
CORREO_DE_PRUEBA = "freddyjavier556@gmail.com"  # el que devuelve mock_login_ok


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _detalle(**cambios):
    datos = dict(
        sku="DEMO-1", nombre="Producto Demo", estado="borrador", precio="24.99", costo_rocketfy="10.00",
        precio_sugerido_rocketfy="29.90", stock_ultimo=10, stock_actualizado_en="2026-11-05T21:00:00+00:00",
        peso_kg="0.350", imagen_url=None, rocketfy_product_id=4821, descripcion="Desc", variantes=None,
        tiempo_entrega="2 días", metodos_pago=["contraentrega"], preguntas_frecuentes=None, temas_no_responder=None,
        max_unidades_por_pedido=1, notas_internas=None, publicado_en=None, publicado_por=None,
        creado_en="2026-11-05T21:00:00+00:00", actualizado_en="2026-11-05T21:00:00+00:00",
        verificacion=VerificacionDTO(bloqueos=[], avisos=["Aviso de prueba"]),
        historial=[HistorialDTO(accion="creado", usuario="ana@ejemplo.com", cambios={"desde": "rocketfy"}, creado_en="2026-11-05T21:00:00+00:00")],
    )
    datos.update(cambios)
    return ProductoBotDetalleDTO(**datos)


class TestAutenticacion:
    def test_sin_login_no_se_puede_ver_la_gestion(self):
        assert _client().get("/productos-bot").status_code == 401
        assert _client().post("/productos-bot", json={"sku": "X"}).status_code == 401
        assert _client().post("/productos-bot/X/publicar").status_code == 401


class TestListar:
    @responses.activate
    def test_lista_en_camel_case_y_sin_archivados_por_defecto(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.listar.return_value = [
                ProductoBotResumenDTO(
                    sku="DEMO-1", nombre="Producto Demo", estado="activo", precio="24.99", costo_rocketfy="10.00",
                    stock_ultimo=3, max_unidades_por_pedido=1, imagen_url=None, publicado_en=None, actualizado_en=None,
                )
            ]
            resp = _client().get("/productos-bot", headers=AUTH_HEADER)

        assert resp.status_code == 200
        item = resp.get_json()[0]
        assert item["costoRocketfy"] == "10.00" and item["stockUltimo"] == 3 and item["maxUnidadesPorPedido"] == 1
        Servicio.return_value.listar.assert_called_once_with(incluir_archivados=False)
        # Fase F: sin datos nuevos, los valores por defecto (nada de pedidos, sin insignia)
        assert item["pedidos30d"] == 0 and item["margenEnRiesgo"] is False

    @responses.activate
    def test_la_lista_trae_los_pedidos_de_30_dias_y_la_insignia_de_margen(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.listar.return_value = [
                ProductoBotResumenDTO(
                    sku="DEMO-1", nombre="Producto Demo", estado="activo", precio="24.99", costo_rocketfy="10.00",
                    stock_ultimo=3, max_unidades_por_pedido=1, imagen_url=None, publicado_en=None, actualizado_en=None,
                    pedidos_30d=12, margen_en_riesgo=True,
                )
            ]
            resp = _client().get("/productos-bot", headers=AUTH_HEADER)
        item = resp.get_json()[0]
        assert item["pedidos30d"] == 12 and item["margenEnRiesgo"] is True

    @responses.activate
    def test_incluir_archivados(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.listar.return_value = []
            _client().get("/productos-bot?incluirArchivados=true", headers=AUTH_HEADER)
        Servicio.return_value.listar.assert_called_once_with(incluir_archivados=True)


class TestDetalle:
    @responses.activate
    def test_devuelve_el_detalle_con_verificacion_e_historial(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.obtener_detalle.return_value = _detalle()
            resp = _client().get("/productos-bot/DEMO-1", headers=AUTH_HEADER)

        assert resp.status_code == 200
        cuerpo = resp.get_json()
        assert cuerpo["precioSugeridoRocketfy"] == "29.90"
        assert cuerpo["metodosPago"] == ["contraentrega"]
        assert cuerpo["verificacion"] == {"bloqueos": [], "avisos": ["Aviso de prueba"]}
        assert cuerpo["historial"][0] == {
            "accion": "creado", "usuario": "ana@ejemplo.com", "cambios": {"desde": "rocketfy"}, "creadoEn": "2026-11-05T21:00:00+00:00",
        }

    @responses.activate
    def test_404_si_no_existe(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.obtener_detalle.side_effect = ProductoBotNoEncontradoError("no existe")
            resp = _client().get("/productos-bot/NO-EXISTE", headers=AUTH_HEADER)
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "no existe"


class TestCrear:
    @responses.activate
    def test_201_y_pasa_el_correo_del_usuario(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.crear_borrador.return_value = _detalle()
            resp = _client().post("/productos-bot", json={"sku": "DEMO-1"}, headers=AUTH_HEADER)

        assert resp.status_code == 201
        Servicio.return_value.crear_borrador.assert_called_once_with("DEMO-1", CORREO_DE_PRUEBA)

    @responses.activate
    def test_422_si_falta_el_sku(self):
        mock_login_ok()
        with patch(SERVICIO):
            resp = _client().post("/productos-bot", json={}, headers=AUTH_HEADER)
        assert resp.status_code == 422
        assert "sku" in resp.get_json()["detalle"]

    @responses.activate
    def test_errores_conocidos(self):
        casos = [
            (SkuNoExisteEnRocketfyError("no está"), 422),
            (SkuInvalidoError("inválido"), 422),
            (ProductoBotYaExisteError("ya existe"), 409),
            (RocketfyRequestError("timeout"), 502),
        ]
        for excepcion, esperado in casos:
            mock_login_ok()
            with patch(SERVICIO) as Servicio:
                Servicio.return_value.crear_borrador.side_effect = excepcion
                resp = _client().post("/productos-bot", json={"sku": "X"}, headers=AUTH_HEADER)
            assert resp.status_code == esperado, excepcion
            assert resp.get_json()["error"]


class TestEditar:
    @responses.activate
    def test_traduce_los_nombres_a_columnas_y_normaliza(self):
        mock_login_ok()
        cuerpo = {
            "precio": "27.5",
            "tiempoEntrega": "  3 días  ",
            "metodosPago": ["contraentrega", "transferencia", "contraentrega"],
            "maxUnidadesPorPedido": 2,
            "variantes": "   ",
            "preguntasFrecuentes": "¿Trae cargador? Sí.",
            "campoQueNoExiste": "se ignora",
        }
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.editar.return_value = _detalle()
            resp = _client().patch("/productos-bot/DEMO-1", json=cuerpo, headers=AUTH_HEADER)

        assert resp.status_code == 200
        Servicio.return_value.editar.assert_called_once_with(
            "DEMO-1",
            {
                "precio": Decimal("27.50"),
                "tiempo_entrega": "3 días",
                "metodos_pago_aceptados": "contraentrega, transferencia",
                "max_unidades_por_pedido": 2,
                "variantes": None,  # solo espacios = vaciar
                "preguntas_frecuentes": "¿Trae cargador? Sí.",
            },
            CORREO_DE_PRUEBA,
        )

    @responses.activate
    def test_validaciones_de_entrada(self):
        invalidos = [
            {"precio": "0"},
            {"precio": "-3"},
            {"precio": "abc"},
            {"nombre": ""},
            {"nombre": "x" * 121},
            {"descripcion": "x" * 1501},
            {"metodosPago": []},
            {"metodosPago": ["bitcoin"]},
            {"maxUnidadesPorPedido": 0},
            {"maxUnidadesPorPedido": 21},
            {"preguntasFrecuentes": "x" * 3001},
            {"precioCompetencia": "0"},
            {"precioCompetencia": "-5"},
            {"precioCompetencia": "abc"},
        ]
        for cuerpo in invalidos:
            mock_login_ok()
            with patch(SERVICIO) as Servicio:
                resp = _client().patch("/productos-bot/DEMO-1", json=cuerpo, headers=AUTH_HEADER)
            assert resp.status_code == 422, cuerpo
            Servicio.return_value.editar.assert_not_called()

    @responses.activate
    def test_precio_de_la_competencia_se_guarda_y_se_puede_borrar(self):
        for enviado, guardado in (("22.5", Decimal("22.50")), (None, None)):
            mock_login_ok()
            with patch(SERVICIO) as Servicio:
                Servicio.return_value.editar.return_value = _detalle(precio_competencia="22.50")
                resp = _client().patch("/productos-bot/DEMO-1", json={"precioCompetencia": enviado}, headers=AUTH_HEADER)
            assert resp.status_code == 200
            assert resp.get_json()["precioCompetencia"] == "22.50"
            Servicio.return_value.editar.assert_called_once_with("DEMO-1", {"precio_competencia": guardado}, CORREO_DE_PRUEBA)

    @responses.activate
    def test_cuerpo_vacio_no_cambia_nada_pero_no_falla(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.editar.return_value = _detalle()
            resp = _client().patch("/productos-bot/DEMO-1", json={}, headers=AUTH_HEADER)
        assert resp.status_code == 200
        Servicio.return_value.editar.assert_called_once_with("DEMO-1", {}, CORREO_DE_PRUEBA)

    @responses.activate
    def test_bloqueo_de_un_producto_activo_devuelve_422_con_la_lista(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.editar.side_effect = PublicacionBloqueadaError(["Falta la descripción de ventas."])
            resp = _client().patch("/productos-bot/DEMO-1", json={"descripcion": "x"}, headers=AUTH_HEADER)
        assert resp.status_code == 422
        assert resp.get_json()["bloqueos"] == ["Falta la descripción de ventas."]


class TestAcciones:
    @responses.activate
    def test_cada_accion_llama_a_su_metodo_con_el_correo(self):
        acciones = {
            "publicar": "publicar", "reanudar": "reanudar", "pausar": "pausar",
            "archivar": "archivar", "restaurar": "restaurar",
        }
        for ruta, metodo in acciones.items():
            mock_login_ok()
            with patch(SERVICIO) as Servicio:
                getattr(Servicio.return_value, metodo).return_value = _detalle(estado="activo")
                resp = _client().post(f"/productos-bot/DEMO-1/{ruta}", headers=AUTH_HEADER)
            assert resp.status_code == 200, ruta
            getattr(Servicio.return_value, metodo).assert_called_once_with("DEMO-1", CORREO_DE_PRUEBA)
            assert resp.get_json()["estado"] == "activo"

    @responses.activate
    def test_publicacion_bloqueada_devuelve_422_con_los_motivos(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.publicar.side_effect = PublicacionBloqueadaError(["Falta el tiempo de entrega.", "No hay stock en Rocketfy (0 unidades)."])
            resp = _client().post("/productos-bot/DEMO-1/publicar", headers=AUTH_HEADER)
        assert resp.status_code == 422
        assert resp.get_json()["bloqueos"] == ["Falta el tiempo de entrega.", "No hay stock en Rocketfy (0 unidades)."]

    @responses.activate
    def test_transicion_invalida_es_409(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.pausar.side_effect = TransicionInvalidaError("No se puede pausar")
            resp = _client().post("/productos-bot/DEMO-1/pausar", headers=AUTH_HEADER)
        assert resp.status_code == 409

    @responses.activate
    def test_rocketfy_caido_al_publicar_es_502(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.publicar.side_effect = RocketfyRequestError("timeout")
            resp = _client().post("/productos-bot/DEMO-1/publicar", headers=AUTH_HEADER)
        assert resp.status_code == 502

    @responses.activate
    def test_actualizar_desde_rocketfy(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.actualizar_desde_rocketfy.return_value = _detalle()
            resp = _client().post("/productos-bot/DEMO-1/actualizar-rocketfy", headers=AUTH_HEADER)
        assert resp.status_code == 200
        Servicio.return_value.actualizar_desde_rocketfy.assert_called_once_with("DEMO-1", CORREO_DE_PRUEBA)


def _recomendacion(**cambios):
    datos = dict(
        ajustes_confirmados=True, costo="10.00", piso="15.00", envio_estimado="5.00", otros_costos_fijos="0.00",
        otros_costos_pct="0.00", margen_minimo_pct="25.00", margen_objetivo_pct="35.00", precio_sugerido="29.90",
        precio_competencia=None,
        niveles=[NivelPrecioDTO(clave="minimo", nombre="Mínimo", precio="20.99", ganancia="5.99", margen_pct="28.5")],
        evaluacion=EvaluacionPrecioDTO(precio="24.99", ganancia="9.99", margen_pct="40.0", bajo_piso=False, bajo_margen_minimo=False),
        avisos=["Un aviso"],
    )
    datos.update(cambios)
    return RecomendacionPrecioDTO(**datos)


class TestRecomendarPrecio:
    @responses.activate
    def test_sin_login_es_401(self):
        assert _client().get("/productos-bot/DEMO-1/precio").status_code == 401

    @responses.activate
    def test_devuelve_la_recomendacion_en_camel_case(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.recomendar_precio.return_value = _recomendacion()
            resp = _client().get("/productos-bot/DEMO-1/precio", headers=AUTH_HEADER)

        assert resp.status_code == 200
        cuerpo = resp.get_json()
        assert cuerpo["ajustesConfirmados"] is True
        assert (cuerpo["costo"], cuerpo["piso"], cuerpo["envioEstimado"], cuerpo["precioSugerido"]) == ("10.00", "15.00", "5.00", "29.90")
        assert cuerpo["niveles"] == [{"clave": "minimo", "nombre": "Mínimo", "precio": "20.99", "ganancia": "5.99", "margenPct": "28.5"}]
        assert cuerpo["evaluacion"] == {"precio": "24.99", "ganancia": "9.99", "margenPct": "40.0", "bajoPiso": False, "bajoMargenMinimo": False}
        assert cuerpo["avisos"] == ["Un aviso"]
        Servicio.return_value.recomendar_precio.assert_called_once_with("DEMO-1", precio=None, competencia=None)

    @responses.activate
    def test_pasa_el_precio_y_la_competencia_como_decimal(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.recomendar_precio.return_value = _recomendacion(evaluacion=None)
            resp = _client().get("/productos-bot/DEMO-1/precio?precio=24.99&competencia=22", headers=AUTH_HEADER)

        assert resp.status_code == 200 and resp.get_json()["evaluacion"] is None
        Servicio.return_value.recomendar_precio.assert_called_once_with("DEMO-1", precio=Decimal("24.99"), competencia=Decimal("22"))

    @responses.activate
    def test_montos_invalidos_son_422_y_no_llegan_al_servicio(self):
        for consulta in ("precio=abc", "precio=0", "precio=-3", "precio=1e999", "precio=24.999", "competencia=x", "competencia=0"):
            mock_login_ok()
            with patch(SERVICIO) as Servicio:
                resp = _client().get(f"/productos-bot/DEMO-1/precio?{consulta}", headers=AUTH_HEADER)
            assert resp.status_code == 422, consulta
            Servicio.return_value.recomendar_precio.assert_not_called()

    @responses.activate
    def test_producto_inexistente_es_404(self):
        mock_login_ok()
        with patch(SERVICIO) as Servicio:
            Servicio.return_value.recomendar_precio.side_effect = ProductoBotNoEncontradoError("no existe")
            resp = _client().get("/productos-bot/NO-EXISTE/precio", headers=AUTH_HEADER)
        assert resp.status_code == 404


def _borrador(**cambios):
    datos = dict(
        campos=CamposContenidoDTO(nombre="Audífonos", descripcion="Con 20 horas.", preguntas_frecuentes="¿Trae estuche? Sí."),
        fuentes=CamposContenidoDTO(nombre="mixto", descripcion="rocketfy", preguntas_frecuentes="ia"),
        alertas=[
            AlertaContenidoDTO(campo=None, texto="General", origen="ia"),
            AlertaContenidoDTO(campo="preguntasFrecuentes", texto="Menciona «30»", origen="verificacion"),
        ],
        uso=UsoIADTO(tope=20, usadas=3, restantes=17),
    )
    datos.update(cambios)
    return BorradorContenidoDTO(**datos)


class TestGenerarContenido:
    @responses.activate
    def test_sin_login_es_401(self):
        assert _client().post("/productos-bot/DEMO-1/contenido/generar", json={}).status_code == 401
        assert _client().get("/productos-bot/contenido/uso").status_code == 401

    @responses.activate
    def test_devuelve_el_borrador_en_camel_case_sin_los_campos_que_no_se_pidieron(self):
        mock_login_ok()
        with patch(SERVICIO_IA) as Servicio:
            Servicio.return_value.generar.return_value = _borrador()
            resp = _client().post("/productos-bot/DEMO-1/contenido/generar", json={}, headers=AUTH_HEADER)

        assert resp.status_code == 200
        cuerpo = resp.get_json()
        assert cuerpo["campos"] == {"nombre": "Audífonos", "descripcion": "Con 20 horas.", "preguntasFrecuentes": "¿Trae estuche? Sí."}
        assert cuerpo["fuentes"] == {"nombre": "mixto", "descripcion": "rocketfy", "preguntasFrecuentes": "ia"}
        assert cuerpo["alertas"][1] == {"campo": "preguntasFrecuentes", "texto": "Menciona «30»", "origen": "verificacion"}
        assert cuerpo["alertas"][0]["campo"] is None
        assert cuerpo["uso"] == {"tope": 20, "usadas": 3, "restantes": 17}

    @responses.activate
    def test_pasa_las_notas_los_campos_y_el_correo_al_servicio(self):
        mock_login_ok()
        cuerpo = {
            "notas": {"dirigidoA": "  jóvenes  ", "destacar": "batería", "evitar": "", "otrosDatos": "Incluye estuche", "campoRaro": "se ignora"},
            "productoDeSalud": True,
            "campos": ["preguntasFrecuentes", "nombre", "nombre"],
        }
        with patch(SERVICIO_IA) as Servicio:
            Servicio.return_value.generar.return_value = _borrador()
            _client().post("/productos-bot/DEMO-1/contenido/generar", json=cuerpo, headers=AUTH_HEADER)

        sku, notas, campos, usuario = Servicio.return_value.generar.call_args.args
        assert sku == "DEMO-1"
        assert notas == NotasDelDueno(dirigido_a="jóvenes", destacar="batería", evitar="", otros_datos="Incluye estuche", producto_de_salud=True)
        assert campos == ["preguntas_frecuentes", "nombre"]  # a nombres de columna y sin repetidos
        assert usuario == CORREO_DE_PRUEBA

    @responses.activate
    def test_un_cuerpo_vacio_redacta_todo_con_notas_vacias(self):
        mock_login_ok()
        with patch(SERVICIO_IA) as Servicio:
            Servicio.return_value.generar.return_value = _borrador()
            resp = _client().post("/productos-bot/DEMO-1/contenido/generar", json={}, headers=AUTH_HEADER)

        assert resp.status_code == 200
        _, notas, campos, _ = Servicio.return_value.generar.call_args.args
        assert notas == NotasDelDueno() and campos is None

    @responses.activate
    def test_validaciones_de_entrada_no_llegan_al_servicio(self):
        invalidos = [
            {"notas": {"destacar": "x" * 601}},
            {"notas": {"otrosDatos": "x" * 1501}},
            {"notas": {"dirigidoA": "x" * 601}},
            {"campos": ["precio"]},
            {"campos": ["estado"]},
            {"campos": []},
            {"campos": "nombre"},
            {"productoDeSalud": "quizás"},
            {"notas": "texto suelto"},
        ]
        for cuerpo in invalidos:
            mock_login_ok()
            with patch(SERVICIO_IA) as Servicio:
                resp = _client().post("/productos-bot/DEMO-1/contenido/generar", json=cuerpo, headers=AUTH_HEADER)
            assert resp.status_code == 422, cuerpo
            Servicio.return_value.generar.assert_not_called()

    @responses.activate
    def test_el_tope_alcanzado_es_429_con_el_uso(self):
        mock_login_ok()
        with patch(SERVICIO_IA) as Servicio:
            Servicio.return_value.generar.side_effect = TopeDeIAAlcanzadoError(20, 20)
            resp = _client().post("/productos-bot/DEMO-1/contenido/generar", json={}, headers=AUTH_HEADER)

        assert resp.status_code == 429
        assert "20 borradores" in resp.get_json()["error"]
        assert resp.get_json()["uso"] == {"tope": 20, "usadas": 20, "restantes": 0}

    @responses.activate
    def test_errores_conocidos(self):
        casos = [
            (IANoDisponibleError("no configurada"), 503),
            (IAFalloError("falló"), 502),
            (ProductoBotNoEncontradoError("no existe"), 404),
            (TransicionInvalidaError("archivado"), 409),
            (SkuNoExisteEnRocketfyError("ya no existe"), 422),
            (RocketfyRequestError("caído"), 502),
        ]
        for error, estado in casos:
            mock_login_ok()
            with patch(SERVICIO_IA) as Servicio:
                Servicio.return_value.generar.side_effect = error
                resp = _client().post("/productos-bot/DEMO-1/contenido/generar", json={}, headers=AUTH_HEADER)
            assert resp.status_code == estado, error

    @responses.activate
    def test_el_mensaje_de_un_error_de_la_ia_no_expone_detalles_internos(self):
        mock_login_ok()
        with patch(SERVICIO_IA) as Servicio:
            Servicio.return_value.generar.side_effect = IANoDisponibleError("La IA no está configurada correctamente.")
            resp = _client().post("/productos-bot/DEMO-1/contenido/generar", json={}, headers=AUTH_HEADER)
        assert set(resp.get_json()) == {"error"}


class TestUsoDeLaIA:
    @responses.activate
    def test_devuelve_cuantos_borradores_quedan(self):
        mock_login_ok()
        with patch(SERVICIO_IA) as Servicio:
            Servicio.return_value.uso.return_value = UsoIADTO(tope=20, usadas=5, restantes=15)
            resp = _client().get("/productos-bot/contenido/uso", headers=AUTH_HEADER)

        assert resp.status_code == 200
        assert resp.get_json() == {"tope": 20, "usadas": 5, "restantes": 15}

    @responses.activate
    def test_la_ruta_no_se_confunde_con_el_detalle_de_un_producto(self):
        mock_login_ok()
        with patch(SERVICIO_IA) as Uso, patch(SERVICIO) as Productos:
            Uso.return_value.uso.return_value = UsoIADTO(tope=20, usadas=0, restantes=20)
            _client().get("/productos-bot/contenido/uso", headers=AUTH_HEADER)
        Productos.return_value.obtener_detalle.assert_not_called()




def _turno(**cambios):
    datos = dict(
        respuesta="Hola, soy Victoria.",
        herramientas=[LlamadaHerramientaDTO(nombre="registrar_producto", entrada={"producto_sku": "DEMO-1"}, resultado="Producto registrado.")],
        estado={"nombreCliente": "Ana", "productoSku": "DEMO-1", "cantidad": 1, "total": "24.99", "estado": "despachado"},
        escalada=False,
        pedido=PedidoSimuladoDTO(payload={"name": "Ana", "total": "24.99", "not_COD": 0}, confirmado=True),
        avisos=[AvisoSimuladoDTO(canal="telegram", texto="Victoria escaló la conversación. Motivo: x")],
        uso=UsoPruebasDTO(tope=100, usadas=1, restantes=99, max_mensajes=20),
    )
    datos.update(cambios)
    return TurnoSimuladoDTO(**datos)


class TestProbarConVictoria:
    @responses.activate
    def test_sin_login_es_401(self):
        assert _client().post("/productos-bot/DEMO-1/probar", json={"mensaje": "Hola"}).status_code == 401
        assert _client().get("/productos-bot/pruebas/uso").status_code == 401

    @responses.activate
    def test_devuelve_el_turno_en_camel_case(self):
        mock_login_ok()
        with patch(SERVICIO_PRUEBAS) as Servicio:
            Servicio.return_value.probar.return_value = _turno()
            resp = _client().post("/productos-bot/DEMO-1/probar", json={"mensaje": "Hola"}, headers=AUTH_HEADER)

        assert resp.status_code == 200
        cuerpo = resp.get_json()
        assert cuerpo["respuesta"] == "Hola, soy Victoria."
        assert cuerpo["herramientas"] == [{"nombre": "registrar_producto", "entrada": {"producto_sku": "DEMO-1"}, "resultado": "Producto registrado."}]
        assert cuerpo["estado"]["nombreCliente"] == "Ana" and cuerpo["escalada"] is False
        assert cuerpo["pedido"] == {"payload": {"name": "Ana", "total": "24.99", "not_COD": 0}, "confirmado": True}
        assert cuerpo["avisos"] == [{"canal": "telegram", "texto": "Victoria escaló la conversación. Motivo: x"}]
        assert cuerpo["uso"] == {"tope": 100, "usadas": 1, "restantes": 99, "maxMensajes": 20}

    @responses.activate
    def test_sin_pedido_va_null(self):
        mock_login_ok()
        with patch(SERVICIO_PRUEBAS) as Servicio:
            Servicio.return_value.probar.return_value = _turno(pedido=None, avisos=[])
            resp = _client().post("/productos-bot/DEMO-1/probar", json={"mensaje": "Hola"}, headers=AUTH_HEADER)
        assert resp.get_json()["pedido"] is None

    @responses.activate
    def test_pasa_todo_lo_que_importa_al_servicio(self):
        mock_login_ok()
        cuerpo = {
            "mensaje": "  Quiero 2  ",
            "historial": [{"rol": "cliente", "contenido": "Hola", "extra": "se ignora"}, {"rol": "bot", "contenido": "Hola!"}],
            "estado": {"nombreCliente": "Ana", "productoSku": "DEMO-1", "cantidad": 2, "total": "49.98", "metodoPago": "contraentrega", "idPedidoRocketfy": 9000001, "raro": 1},
            "desdeAnuncio": True,
            "escalada": False,
        }
        with patch(SERVICIO_PRUEBAS) as Servicio:
            Servicio.return_value.probar.return_value = _turno()
            resp = _client().post("/productos-bot/DEMO-1/probar", json=cuerpo, headers=AUTH_HEADER)

        assert resp.status_code == 200
        kw = Servicio.return_value.probar.call_args.kwargs
        assert kw["sku"] == "DEMO-1" and kw["mensaje"] == "Quiero 2"
        assert kw["historial"] == [{"rol": "cliente", "contenido": "Hola"}, {"rol": "bot", "contenido": "Hola!"}]
        assert kw["estado"] == {
            "nombre_cliente": "Ana", "producto_sku": "DEMO-1", "cantidad": 2, "total": "49.98",
            "metodo_pago": "contraentrega", "id_pedido_rocketfy": 9000001,
        }
        assert kw["desde_anuncio"] is True and kw["escalada"] is False and kw["usuario"] == CORREO_DE_PRUEBA

    @responses.activate
    def test_lo_que_no_viene_toma_valores_por_defecto(self):
        mock_login_ok()
        with patch(SERVICIO_PRUEBAS) as Servicio:
            Servicio.return_value.probar.return_value = _turno()
            _client().post("/productos-bot/DEMO-1/probar", json={"mensaje": "Hola"}, headers=AUTH_HEADER)
        kw = Servicio.return_value.probar.call_args.kwargs
        assert kw["historial"] == [] and kw["estado"] is None and kw["desde_anuncio"] is False and kw["escalada"] is False

    @responses.activate
    def test_validaciones_de_entrada_no_llegan_al_servicio(self):
        invalidos = [
            {},
            {"mensaje": ""},
            {"mensaje": "   "},
            {"mensaje": "x" * 1001},
            {"mensaje": "Hola", "historial": [{"rol": "admin", "contenido": "hola"}]},
            {"mensaje": "Hola", "historial": [{"rol": "cliente", "contenido": ""}]},
            {"mensaje": "Hola", "historial": [{"rol": "cliente", "contenido": "x" * 4001}]},
            {"mensaje": "Hola", "historial": [{"rol": "cliente", "contenido": "hola"}] * 101},
            {"mensaje": "Hola", "estado": "no-es-un-objeto"},
        ]
        for cuerpo in invalidos:
            mock_login_ok()
            with patch(SERVICIO_PRUEBAS) as Servicio:
                resp = _client().post("/productos-bot/DEMO-1/probar", json=cuerpo, headers=AUTH_HEADER)
            assert resp.status_code == 422, cuerpo
            Servicio.return_value.probar.assert_not_called()

    @responses.activate
    def test_errores_conocidos_se_traducen(self):
        casos = [
            (ProductoBotNoEncontradoError("no existe"), 404, None),
            (TransicionInvalidaError("archivado"), 409, None),
            (PruebaInvalidaError("La prueba ya terminó."), 409, None),
            (PublicacionBloqueadaError(["Falta el nombre del producto."]), 422, "bloqueos"),
            (TopeDePruebasAlcanzadoError(100, 100), 429, "uso"),
            (IANoDisponibleError("sin clave"), 503, None),
            (IAFalloError("no responde"), 502, None),
        ]
        for error, estado, clave in casos:
            mock_login_ok()
            with patch(SERVICIO_PRUEBAS) as Servicio:
                Servicio.return_value.probar.side_effect = error
                resp = _client().post("/productos-bot/DEMO-1/probar", json={"mensaje": "Hola"}, headers=AUTH_HEADER)
            assert resp.status_code == estado, error
            assert "error" in resp.get_json()
            if clave:
                assert clave in resp.get_json()
        # el tope trae el uso para que la app lo muestre
        mock_login_ok()
        with patch(SERVICIO_PRUEBAS) as Servicio:
            Servicio.return_value.probar.side_effect = TopeDePruebasAlcanzadoError(100, 100)
            resp = _client().post("/productos-bot/DEMO-1/probar", json={"mensaje": "Hola"}, headers=AUTH_HEADER)
        assert resp.get_json()["uso"] == {"tope": 100, "usadas": 100, "restantes": 0}

    @responses.activate
    def test_uso_de_las_pruebas(self):
        mock_login_ok()
        with patch(SERVICIO_PRUEBAS) as Servicio:
            Servicio.return_value.uso.return_value = UsoPruebasDTO(tope=100, usadas=12, restantes=88, max_mensajes=20)
            resp = _client().get("/productos-bot/pruebas/uso", headers=AUTH_HEADER)
        assert resp.status_code == 200 and resp.get_json() == {"tope": 100, "usadas": 12, "restantes": 88, "maxMensajes": 20}
