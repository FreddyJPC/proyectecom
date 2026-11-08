"""
Productos PROPIOS (ADR-012) en el servicio de gestión: se crean a mano, no se verifican contra Rocketfy, llevan
su propio stock y su propio envío. Con repositorios en memoria: sin base de datos ni red.
"""
from decimal import Decimal

import pytest

from src.routes.productos_bot.exceptions import (
    DatosDeProductoInvalidosError,
    PublicacionBloqueadaError,
    TransicionInvalidaError,
)
from src.routes.productos_bot.services import ProductosBotService
from src.routes.productos_bot.sincronizacion import SincronizacionProductosService
from tests.unit.routes.productos_bot.test_services import AjustesFalsos, MonitoreoFalso, RepoEnMemoria, RocketfyFalso, _fila
from tests.unit.routes.productos_bot.test_sincronizacion import (
    AlertasFalsas,
    RocketfyPorSku,
    TelegramFalso,
    en_rocketfy,
)


def _propio(**cambios):
    fila = _fila(
        id=2, sku="PROP-0001", nombre="Zapatos de cuero", descripcion="Zapatos hechos a mano.", precio=Decimal("30.00"),
        rocketfy_product_id=None, costo_rocketfy=None, precio_sugerido_rocketfy=None, stock_ultimo=5, peso_kg=None,
        imagen_url=None, proveedor_id=2, proveedor_clave="propio", proveedor_nombre="Producto propio",
        proveedor_cierre="manual", categoria_id=None, categoria_nombre=None, costo_propio=Decimal("18.00"),
        controla_stock=True, envio_incluido=True, costo_flete_estimado=None,
    )
    fila.update(cambios)
    return fila


def _de_rocketfy(**cambios):
    datos = dict(proveedor_id=1, proveedor_clave="rocketfy", proveedor_nombre="Rocketfy", proveedor_cierre="rocketfy",
                 categoria_id=None, categoria_nombre=None, costo_propio=None, controla_stock=True, envio_incluido=True,
                 costo_flete_estimado=None)
    datos.update(cambios)
    return _fila(**datos)


class RepoConPropios(RepoEnMemoria):
    def crear_propio(self, datos, entregas):
        sku = f"PROP-{len([s for s in self.filas if s.startswith('PROP-')]) + 1:04d}"
        fila = _propio(
            sku=sku, nombre=datos["nombre"], descripcion=datos["descripcion"], precio=datos["precio"],
            tiempo_entrega=datos["tiempo_entrega"], metodos_pago_aceptados=datos["metodos_pago_aceptados"],
            costo_propio=datos.get("costo_propio"), controla_stock=datos["controla_stock"],
            stock_ultimo=datos.get("stock_ultimo"), envio_incluido=datos["envio_incluido"],
            max_unidades_por_pedido=datos["max_unidades_por_pedido"], estado="borrador", activo=False,
            costo_flete_estimado=datos.get("costo_flete_estimado"),
        )
        self.filas[sku] = fila
        self.entregas_creadas = {sku: entregas}
        return dict(fila)


class EntregasEnMemoria:
    def __init__(self, por_sku=None):
        self.por_sku = {k: [dict(o) for o in v] for k, v in (por_sku or {}).items()}

    def listar(self, sku, solo_activas=False):
        return [dict(o) for o in self.por_sku.get(sku, []) if not solo_activas or o["activo"]]

    def reemplazar(self, sku, opciones):
        self.por_sku[sku] = [{**o, "id": i + 1, "producto_sku": sku, "orden": i} for i, o in enumerate(opciones)]
        return self.listar(sku)


class CategoriasEnMemoria:
    def __init__(self, categorias=None):
        self.categorias = categorias or {3: {"id": 3, "nombre": "Calzado", "activo": True}, 4: {"id": 4, "nombre": "Vieja", "activo": False}}

    def obtener(self, categoria_id):
        return self.categorias.get(categoria_id)


def _opcion_valida(**cambios):
    opcion = {"nombre": "Envío en Cuenca", "tipo": "envio", "costo_cliente": "2.00", "cantones": ["Cuenca"]}
    opcion.update(cambios)
    return opcion


def _servicio(filas=(), entregas=None, ajustes=None, rocketfy=None):
    repo = RepoConPropios(filas)
    rocketfy = rocketfy or RocketfyFalso()
    monitoreo = MonitoreoFalso()
    entregas_repo = EntregasEnMemoria(entregas)
    servicio = ProductosBotService(
        client=rocketfy, repo=repo, monitoreo_repo=monitoreo, ajustes_service=ajustes or AjustesFalsos(),
        entregas_repo=entregas_repo, categorias_repo=CategoriasEnMemoria(),
    )
    return servicio, repo, rocketfy, monitoreo, entregas_repo


