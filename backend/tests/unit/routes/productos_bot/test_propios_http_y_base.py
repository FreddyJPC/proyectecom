"""
Productos propios (ADR-012) en la capa HTTP y contra la base real: crear con envío en una sola transacción, SKU
generado, lecturas con proveedor y categoría, y los nuevos campos editables.
"""
from decimal import Decimal
from unittest.mock import patch

import psycopg2.errors
import pytest
import responses

from src.app import create_app
from src.config.database import get_connection
from src.routes.entregas.repository import EntregaRepository
from src.routes.productos_bot.exceptions import DatosDeProductoInvalidosError
from src.routes.productos_bot.repository import COLUMNAS_EDITABLES, ProductoBotGestionRepository as Repo
from src.routes.whatsapp.repository import ProductoBotRepository
from tests.conftest import AUTH_HEADER, mock_login_ok
from tests.unit.routes.productos_bot.test_controllers import SERVICIO, _client, _detalle

PREFIJO = "TEST-PROPIOS "


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from productos_bot where nombre like %s", (PREFIJO + "%",))  # cascada: entregas
            cur.execute("delete from categorias_producto where nombre like %s", (PREFIJO + "%",))


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def _datos(**cambios):
    datos = {
        "nombre": PREFIJO + "Zapatos", "descripcion": "Hechos a mano", "precio": Decimal("30.00"), "variantes": "38 a 42",
        "tiempo_entrega": "2 días", "metodos_pago_aceptados": "contraentrega", "preguntas_frecuentes": None,
        "temas_no_responder": None, "max_unidades_por_pedido": 2, "categoria_id": None, "costo_propio": Decimal("18.00"),
        "controla_stock": True, "stock_ultimo": 5, "envio_incluido": False, "costo_flete_estimado": Decimal("1.50"),
    }
    datos.update(cambios)
    return datos


ENTREGA = {
    "nombre": "Envío en Cuenca", "tipo": "envio", "costo_cliente": Decimal("2.00"), "costo_negocio": Decimal("1.00"),
    "cantones": ["Cuenca"], "provincias": [], "resto_del_pais": False, "direccion_retiro": None, "tiempo_entrega": "mismo día",
    "activo": True,
}


