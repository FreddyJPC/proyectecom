"""
Único punto de la suite que habla con la Supabase real: el repositorio es
SQL crudo con psycopg2, no hay forma útil de probarlo sin una base real
detrás. Se mantiene autocontenido (SKU e id_anuncio de prueba propios,
limpieza en finally) para no ensuciar productos_bot ni chocar con datos
reales del negocio.
"""
from decimal import Decimal

from src.config.database import get_connection
from src.routes.whatsapp.repository import ProductoBotRepository

_SKU_PRUEBA = "TEST-FASE32-PRODUCTO-BOT"
_ID_ANUNCIO_PRUEBA = "TEST-FASE32-ANUNCIO"


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from anuncios_productos where id_anuncio = %s", (_ID_ANUNCIO_PRUEBA,))
            cur.execute("delete from productos_bot where sku = %s", (_SKU_PRUEBA,))


class TestProductoBotRepository:
    def test_obtiene_por_sku_y_por_id_anuncio(self):
        _limpiar()
        try:
            creado = ProductoBotRepository.crear(
                sku=_SKU_PRUEBA,
                nombre="Producto de prueba Fase 3.2",
                descripcion="Solo para pytest -- se borra al terminar el test.",
                precio=Decimal("19.99"),
                tiempo_entrega="2 a 4 días hábiles",
            )
            assert creado["sku"] == _SKU_PRUEBA
            assert creado["precio"] == Decimal("19.99")

            por_sku = ProductoBotRepository.obtener_por_sku(_SKU_PRUEBA)
            assert por_sku is not None
            assert por_sku["nombre"] == "Producto de prueba Fase 3.2"

            assert ProductoBotRepository.obtener_por_sku("NO-EXISTE-XYZ") is None
            assert ProductoBotRepository.obtener_por_id_anuncio("NO-EXISTE-XYZ") is None

            ProductoBotRepository.vincular_anuncio(id_anuncio=_ID_ANUNCIO_PRUEBA, producto_sku=_SKU_PRUEBA)
            por_anuncio = ProductoBotRepository.obtener_por_id_anuncio(_ID_ANUNCIO_PRUEBA)
            assert por_anuncio is not None
            assert por_anuncio["sku"] == _SKU_PRUEBA

            actualizado = ProductoBotRepository.actualizar(
                sku=_SKU_PRUEBA,
                nombre="Producto de prueba Fase 3.2 (actualizado)",
                descripcion="Descripción actualizada.",
                precio=Decimal("29.99"),
                tiempo_entrega="1 a 3 días hábiles",
            )
            assert actualizado["nombre"] == "Producto de prueba Fase 3.2 (actualizado)"
            assert actualizado["precio"] == Decimal("29.99")

            activos = ProductoBotRepository.listar_activos()
            assert any(p["sku"] == _SKU_PRUEBA for p in activos)
        finally:
            _limpiar()