DATOS_NUEVO = {
    "nombre": "Zapatos de cuero", "descripcion": "Hechos a mano.", "precio": Decimal("30.00"),
    "costo_propio": Decimal("18.00"), "controla_stock": True, "stock_ultimo": 5, "categoria_id": 3,
    "variantes": "talla 38 a 42", "tiempo_entrega": "2 días", "metodos_pago_aceptados": "contraentrega",
    "preguntas_frecuentes": None, "temas_no_responder": None, "max_unidades_por_pedido": 2,
    "envio_incluido": False, "costo_flete_estimado": None,
}


class TestCrearPropio:
    def test_nace_como_borrador_con_sku_generado_y_su_envio(self):
        servicio, repo, rocketfy, _, _ = _servicio()

        detalle = servicio.crear_propio(dict(DATOS_NUEVO), [_opcion_valida()], "freddy@azoshop.com")

        assert detalle.sku == "PROP-0001" and detalle.estado == "borrador"
        assert detalle.proveedor == "propio" and detalle.proveedor_nombre == "Producto propio"
        assert repo.filas["PROP-0001"]["activo"] is False
        assert repo.historial[-1]["accion"] == "creado" and repo.historial[-1]["cambios"] == {"desde": "propio"}
        assert rocketfy.consultas == []  # no existe en Rocketfy: ni se pregunta

    def test_opciones_de_entrega_mal_armadas_no_crean_nada(self):
        servicio, repo, _, _, _ = _servicio()
        with pytest.raises(DatosDeProductoInvalidosError) as error:
            servicio.crear_propio(dict(DATOS_NUEVO), [{"nombre": "Sin cobertura", "tipo": "envio"}], "x")
        assert "Opción 1" in error.value.mensajes[0]
        assert repo.filas == {}

    def test_categoria_inexistente_o_desactivada(self):
        servicio, repo, _, _, _ = _servicio()
        for categoria in (99, 4):
            with pytest.raises(DatosDeProductoInvalidosError):
                servicio.crear_propio({**DATOS_NUEVO, "categoria_id": categoria}, [], "x")
        assert repo.filas == {}


class TestPublicarPropio:
    def test_se_publica_sin_consultar_rocketfy_ni_vigilar_el_stock(self):
        servicio, repo, rocketfy, monitoreo, _ = _servicio([_propio()])

        detalle = servicio.publicar("PROP-0001", "freddy@azoshop.com")

        assert detalle.estado == "activo" and repo.filas["PROP-0001"]["activo"] is True
        assert rocketfy.consultas == []
        assert monitoreo.upserts == []  # Vigilados consulta Rocketfy: un producto propio no va ahí

    def test_no_se_aplica_el_minimo_de_10_dolares_de_rocketfy(self):
        servicio, *_ = _servicio([_propio(precio=Decimal("4.00"), costo_propio=Decimal("2.00"))])
        assert servicio.publicar("PROP-0001", "x").estado == "activo"

    def test_no_se_puede_vender_bajo_el_costo(self):
        servicio, *_ = _servicio([_propio(precio=Decimal("15.00"), costo_propio=Decimal("18.00"))])
        with pytest.raises(PublicacionBloqueadaError) as error:
            servicio.publicar("PROP-0001", "x")
        assert "no cubre tu costo" in error.value.bloqueos[0] and "Rocketfy" not in error.value.bloqueos[0]

    def test_con_control_de_stock_y_cero_unidades_no_se_publica(self):
        servicio, *_ = _servicio([_propio(stock_ultimo=0)])
        with pytest.raises(PublicacionBloqueadaError) as error:
            servicio.publicar("PROP-0001", "x")
        assert any("No hay stock" in b and "Rocketfy" not in b for b in error.value.bloqueos)

    def test_sin_control_de_stock_se_publica_aunque_no_haya_unidades_anotadas(self):
        servicio, *_ = _servicio([_propio(controla_stock=False, stock_ultimo=None)])
        detalle = servicio.publicar("PROP-0001", "x")
        assert detalle.estado == "activo"
        assert any("No llevas el control de stock" in a for a in detalle.verificacion.avisos)

    def test_envio_cobrado_aparte_exige_al_menos_una_opcion(self):
        servicio, *_ = _servicio([_propio(envio_incluido=False)])
        with pytest.raises(PublicacionBloqueadaError) as error:
            servicio.publicar("PROP-0001", "x")
        assert any("Falta definir el envío" in b for b in error.value.bloqueos)

    def test_con_una_opcion_de_entrega_activa_se_publica(self):
        opcion = {**_opcion_valida(), "activo": True, "id": 1, "costo_negocio": None, "provincias": [], "resto_del_pais": False,
                  "direccion_retiro": None, "tiempo_entrega": None}
        servicio, *_ = _servicio([_propio(envio_incluido=False)], entregas={"PROP-0001": [opcion]})
        assert servicio.publicar("PROP-0001", "x").estado == "activo"

    def test_sin_costo_anotado_avisa_pero_no_bloquea(self):
        servicio, *_ = _servicio([_propio(costo_propio=None)])
        detalle = servicio.publicar("PROP-0001", "x")
        assert any("no se podrá calcular tu ganancia" in a for a in detalle.verificacion.avisos)