class TestRepositorio:
    def test_crear_propio_genera_sku_y_nace_como_borrador_con_su_proveedor(self):
        fila = Repo.crear_propio(_datos(), [ENTREGA])

        assert fila["sku"].startswith("PROP-") and len(fila["sku"]) == 9
        assert (fila["estado"], fila["activo"]) == ("borrador", False)
        assert (fila["proveedor_clave"], fila["proveedor_cierre"], fila["proveedor_nombre"]) == ("propio", "manual", "Producto propio")
        assert fila["costo_propio"] == Decimal("18.00") and fila["stock_ultimo"] == 5 and fila["stock_actualizado_en"] is not None
        assert fila["envio_incluido"] is False and fila["costo_flete_estimado"] == Decimal("1.50")
        assert [e["nombre"] for e in EntregaRepository.listar(fila["sku"])] == ["Envío en Cuenca"]

    def test_dos_productos_propios_no_comparten_sku(self):
        a, b = Repo.crear_propio(_datos(), []), Repo.crear_propio(_datos(), [])
        assert a["sku"] != b["sku"]

    def test_un_borrador_propio_no_lo_ve_victoria_y_uno_activo_si_con_su_cierre(self):
        fila = Repo.crear_propio(_datos(), [])
        assert fila["sku"] not in [p["sku"] for p in ProductoBotRepository.listar_activos()]

        Repo.cambiar_estado(fila["sku"], "activo", "test")
        visto = ProductoBotRepository.obtener_por_sku(fila["sku"])

        assert visto["proveedor_cierre"] == "manual" and visto["envio_incluido"] is False
        assert visto["controla_stock"] is True and visto["stock_ultimo"] == 5
        assert fila["sku"] in [p["sku"] for p in ProductoBotRepository.listar_activos()]

    def test_los_productos_de_rocketfy_siguen_siendo_de_rocketfy(self):
        creado = Repo.crear_borrador(
            "TEST-PROPIOS-RKT", PREFIJO + "De Rocketfy", "Desc", Decimal("29.90"), "contraentrega",
            {"rocketfy_product_id": 1, "costo_rocketfy": Decimal("10.00"), "precio_sugerido_rocketfy": Decimal("29.90"),
             "stock_ultimo": 4, "peso_kg": Decimal("0.1"), "imagen_url": None},
        )
        assert (creado["proveedor_clave"], creado["proveedor_cierre"], creado["envio_incluido"]) == ("rocketfy", "rocketfy", True)

    def test_crear_con_entregas_es_todo_o_nada(self):
        malas = [{**ENTREGA, "tipo": "tipo-que-la-base-rechaza"}]
        with pytest.raises(psycopg2.errors.CheckViolation):
            Repo.crear_propio(_datos(nombre=PREFIJO + "Atómico"), malas)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from productos_bot where nombre = %s", (PREFIJO + "Atómico",))
                assert cur.fetchone()[0] == 0

    def test_editar_el_stock_actualiza_la_fecha_del_stock(self):
        fila = Repo.crear_propio(_datos(), [])
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update productos_bot set stock_actualizado_en = now() - interval '2 days' where sku = %s", (fila["sku"],))
        antes = Repo.obtener(fila["sku"])["stock_actualizado_en"]

        despues = Repo.actualizar_campos(fila["sku"], {"stock_ultimo": 9})

        assert despues["stock_ultimo"] == 9 and despues["stock_actualizado_en"] > antes

    def test_los_campos_nuevos_son_editables_pero_nada_mas(self):
        assert {"categoria_id", "envio_incluido", "costo_flete_estimado", "costo_propio", "controla_stock", "stock_ultimo"} <= COLUMNAS_EDITABLES
        assert not ({"proveedor_id", "sku", "estado", "activo"} & COLUMNAS_EDITABLES)
        with pytest.raises(ValueError):
            Repo.actualizar_campos("x", {"proveedor_id": 1})

    def test_la_categoria_viaja_en_la_lectura(self):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("insert into categorias_producto (nombre) values (%s) returning id", (PREFIJO + "Calzado",))
                categoria_id = cur.fetchone()[0]
        fila = Repo.crear_propio(_datos(categoria_id=categoria_id), [])
        assert (fila["categoria_id"], fila["categoria_nombre"]) == (categoria_id, PREFIJO + "Calzado")
        assert Repo.listar()[0]["proveedor_clave"] in ("propio", "rocketfy")


