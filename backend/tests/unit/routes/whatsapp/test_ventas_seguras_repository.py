"""
Habla con la base real (la de pruebas local), igual que
test_productos_bot_repository.py: SQL crudo que solo se prueba contra
Postgres. Se mantiene autocontenido (teléfono, SKU y mensajes de prueba
propios, limpieza en finally) para no ensuciar datos reales.
"""
from decimal import Decimal

from src.config.database import get_connection
from src.routes.whatsapp.repository import (
    ConversacionRepository,
    LeadRepository,
    MinimoObservadoRepository,
    ProductoBotRepository,
)
from tests.helpers_db import borrar_conversaciones_de_prueba

_TELEFONO = "593900000777"
_SKU_PRODUCTO = "TEST-FASE-A-PRODUCTO"
_SKU_MINIMO = "TEST-FASE-A-MINIMO"


def _limpiar():
    borrar_conversaciones_de_prueba(_TELEFONO)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from productos_bot where sku = %s", (_SKU_PRODUCTO,))
            cur.execute("delete from rocketfy_minimos_observados where sku = %s", (_SKU_MINIMO,))


class TestCantidadEnElLead:
    def test_un_lead_nuevo_arranca_con_una_unidad_y_se_actualiza_con_el_producto(self):
        _limpiar()
        try:
            conversacion = ConversacionRepository.crear(id_externo=_TELEFONO, origen="directo")
            lead = LeadRepository.obtener_o_crear(conversacion["id"], conversacion["contacto_id"], telefono=_TELEFONO)
            assert lead["cantidad"] == 1

            LeadRepository.actualizar_producto(
                lead["id"], producto_sku="X", producto_nombre="Producto X", total=Decimal("49.98"), variante="negro", cantidad=2
            )

            actualizado = LeadRepository.obtener_por_id(lead["id"])
            assert actualizado["cantidad"] == 2
            assert actualizado["total"] == Decimal("49.98")
            assert actualizado["producto_variante"] == "negro"
        finally:
            _limpiar()

    def test_llamar_sin_cantidad_deja_una_unidad(self):
        _limpiar()
        try:
            conversacion = ConversacionRepository.crear(id_externo=_TELEFONO, origen="directo")
            lead = LeadRepository.obtener_o_crear(conversacion["id"], conversacion["contacto_id"], telefono=_TELEFONO)

            LeadRepository.actualizar_producto(lead["id"], producto_sku="X", producto_nombre="Producto X", total=Decimal("24.99"))

            assert LeadRepository.obtener_por_id(lead["id"])["cantidad"] == 1
        finally:
            _limpiar()


class TestMaximoDeUnidadesDelProducto:
    def test_por_defecto_es_una_unidad_y_se_puede_cambiar(self):
        _limpiar()
        try:
            creado = ProductoBotRepository.crear(
                sku=_SKU_PRODUCTO, nombre="Producto de prueba", descripcion="Solo para pytest.", precio=Decimal("10.00"),
                tiempo_entrega="2 días",
            )
            assert creado["max_unidades_por_pedido"] == 1

            actualizado = ProductoBotRepository.actualizar(
                sku=_SKU_PRODUCTO, nombre="Producto de prueba", descripcion="Solo para pytest.", precio=Decimal("10.00"),
                tiempo_entrega="2 días", max_unidades_por_pedido=3,
            )
            assert actualizado["max_unidades_por_pedido"] == 3
            assert ProductoBotRepository.obtener_por_sku(_SKU_PRODUCTO)["max_unidades_por_pedido"] == 3
        finally:
            _limpiar()


class TestMinimoObservadoRepository:
    def test_guarda_el_minimo_con_su_destino(self):
        _limpiar()
        try:
            MinimoObservadoRepository.guardar(
                sku=_SKU_MINIMO, canton="QUITO", provincia="Pichincha", cantidad=1, minimo=Decimal("18.47"),
                mensaje="El importe mínimo del pedido debe ser ... ($18.47)",
            )

            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "select canton, provincia, cantidad, minimo from rocketfy_minimos_observados where sku = %s",
                        (_SKU_MINIMO,),
                    )
                    assert cur.fetchall() == [("QUITO", "Pichincha", 1, Decimal("18.47"))]
        finally:
            _limpiar()