class TestEditarPropio:
    def test_un_propio_acepta_costo_y_stock(self):
        servicio, repo, *_ = _servicio([_propio()])
        detalle = servicio.editar("PROP-0001", {"costo_propio": Decimal("20.00"), "stock_ultimo": 9}, "x")
        assert detalle.costo_propio == "20.00" and detalle.stock_ultimo == 9

    def test_un_producto_de_rocketfy_no_acepta_costo_propio_ni_stock_a_mano(self):
        servicio, *_ = _servicio([_de_rocketfy()])
        for cambio in ({"costo_propio": Decimal("5.00")}, {"stock_ultimo": 3}, {"controla_stock": False}):
            with pytest.raises(DatosDeProductoInvalidosError):
                servicio.editar("DEMO-1", cambio, "x")

    def test_un_producto_de_rocketfy_si_puede_tener_envio_aparte_y_flete_propio(self):
        servicio, *_ = _servicio([_de_rocketfy()])
        detalle = servicio.editar("DEMO-1", {"costo_flete_estimado": Decimal("8.00")}, "x")
        assert detalle.costo_flete_estimado == "8.00"

    def test_activar_el_control_de_stock_exige_las_unidades(self):
        servicio, *_ = _servicio([_propio(controla_stock=False, stock_ultimo=None)])
        with pytest.raises(DatosDeProductoInvalidosError):
            servicio.editar("PROP-0001", {"controla_stock": True}, "x")
        assert servicio.editar("PROP-0001", {"controla_stock": True, "stock_ultimo": 4}, "x").stock_ultimo == 4

    def test_categoria_invalida(self):
        servicio, *_ = _servicio([_propio()])
        with pytest.raises(DatosDeProductoInvalidosError):
            servicio.editar("PROP-0001", {"categoria_id": 99}, "x")

    def test_un_producto_a_la_venta_no_puede_quedar_con_envio_aparte_y_sin_opciones(self):
        servicio, *_ = _servicio([_propio(estado="activo", activo=True)])
        with pytest.raises(PublicacionBloqueadaError) as error:
            servicio.editar("PROP-0001", {"envio_incluido": False}, "x")
        assert any("Falta definir el envío" in b for b in error.value.bloqueos)

    def test_actualizar_desde_rocketfy_no_aplica_a_un_propio(self):
        servicio, *_ = _servicio([_propio()])
        with pytest.raises(TransicionInvalidaError):
            servicio.actualizar_desde_rocketfy("PROP-0001", "x")


class TestEntregasPorProducto:
    def test_guardar_reemplaza_todas_y_aparecen_en_el_detalle(self):
        servicio, repo, _, _, entregas = _servicio([_propio(envio_incluido=False)])

        detalle = servicio.guardar_entregas("PROP-0001", [_opcion_valida(), _opcion_valida(nombre="Resto", cantones=[], resto_del_pais=True, costo_cliente="5")], "x")

        assert [e["nombre"] for e in detalle.entregas] == ["Envío en Cuenca", "Resto"]
        assert detalle.entregas[1]["costo_cliente"] == "5.00"

    def test_un_producto_a_la_venta_con_envio_aparte_no_puede_quedarse_sin_opciones(self):
        opcion = {**_opcion_valida(), "activo": True, "id": 1, "costo_negocio": None, "provincias": [], "resto_del_pais": False,
                  "direccion_retiro": None, "tiempo_entrega": None}
        servicio, _, _, _, entregas = _servicio([_propio(envio_incluido=False, estado="activo", activo=True)], entregas={"PROP-0001": [opcion]})
        with pytest.raises(PublicacionBloqueadaError):
            servicio.guardar_entregas("PROP-0001", [], "x")
        assert len(entregas.listar("PROP-0001")) == 1

    def test_opciones_invalidas_no_se_guardan(self):
        servicio, _, _, _, entregas = _servicio([_propio()])
        with pytest.raises(DatosDeProductoInvalidosError):
            servicio.guardar_entregas("PROP-0001", [{"nombre": "x", "tipo": "retiro"}], "x")
        assert entregas.listar("PROP-0001") == []

    def test_copiar_el_envio_de_otro_producto(self):
        origen = {**_opcion_valida(), "activo": True, "id": 1, "costo_negocio": None, "provincias": [], "resto_del_pais": False,
                  "direccion_retiro": None, "tiempo_entrega": None, "cantones": ["Cuenca"], "tipo": "envio",
                  "costo_cliente": Decimal("2.00"), "producto_sku": "PROP-0001", "orden": 0}
        servicio, _, _, _, entregas = _servicio(
            [_propio(), _propio(id=3, sku="PROP-0002", nombre="Cinturón")], entregas={"PROP-0001": [origen]}
        )

        detalle = servicio.copiar_entregas("PROP-0002", "PROP-0001", "x")

        assert [e["nombre"] for e in detalle.entregas] == ["Envío en Cuenca"]
        assert detalle.entregas[0]["costo_cliente"] == "2.00"
        assert len(entregas.listar("PROP-0001")) == 1  # el origen queda igual