class TestEntregasRepositorio:
    def test_reemplazar_deja_exactamente_las_nuevas_en_orden(self):
        fila = Repo.crear_propio(_datos(), [ENTREGA])
        nuevas = [
            {**ENTREGA, "nombre": "Retiro", "tipo": "retiro", "cantones": [], "direccion_retiro": "Calle 1", "costo_cliente": Decimal("0.00")},
            {**ENTREGA, "nombre": "Resto", "cantones": [], "resto_del_pais": True, "costo_cliente": Decimal("5.00")},
        ]

        listadas = EntregaRepository.reemplazar(fila["sku"], nuevas)

        assert [e["nombre"] for e in listadas] == ["Retiro", "Resto"]
        assert listadas[1]["resto_del_pais"] is True and listadas[1]["costo_cliente"] == Decimal("5.00")
        assert EntregaRepository.obtener(listadas[0]["id"])["direccion_retiro"] == "Calle 1"

    def test_solo_activas(self):
        fila = Repo.crear_propio(_datos(), [ENTREGA, {**ENTREGA, "nombre": "Pausada", "activo": False}])
        assert [e["nombre"] for e in EntregaRepository.listar(fila["sku"], solo_activas=True)] == ["Envío en Cuenca"]
        assert len(EntregaRepository.listar(fila["sku"])) == 2

    def test_al_borrar_el_producto_se_borran_sus_entregas(self):
        fila = Repo.crear_propio(_datos(), [ENTREGA])
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from productos_bot where sku = %s", (fila["sku"],))
        assert EntregaRepository.listar(fila["sku"]) == []

    def test_la_base_rechaza_un_costo_negativo(self):
        fila = Repo.crear_propio(_datos(), [])
        with pytest.raises(psycopg2.errors.CheckViolation):
            EntregaRepository.reemplazar(fila["sku"], [{**ENTREGA, "costo_cliente": Decimal("-1.00")}])

    def test_pedidos_de_30_dias_cuentan_tambien_las_ventas_de_productos_propios(self):
        fila = Repo.crear_propio(_datos(), [])
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into ventas (proveedor_id, estado, subtotal, total, telefono) values (2, 'por_gestionar', 30, 30, 'test-ventas-30d') returning id"
                )
                venta_id = cur.fetchone()[0]
                cur.execute(
                    "insert into ventas_lineas (venta_id, producto_sku, producto_nombre, cantidad, precio_unitario) values (%s, %s, 'x', 1, 30)",
                    (venta_id, fila["sku"]),
                )
        try:
            assert Repo.contar_pedidos_por_sku(30).get(fila["sku"].upper()) == 1
        finally:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("delete from ventas where telefono = 'test-ventas-30d'")


CUERPO_PROPIO = {
    "nombre": "Zapatos", "descripcion": "Hechos a mano", "precio": 30, "costoPropio": 18, "controlaStock": True, "stock": 5,
    "tiempoEntrega": "2 días", "metodosPago": ["contraentrega"], "envioIncluido": False,
    "entregas": [{"nombre": "Envío en Cuenca", "costoCliente": 2, "cantones": ["Cuenca"]}],
}


