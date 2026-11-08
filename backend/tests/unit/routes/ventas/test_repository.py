"""
Contra la base real (la de pruebas local): el cierre de una venta propia debe ser TODO O NADA
(stock, venta, lead, solicitud de gestión y conversación en una sola transacción). Autocontenido:
SKU y teléfono de prueba propios, con limpieza antes y después.
"""
from decimal import Decimal

import pytest

from src.config.database import get_connection
from src.routes.productos_bot.repository import ProductoBotGestionRepository as ProductosRepo
from src.routes.ventas.exceptions import StockInsuficienteError, VentaYaRegistradaError
from src.routes.ventas.repository import VentasRepository
from src.routes.ventas.snapshot import armar_venta
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository

TELEFONO = "593900001234"
ID_ANUNCIO = "anuncio-ventas-test"


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from ventas where telefono = %s", (TELEFONO,))
            cur.execute("delete from conversaciones where telefono = %s", (TELEFONO,))  # cascada: leads, solicitudes
            cur.execute("delete from productos_bot where nombre like 'TEST-VENTAS %'")


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def _producto(stock=3, controla=True, **cambios):
    datos = {
        "nombre": "TEST-VENTAS Zapatos", "descripcion": "Zapatos de cuero", "precio": Decimal("30.00"),
        "tiempo_entrega": "2 días", "metodos_pago_aceptados": "contraentrega", "max_unidades_por_pedido": 5,
        "costo_propio": Decimal("18.00"), "controla_stock": controla, "stock_ultimo": stock if controla else None,
        "envio_incluido": True, "costo_flete_estimado": None, "categoria_id": None,
    }
    datos.update(cambios)
    fila = ProductosRepo.crear_propio(datos, [])
    return ProductosRepo.cambiar_estado(fila["sku"], "activo", "test")


def _lead_listo(producto, cantidad=2):
    conversacion = ConversacionRepository.crear(telefono=TELEFONO, origen="fep", id_anuncio=ID_ANUNCIO)
    lead = LeadRepository.obtener_o_crear(conversacion["id"], telefono=TELEFONO)
    LeadRepository.actualizar_datos_cliente(lead["id"], "Ana", "Calle 1", "Cuenca", "Azuay")
    LeadRepository.actualizar_producto(
        lead["id"], producto["sku"], producto["nombre"], Decimal("30.00") * cantidad, variante="talla 40", cantidad=cantidad
    )
    LeadRepository.actualizar_metodo_pago(lead["id"], "contraentrega", esperar_comprobante=False)
    return LeadRepository.obtener_por_id(lead["id"]), ConversacionRepository.obtener_por_id(conversacion["id"])


def _cerrar(producto, lead, conversacion):
    venta, lineas = armar_venta(lead, producto, conversacion, None, "por_gestionar", Decimal("0.00"))
    return VentasRepository.cerrar_manual(
        venta, lineas, producto["sku"], int(lead["cantidad"]), bool(producto["controla_stock"]), "2 x Zapatos · total $60.00"
    )


def _stock(sku):
    return ProductosRepo.obtener(sku)["stock_ultimo"]


def _estado_conversacion(conversacion_id):
    return ConversacionRepository.obtener_por_id(conversacion_id)["estado"]


