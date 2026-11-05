"""
Contra la base real (la de pruebas local): el SQL crudo y las restricciones de la
migración 015. Restaura la fila de ajustes y borra lo que crea, para no dejar
la base de pruebas distinta de como estaba.
"""
from decimal import Decimal

import psycopg2.errors
import pytest

from src.config.database import get_connection
from src.routes.ajustes.exceptions import AjustesInvalidosError
from src.routes.ajustes.repository import AjustesNegocioRepository as Repo

SKU = "TEST-FASE-C-AJUSTES"
VALIDOS = {
    "margen_minimo_pct": Decimal("30.00"), "margen_objetivo_pct": Decimal("40.00"), "envio_estimado": Decimal("6.50"),
    "otros_costos_fijos": Decimal("1.00"), "otros_costos_pct": Decimal("3.00"), "redondeo": "ninguno",
}


def _volver_a_los_valores_de_partida():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from ajustes_negocio")
            cur.execute("insert into ajustes_negocio (id) values (1)")
            cur.execute("delete from rocketfy_minimos_observados where sku = %s", (SKU,))
            cur.execute("delete from productos_bot where sku = %s", (SKU,))


@pytest.fixture(autouse=True)
def limpio():
    _volver_a_los_valores_de_partida()
    yield
    _volver_a_los_valores_de_partida()


class TestObtener:
    def test_la_fila_inicial_tiene_los_valores_de_partida_y_no_esta_confirmada(self):
        fila = Repo.obtener()
        assert (fila["margen_minimo_pct"], fila["margen_objetivo_pct"], fila["envio_estimado"]) == (
            Decimal("25.00"), Decimal("35.00"), Decimal("5.00"),
        )
        assert (fila["otros_costos_fijos"], fila["otros_costos_pct"], fila["redondeo"]) == (Decimal("0.00"), Decimal("0.00"), "terminado_99")
        assert fila["confirmado_en"] is None

    def test_si_la_fila_desaparece_se_vuelve_a_crear(self):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from ajustes_negocio")
        assert Repo.obtener()["envio_estimado"] == Decimal("5.00")


class TestGuardar:
    def test_guarda_los_seis_ajustes_y_marca_la_confirmacion_una_sola_vez(self):
        primera = Repo.guardar(VALIDOS, "ana@ejemplo.com")
        assert (primera["margen_minimo_pct"], primera["envio_estimado"], primera["redondeo"]) == (Decimal("30.00"), Decimal("6.50"), "ninguno")
        assert primera["actualizado_por"] == "ana@ejemplo.com" and primera["confirmado_en"] is not None

        segunda = Repo.guardar({**VALIDOS, "envio_estimado": Decimal("7.00")}, "bea@ejemplo.com")
        assert segunda["envio_estimado"] == Decimal("7.00") and segunda["actualizado_por"] == "bea@ejemplo.com"
        assert segunda["confirmado_en"] == primera["confirmado_en"]  # la fecha de confirmación no se mueve

    def test_rechaza_columnas_que_faltan_o_sobran(self):
        with pytest.raises(ValueError):
            Repo.guardar({"envio_estimado": Decimal("5.00")}, None)
        with pytest.raises(ValueError):
            Repo.guardar({**VALIDOS, "confirmado_en": "2020-01-01"}, None)

    def test_la_base_rechaza_un_objetivo_menor_que_el_minimo(self):
        with pytest.raises(AjustesInvalidosError):
            Repo.guardar({**VALIDOS, "margen_minimo_pct": Decimal("40.00"), "margen_objetivo_pct": Decimal("30.00")}, None)

    def test_la_base_rechaza_porcentajes_que_suman_cien(self):
        with pytest.raises(AjustesInvalidosError):
            Repo.guardar({**VALIDOS, "margen_objetivo_pct": Decimal("90.00"), "otros_costos_pct": Decimal("10.00")}, None)

    def test_la_base_rechaza_un_redondeo_desconocido(self):
        with pytest.raises(AjustesInvalidosError):
            Repo.guardar({**VALIDOS, "redondeo": "al_dolar"}, None)

    def test_solo_puede_existir_la_fila_numero_uno(self):
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("insert into ajustes_negocio (id) values (2)")


class TestMinimosConCosto:
    def _sembrar(self, costo="10.00"):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """insert into productos_bot (sku, nombre, descripcion, precio, tiempo_entrega, costo_rocketfy)
                       values (%s, 'Prueba', 'd', 24.99, '2 dias', %s)""",
                    (SKU, costo),
                )
                cur.execute(
                    "insert into rocketfy_minimos_observados (sku, cantidad, minimo, mensaje) values (%s, 1, 18.47, 'm')", (SKU,)
                )
                cur.execute(
                    "insert into rocketfy_minimos_observados (sku, cantidad, minimo, mensaje) values (%s, NULL, 30.00, 'sin cantidad')", (SKU,)
                )
                cur.execute(
                    "insert into rocketfy_minimos_observados (sku, cantidad, minimo, mensaje) values ('SKU-SIN-FICHA-XYZ', 1, 25.00, 'sin ficha')"
                )

    def test_trae_los_minimos_de_productos_con_costo_y_cantidad(self):
        self._sembrar()
        try:
            filas = [f for f in Repo.listar_minimos_con_costo() if f["sku"] == SKU]
            assert [(f["cantidad"], f["minimo"], f["costo_rocketfy"]) for f in filas] == [(1, Decimal("18.47"), Decimal("10.00"))]
        finally:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("delete from rocketfy_minimos_observados where sku = 'SKU-SIN-FICHA-XYZ'")

    def test_ignora_los_productos_sin_costo_guardado(self):
        self._sembrar(costo=None)
        try:
            assert [f for f in Repo.listar_minimos_con_costo() if f["sku"] == SKU] == []
        finally:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("delete from rocketfy_minimos_observados where sku = 'SKU-SIN-FICHA-XYZ'")