class TestPrecioDeUnPropio:
    def test_el_piso_es_el_costo_no_los_10_dolares(self):
        servicio, *_ = _servicio([_propio(costo_propio=Decimal("3.00"), precio=Decimal("5.00"))])
        recomendacion = servicio.recomendar_precio("PROP-0001", precio=Decimal("5.00"))
        assert recomendacion.piso == "3.00"
        assert recomendacion.evaluacion.bajo_piso is False

    def test_usa_el_flete_del_producto_en_lugar_del_general(self):
        ajustes = AjustesFalsos(envio_estimado=Decimal("5.00"), confirmado=True, margen_minimo_pct=Decimal("25.00"), margen_objetivo_pct=Decimal("35.00"))
        servicio, *_ = _servicio(
            [_de_rocketfy(costo_flete_estimado=Decimal("9.00"), precio=Decimal("34.90"))], ajustes=ajustes
        )
        recomendacion = servicio.recomendar_precio("DEMO-1", precio=Decimal("34.90"))
        assert recomendacion.envio_estimado == "9.00"
        assert recomendacion.evaluacion.ganancia == "15.90"  # 34.90 - 10.00 - 9.00

    def test_con_envio_cobrado_aparte_el_flete_no_resta_del_precio(self):
        ajustes = AjustesFalsos(envio_estimado=Decimal("5.00"), confirmado=True)
        servicio, *_ = _servicio([_propio(envio_incluido=False)], ajustes=ajustes)
        assert servicio.recomendar_precio("PROP-0001", precio=Decimal("30.00")).envio_estimado == "0.00"

    def test_el_flete_anotado_por_el_dueno_cuenta_aunque_los_ajustes_no_esten_confirmados(self):
        ajustes = AjustesFalsos(envio_estimado=Decimal("5.00"), confirmado=False)
        servicio, *_ = _servicio([_de_rocketfy(costo_flete_estimado=Decimal("30.00"), precio=Decimal("34.90"))], ajustes=ajustes)
        with pytest.raises(PublicacionBloqueadaError):
            servicio.publicar("DEMO-1", "x")  # 34.90 < costo 10 + flete 30


class TestListaYSincronizacion:
    def test_la_lista_trae_proveedor_categoria_y_stock(self):
        servicio, *_ = _servicio([_propio(categoria_id=3, categoria_nombre="Calzado", controla_stock=False, envio_incluido=False), _de_rocketfy()])
        lista = {p.sku: p for p in servicio.listar()}
        assert (lista["PROP-0001"].proveedor, lista["PROP-0001"].categoria) == ("propio", "Calzado")
        assert lista["PROP-0001"].controla_stock is False and lista["PROP-0001"].envio_incluido is False
        assert (lista["DEMO-1"].proveedor, lista["DEMO-1"].controla_stock) == ("rocketfy", True)

    def test_la_sincronizacion_horaria_no_toca_los_productos_propios(self):
        propio = _propio(estado="activo", activo=True)
        rocketfy = _de_rocketfy(estado="activo", activo=True, precio=Decimal("34.90"), costo_rocketfy=Decimal("10.00"), stock_ultimo=50)
        repo = RepoConPropios([propio, rocketfy])
        catalogo = RocketfyPorSku([en_rocketfy(stock=7)])
        productos = ProductosBotService(
            client=catalogo, repo=repo, monitoreo_repo=MonitoreoFalso(), ajustes_service=AjustesFalsos(),
            entregas_repo=EntregasEnMemoria(), categorias_repo=CategoriasEnMemoria(),
        )
        sincronizacion = SincronizacionProductosService(
            productos=productos, repo=repo, alertas=AlertasFalsas(), monitoreo=MonitoreoFalso(),
            ajustes_service=AjustesFalsos(confirmado=True), telegram=TelegramFalso(),
        )

        resultado = sincronizacion.sincronizar_todos()

        assert resultado.revisados == 1
        assert catalogo.consultas == ["DEMO-1"]  # a Rocketfy solo se le pregunta por el suyo
        assert repo.filas["PROP-0001"]["stock_ultimo"] == 5 and repo.filas["PROP-0001"]["estado"] == "activo"