class TestCerrarManual:
    def test_cierra_todo_en_una_transaccion(self):
        producto = _producto(stock=5)
        lead, conversacion = _lead_listo(producto, cantidad=2)

        resultado = _cerrar(producto, lead, conversacion)

        assert resultado["stock_restante"] == 3 and _stock(producto["sku"]) == 3
        assert resultado["pausado_por_agotado"] is False
        assert LeadRepository.obtener_por_id(lead["id"])["estado"] == "por_gestionar"
        assert _estado_conversacion(conversacion["id"]) == "en_gestion"

        venta = VentasRepository.obtener_por_lead(lead["id"])
        assert venta["estado"] == "por_gestionar" and venta["proveedor_id"] == 2
        assert venta["total"] == Decimal("60.00") and venta["costo_productos"] == Decimal("36.00")
        assert (venta["canal"], venta["id_anuncio"]) == ("fep", ID_ANUNCIO)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select producto_sku, cantidad, precio_unitario, costo_unitario, variante from ventas_lineas where venta_id = %s", (venta["id"],))
                assert cur.fetchall() == [(producto["sku"], 2, Decimal("30.00"), Decimal("18.00"), "talla 40")]
                cur.execute("select tipo, estado, venta_id, detalle from solicitudes_gestion where conversacion_id = %s", (conversacion["id"],))
                assert cur.fetchall() == [("pedido_cerrado", "pendiente", venta["id"], "2 x Zapatos · total $60.00")]

    def test_stock_insuficiente_no_toca_nada(self):
        producto = _producto(stock=1)
        lead, conversacion = _lead_listo(producto, cantidad=2)

        with pytest.raises(StockInsuficienteError) as error:
            _cerrar(producto, lead, conversacion)

        assert error.value.disponible == 1
        assert _stock(producto["sku"]) == 1
        assert VentasRepository.obtener_por_lead(lead["id"]) is None
        assert LeadRepository.obtener_por_id(lead["id"])["estado"] != "por_gestionar"
        assert _estado_conversacion(conversacion["id"]) != "en_gestion"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from solicitudes_gestion where conversacion_id = %s", (conversacion["id"],))
                assert cur.fetchone()[0] == 0

    def test_la_ultima_unidad_pausa_el_producto_como_agotado(self):
        producto = _producto(stock=2)
        lead, conversacion = _lead_listo(producto, cantidad=2)

        resultado = _cerrar(producto, lead, conversacion)

        assert resultado["stock_restante"] == 0 and resultado["pausado_por_agotado"] is True
        actual = ProductosRepo.obtener(producto["sku"])
        assert (actual["estado"], actual["activo"]) == ("agotado", False)

    def test_sin_control_de_stock_no_se_descuenta_nada(self):
        producto = _producto(controla=False)
        lead, conversacion = _lead_listo(producto, cantidad=2)

        resultado = _cerrar(producto, lead, conversacion)

        assert resultado["stock_restante"] is None
        assert _stock(producto["sku"]) is None
        assert ProductosRepo.obtener(producto["sku"])["estado"] == "activo"

    def test_no_se_cierra_dos_veces_el_mismo_lead(self):
        producto = _producto(stock=10)
        lead, conversacion = _lead_listo(producto, cantidad=1)
        _cerrar(producto, lead, conversacion)

        with pytest.raises(VentaYaRegistradaError):
            _cerrar(producto, lead, conversacion)

        assert _stock(producto["sku"]) == 9  # el segundo intento no descontó (se deshizo la transacción)

    def test_completa_la_solicitud_pendiente_que_ya_existia(self):
        from src.routes.gestion.repository import SolicitudGestionRepository

        producto = _producto(stock=5)
        lead, conversacion = _lead_listo(producto, cantidad=1)
        SolicitudGestionRepository.solicitar(conversacion["id"], lead["id"], "quiere_comprar", "dijo que lo quiere")

        resultado = _cerrar(producto, lead, conversacion)

        assert resultado["solicitud"].creada is False and resultado["solicitud"].tipo == "pedido_cerrado"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*), max(tipo) from solicitudes_gestion where conversacion_id = %s and estado = 'pendiente'", (conversacion["id"],))
                assert cur.fetchone() == (1, "pedido_cerrado")


class TestRegistrar:
    def test_registrar_es_idempotente_por_lead(self):
        producto = _producto(stock=5)
        lead, conversacion = _lead_listo(producto, cantidad=1)
        venta, lineas = armar_venta(lead, producto, conversacion, None, "despachada", Decimal("5.00"))

        primero = VentasRepository.registrar(venta, lineas)
        segundo = VentasRepository.registrar(venta, lineas)

        assert primero is not None and segundo is None
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from ventas_lineas where venta_id = %s", (primero,))
                assert cur.fetchone()[0] == 1