class TestHTTP:
    @responses.activate
    def test_crear_producto_propio(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.crear_propio.return_value = _detalle(sku="PROP-0001", proveedor="propio", proveedor_nombre="Producto propio")
            r = _client().post("/productos-bot/propios", json=CUERPO_PROPIO, headers=AUTH_HEADER)

        assert r.status_code == 201 and r.get_json()["sku"] == "PROP-0001" and r.get_json()["proveedor"] == "propio"
        datos, entregas, usuario = servicio.return_value.crear_propio.call_args.args
        assert datos["nombre"] == "Zapatos" and datos["precio"] == Decimal("30") and datos["costo_propio"] == Decimal("18")
        assert datos["controla_stock"] is True and datos["stock_ultimo"] == 5 and datos["envio_incluido"] is False
        assert datos["metodos_pago_aceptados"] == "contraentrega" and datos["max_unidades_por_pedido"] == 1
        assert entregas[0]["nombre"] == "Envío en Cuenca" and entregas[0]["costo_cliente"] == Decimal("2")
        assert usuario == "freddyjavier556@gmail.com"

    @responses.activate
    def test_sin_control_de_stock_no_se_guarda_ninguna_cantidad(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.crear_propio.return_value = _detalle(sku="PROP-0002")
            _client().post("/productos-bot/propios", json={**CUERPO_PROPIO, "controlaStock": False, "stock": 99}, headers=AUTH_HEADER)
        assert servicio.return_value.crear_propio.call_args.args[0]["stock_ultimo"] is None

    @responses.activate
    def test_con_control_de_stock_las_unidades_son_obligatorias(self):
        mock_login_ok()
        cuerpo = {k: v for k, v in CUERPO_PROPIO.items() if k != "stock"}
        r = _client().post("/productos-bot/propios", json=cuerpo, headers=AUTH_HEADER)
        assert r.status_code == 422 and "stock" in str(r.get_json()["detalle"])

    @responses.activate
    @pytest.mark.parametrize("cambio", [{"precio": 0}, {"precio": -3}, {"costoPropio": -1}, {"nombre": ""}, {"descripcion": ""},
                                        {"metodosPago": []}, {"metodosPago": ["efectivo"]}, {"stock": -1}, {"tiempoEntrega": ""}])
    def test_datos_invalidos_son_422(self, cambio):
        mock_login_ok()
        r = _client().post("/productos-bot/propios", json={**CUERPO_PROPIO, **cambio}, headers=AUTH_HEADER)
        assert r.status_code == 422

    @responses.activate
    def test_el_servicio_puede_rechazar_las_entregas_con_422(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.crear_propio.side_effect = DatosDeProductoInvalidosError(["Opción 1: falta el nombre."])
            r = _client().post("/productos-bot/propios", json=CUERPO_PROPIO, headers=AUTH_HEADER)
        assert r.status_code == 422 and r.get_json()["detalle"] == {"producto": ["Opción 1: falta el nombre."]}

    @responses.activate
    def test_guardar_y_copiar_entregas(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.guardar_entregas.return_value = _detalle()
            r = _client().put(
                "/productos-bot/PROP-0001/entregas",
                json={"entregas": [{"nombre": "Retiro", "tipo": "retiro", "direccionRetiro": "Calle 1", "costoCliente": 0}]},
                headers=AUTH_HEADER,
            )
        assert r.status_code == 200
        sku, entregas, _ = servicio.return_value.guardar_entregas.call_args.args
        assert sku == "PROP-0001" and entregas[0]["direccion_retiro"] == "Calle 1" and entregas[0]["tipo"] == "retiro"

        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.copiar_entregas.return_value = _detalle()
            r = _client().post("/productos-bot/PROP-0002/entregas/copiar", json={"desdeSku": "PROP-0001"}, headers=AUTH_HEADER)
        assert r.status_code == 200
        servicio.return_value.copiar_entregas.assert_called_once_with("PROP-0002", "PROP-0001", "freddyjavier556@gmail.com")

    @responses.activate
    def test_el_detalle_muestra_proveedor_categoria_envio_y_entregas(self):
        mock_login_ok()
        entrega = {
            "id": 1, "nombre": "Envío en Cuenca", "tipo": "envio", "costo_cliente": "2.00", "costo_negocio": "1.00",
            "cantones": ["Cuenca"], "provincias": [], "resto_del_pais": False, "direccion_retiro": None,
            "tiempo_entrega": None, "activo": True,
        }
        with patch(SERVICIO) as servicio:
            servicio.return_value.obtener_detalle.return_value = _detalle(
                proveedor="propio", proveedor_nombre="Producto propio", categoria_id=3, categoria="Calzado",
                costo_propio="18.00", controla_stock=True, envio_incluido=False, costo_flete_estimado="1.50", entregas=[entrega],
            )
            body = _client().get("/productos-bot/PROP-0001", headers=AUTH_HEADER).get_json()

        assert (body["proveedor"], body["proveedorNombre"], body["categoria"], body["categoriaId"]) == ("propio", "Producto propio", "Calzado", 3)
        assert (body["costoPropio"], body["controlaStock"], body["envioIncluido"], body["costoFleteEstimado"]) == ("18.00", True, False, "1.50")
        assert body["entregas"][0]["costoCliente"] == "2.00" and body["entregas"][0]["restoDelPais"] is False

    @responses.activate
    def test_editar_acepta_los_campos_nuevos(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.editar.return_value = _detalle()
            r = _client().patch(
                "/productos-bot/PROP-0001",
                json={"costoPropio": 20, "stock": 7, "controlaStock": True, "envioIncluido": True, "costoFleteEstimado": None, "categoriaId": None},
                headers=AUTH_HEADER,
            )
        assert r.status_code == 200
        cambios = servicio.return_value.editar.call_args.args[1]
        assert cambios == {
            "costo_propio": Decimal("20"), "stock_ultimo": 7, "controla_stock": True, "envio_incluido": True,
            "costo_flete_estimado": None, "categoria_id": None,
        }
