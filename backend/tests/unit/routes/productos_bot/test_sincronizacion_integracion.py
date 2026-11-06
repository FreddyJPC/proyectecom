"""
Sincronización de productos contra la base local con los repositorios REALES
(solo Rocketfy y Telegram son falsos): la pausa deja `estado` y `activo`
coherentes, la alerta queda en Incidencias (`alertas_stock`) y el historial
anota al «Sistema».
"""
from decimal import Decimal

import pytest

from src.config.database import get_connection
from src.routes.productos_bot.repository import ProductoBotGestionRepository as Repo
from src.routes.productos_bot.services import ProductosBotService
from src.routes.productos_bot.sincronizacion import SincronizacionProductosService
from tests.unit.routes.productos_bot.test_services import AjustesFalsos
from tests.unit.routes.productos_bot.test_sincronizacion import RocketfyPorSku, TelegramFalso, en_rocketfy

SKU = "TEST-F-SYNC-1"


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from alertas_stock where sku = %s", (SKU,))
            cur.execute("delete from skus_monitoreados where sku = %s", (SKU,))
            cur.execute("delete from productos_bot_historial where sku = %s", (SKU,))
            cur.execute("delete from productos_bot where sku = %s", (SKU,))


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def _producto_activo(costo="10.00", precio="34.90"):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into productos_bot (sku, nombre, descripcion, precio, tiempo_entrega, metodos_pago_aceptados,
                                           max_unidades_por_pedido, estado, activo, costo_rocketfy, stock_ultimo)
                values (%s, 'Reloj de prueba', 'Un reloj.', %s, '2 a 4 dias', 'contraentrega', 1, 'activo', true, %s, 50)
                """,
                (SKU, precio, costo),
            )


def _servicio(catalogo, telegram=None, confirmado=True):
    return SincronizacionProductosService(
        productos=ProductosBotService(client=catalogo, ajustes_service=AjustesFalsos(confirmado=confirmado)),
        ajustes_service=AjustesFalsos(confirmado=confirmado),
        telegram=telegram or TelegramFalso(),
    )


def _alertas():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select tipo, detalle from alertas_stock where sku = %s order by id", (SKU,))
            return cur.fetchall()


class TestContraLaBase:
    def test_un_activo_sin_stock_queda_agotado_con_alerta_historial_y_vigilado(self):
        _producto_activo()
        telegram = TelegramFalso()
        r = _servicio(RocketfyPorSku([en_rocketfy(SKU, stock=0)]), telegram).sincronizar_todos()

        fila = Repo.obtener(SKU)
        assert (fila["estado"], fila["activo"], fila["stock_ultimo"]) == ("agotado", False, 0)
        assert r.pausados_por_agotado == 1 and len(telegram.avisos) == 1
        assert _alertas() == [("producto_agotado", {"stock": 0})]
        historial = Repo.listar_historial(SKU)
        pausa = next(h for h in historial if h["accion"] == "agotado")
        assert pausa["usuario"] is None and pausa["cambios"]["estado"] == ["activo", "agotado"]
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from skus_monitoreados where sku = %s", (SKU,))
                assert cur.fetchone()[0] == 1  # se agregó a Vigilados para poder guardar la alerta

    def test_el_costo_que_sube_deja_la_alerta_de_margen_con_numeros_exactos(self):
        _producto_activo()
        _servicio(RocketfyPorSku([en_rocketfy(SKU, stock=20, costo="22.00")])).sincronizar_todos()

        fila = Repo.obtener(SKU)
        assert fila["costo_rocketfy"] == Decimal("22.00") and fila["estado"] == "activo" and fila["precio"] == Decimal("34.90")
        assert _alertas() == [(
            "margen_en_riesgo",
            {"costoAnterior": "10.00", "costoActual": "22.00", "precio": "34.90", "margenPct": "22.6", "margenMinimoPct": "25.00"},
        )]

    def test_la_pausa_condicional_respeta_al_que_pauso_a_mano(self):
        _producto_activo()
        Repo.cambiar_estado(SKU, "pausado", "ana@ejemplo.com")
        assert Repo.pausar_por_agotado(SKU) is None
        assert Repo.obtener(SKU)["estado"] == "pausado"
