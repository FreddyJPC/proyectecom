"""
Contra la base real (la de pruebas local): SQL crudo que solo se prueba con
Postgres detrás, incluidas las restricciones de la migración 014. Autocontenido
(SKUs de prueba propios, limpieza en finally) para no ensuciar datos reales.
"""
from decimal import Decimal

import psycopg2.errors
import pytest

from src.config.database import get_connection
from src.routes.productos_bot.exceptions import ProductoBotYaExisteError
from src.routes.productos_bot.repository import COLUMNAS_EDITABLES, ProductoBotGestionRepository as Repo
from src.routes.whatsapp.repository import ProductoBotRepository

SKU = "TEST-FASE-B-GESTION"
SKU_LEGADO = "TEST-FASE-B-LEGADO"
DATOS_ROCKETFY = {
    "rocketfy_product_id": 4821,
    "costo_rocketfy": Decimal("10.00"),
    "precio_sugerido_rocketfy": Decimal("29.90"),
    "stock_ultimo": 12,
    "peso_kg": Decimal("0.350"),
    "imagen_url": "https://img/1.png",
}


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from productos_bot where sku in (%s, %s)", (SKU, SKU_LEGADO))
            cur.execute("delete from productos_bot_historial where sku in (%s, %s)", (SKU, SKU_LEGADO))


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def _crear():
    return Repo.crear_borrador(SKU, "Producto de prueba", "Descripción", Decimal("29.90"), "contraentrega", DATOS_ROCKETFY)


class TestCrearBorrador:
    def test_nace_como_borrador_inactivo_y_con_los_datos_de_rocketfy(self):
        fila = _crear()

        assert (fila["estado"], fila["activo"]) == ("borrador", False)
        assert fila["tiempo_entrega"] == ""
        assert fila["max_unidades_por_pedido"] == 1
        assert fila["costo_rocketfy"] == Decimal("10.00")
        assert fila["peso_kg"] == Decimal("0.350")
        assert fila["stock_actualizado_en"] is not None
        assert fila["publicado_en"] is None

    def test_un_borrador_no_lo_ve_victoria(self):
        _crear()
        assert SKU not in [p["sku"] for p in ProductoBotRepository.listar_activos()]

    def test_sku_repetido_lanza_un_error_claro(self):
        _crear()
        with pytest.raises(ProductoBotYaExisteError):
            _crear()


class TestCoherenciaEstadoActivo:
    def test_la_base_rechaza_un_activo_con_estado_que_no_es_activo(self):
        _crear()
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("update productos_bot set activo = true where sku = %s", (SKU,))

    def test_la_base_rechaza_estado_activo_con_activo_falso(self):
        _crear()
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("update productos_bot set estado = 'activo' where sku = %s", (SKU,))

    def test_la_base_rechaza_un_estado_desconocido(self):
        _crear()
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("update productos_bot set estado = 'volando', activo = false where sku = %s", (SKU,))

    def test_el_camino_antiguo_del_script_sigue_creando_productos_activos(self):
        """tools/cargar_producto_bot.py inserta sin `estado`: debe seguir siendo un producto activo."""
        creado = ProductoBotRepository.crear(
            sku=SKU_LEGADO, nombre="Legado", descripcion="d", precio=Decimal("12.00"), tiempo_entrega="2 días"
        )
        assert (creado["activo"], creado["max_unidades_por_pedido"]) == (True, 1)
        fila = Repo.obtener(SKU_LEGADO)
        assert (fila["estado"], fila["activo"]) == ("activo", True)
        assert SKU_LEGADO in [p["sku"] for p in ProductoBotRepository.listar_activos()]


class TestCambiarEstado:
    def test_activar_escribe_estado_activo_y_quien_publico(self):
        _crear()
        fila = Repo.cambiar_estado(SKU, "activo", "ana@ejemplo.com")

        assert (fila["estado"], fila["activo"]) == ("activo", True)
        assert fila["publicado_por"] == "ana@ejemplo.com" and fila["publicado_en"] is not None
        assert SKU in [p["sku"] for p in ProductoBotRepository.listar_activos()]

    def test_pausar_lo_saca_de_lo_que_ve_victoria_y_conserva_quien_publico(self):
        _crear()
        Repo.cambiar_estado(SKU, "activo", "ana@ejemplo.com")
        fila = Repo.cambiar_estado(SKU, "pausado", "bea@ejemplo.com")

        assert (fila["estado"], fila["activo"]) == ("pausado", False)
        assert fila["publicado_por"] == "ana@ejemplo.com"  # pausar no reescribe quién publicó
        assert SKU not in [p["sku"] for p in ProductoBotRepository.listar_activos()]

    @pytest.mark.parametrize("estado", ["borrador", "listo", "pausado", "agotado", "archivado"])
    def test_cualquier_estado_no_activo_deja_activo_en_falso(self, estado):
        _crear()
        Repo.cambiar_estado(SKU, "activo", None)
        fila = Repo.cambiar_estado(SKU, estado, None)
        assert (fila["estado"], fila["activo"]) == (estado, False)


class TestActualizarCampos:
    def test_actualiza_solo_los_campos_pedidos(self):
        _crear()
        fila = Repo.actualizar_campos(SKU, {"precio": Decimal("27.50"), "tiempo_entrega": "3 días", "variantes": None})

        assert fila["precio"] == Decimal("27.50") and fila["tiempo_entrega"] == "3 días"
        assert fila["nombre"] == "Producto de prueba"

    def test_el_precio_de_la_competencia_se_guarda_y_se_puede_borrar(self):
        _crear()
        assert Repo.obtener(SKU)["precio_competencia"] is None

        fila = Repo.actualizar_campos(SKU, {"precio_competencia": Decimal("22.50")})
        assert fila["precio_competencia"] == Decimal("22.50")
        assert Repo.actualizar_campos(SKU, {"precio_competencia": None})["precio_competencia"] is None
        assert "precio_competencia" in COLUMNAS_EDITABLES

    def test_rechaza_columnas_que_no_son_editables(self):
        _crear()
        for columna in ("estado", "activo", "sku", "costo_rocketfy", "publicado_por", "precio; drop table productos_bot"):
            with pytest.raises(ValueError):
                Repo.actualizar_campos(SKU, {columna: "x"})
        assert "estado" not in COLUMNAS_EDITABLES

    def test_sin_campos_devuelve_el_producto_tal_cual(self):
        _crear()
        assert Repo.actualizar_campos(SKU, {})["sku"] == SKU

    def test_sku_inexistente_devuelve_none(self):
        assert Repo.actualizar_campos("NO-EXISTE-XYZ", {"nombre": "x"}) is None


class TestDatosRocketfyYListado:
    def test_guardar_datos_de_rocketfy_no_toca_los_campos_de_ventas(self):
        _crear()
        Repo.actualizar_campos(SKU, {"precio": Decimal("33.00")})
        nuevos = dict(DATOS_ROCKETFY, costo_rocketfy=Decimal("12.00"), stock_ultimo=3)

        fila = Repo.guardar_datos_rocketfy(SKU, nuevos)

        assert fila["costo_rocketfy"] == Decimal("12.00") and fila["stock_ultimo"] == 3
        assert fila["precio"] == Decimal("33.00")

    def test_el_listado_oculta_archivados_salvo_que_se_pidan(self):
        _crear()
        Repo.cambiar_estado(SKU, "archivado", None)

        assert SKU not in [p["sku"] for p in Repo.listar()]
        assert SKU in [p["sku"] for p in Repo.listar(incluir_archivados=True)]


class TestHistorial:
    def test_guarda_y_devuelve_lo_mas_reciente_primero(self):
        Repo.registrar_historial(SKU, "creado", "ana@ejemplo.com", {"desde": "rocketfy"})
        Repo.registrar_historial(SKU, "editado", "bea@ejemplo.com", {"precio": ["24.99", Decimal("27.50")]})
        Repo.registrar_historial(SKU, "pausado", None)

        historial = Repo.listar_historial(SKU)

        assert [h["accion"] for h in historial] == ["pausado", "editado", "creado"]
        assert historial[1]["cambios"] == {"precio": ["24.99", "27.50"]}  # el Decimal viaja como texto
        assert historial[2]["usuario"] == "ana@ejemplo.com"
        assert historial[0]["cambios"] is None

    def test_el_limite_se_respeta(self):
        for i in range(5):
            Repo.registrar_historial(SKU, "editado", None, {"n": i})
        assert len(Repo.listar_historial(SKU, limite=3)) == 3


class TestUltimaFechaDe:
    def test_sin_registros_es_none(self):
        _crear()
        assert Repo.ultima_fecha_de(SKU, "simulacion_completa") is None

    def test_devuelve_la_mas_reciente_de_esa_accion_y_no_mezcla_acciones_ni_productos(self):
        _crear()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into productos_bot_historial (sku, accion, creado_en) values
                      (%s, 'simulacion_completa', '2026-11-01 10:00+00'),
                      (%s, 'simulacion_completa', '2026-11-03 10:00+00'),
                      (%s, 'editado',             '2026-11-04 10:00+00'),
                      (%s, 'simulacion_completa', '2026-11-09 10:00+00')
                    """,
                    (SKU, SKU, SKU, SKU_LEGADO),
                )
        ultima = Repo.ultima_fecha_de(SKU, "simulacion_completa")
        assert (ultima.year, ultima.month, ultima.day) == (2026, 11, 3)
        assert Repo.ultima_fecha_de(SKU, "editado").day == 4

    def test_no_se_limita_a_las_ultimas_20_entradas_del_historial(self):
        _crear()
        Repo.registrar_historial(SKU, "simulacion_completa", None)
        for _ in range(25):
            Repo.registrar_historial(SKU, "editado", None, {})
        assert Repo.ultima_fecha_de(SKU, "simulacion_completa") is not None
        assert all(h["accion"] != "simulacion_completa" for h in Repo.listar_historial(SKU))  # el historial sí la «olvida»


class TestPausarPorAgotado:
    def _activar(self):
        _crear()
        Repo.cambiar_estado(SKU, "activo", "ana@ejemplo.com")

    def test_un_activo_pasa_a_agotado_y_activo_queda_en_falso(self):
        self._activar()
        fila = Repo.pausar_por_agotado(SKU)
        assert (fila["estado"], fila["activo"]) == ("agotado", False)
        assert Repo.obtener(SKU)["estado"] == "agotado"

    @pytest.mark.parametrize("estado", ["borrador", "listo", "pausado", "archivado", "agotado"])
    def test_si_no_esta_activo_no_toca_nada(self, estado):
        _crear()
        Repo.cambiar_estado(SKU, estado, None)
        assert Repo.pausar_por_agotado(SKU) is None
        assert Repo.obtener(SKU)["estado"] == estado

    def test_un_sku_que_no_existe_devuelve_none(self):
        assert Repo.pausar_por_agotado("NO-EXISTE-FASE-F") is None

    def test_no_cambia_publicado_en_ni_publicado_por(self):
        self._activar()
        antes = Repo.obtener(SKU)
        despues = Repo.pausar_por_agotado(SKU)
        assert (despues["publicado_en"], despues["publicado_por"]) == (antes["publicado_en"], antes["publicado_por"])


class TestContarPedidosPorSku:
    SKUS = ("TEST-F-PED-A", "TEST-F-PED-B")
    IDS = (990001, 990002, 990003, 990004, 990005, 990006, 990007)

    @pytest.fixture(autouse=True)
    def limpio_pedidos(self):
        self._borrar()
        yield
        self._borrar()

    def _borrar(self):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from pedidos where id_local = any(%s)", (list(self.IDS),))

    def _pedido(self, id_local, estado, lineas, hace="1 day", payload=None):
        from psycopg2.extras import Json

        cuerpo = payload if payload is not None else {"nombre_cliente": "x", "lineas": lineas}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into pedidos (id_local, estado_local, payload_creacion, creado_en) "
                    "values (%s, %s, %s, now() - %s::interval)",
                    (id_local, estado, Json(cuerpo), hace),
                )

    def _contar(self):
        todos = Repo.contar_pedidos_por_sku(30)
        return {sku: todos.get(sku, 0) for sku in self.SKUS}

    def test_cuenta_pedidos_creados_y_confirmados_por_sku(self):
        a, b = self.SKUS
        self._pedido(990001, "confirmado", [{"sku": a, "nombre": "A", "cantidad": 1}])
        self._pedido(990002, "creado", [{"sku": a, "nombre": "A", "cantidad": 2}, {"sku": b, "nombre": "B", "cantidad": 1}])
        assert self._contar() == {a: 2, b: 1}

    def test_no_cuentan_los_que_fallaron_ni_los_rechazados_ni_los_pendientes(self):
        a, _ = self.SKUS
        for i, estado in enumerate(["error", "rechazado", "pendiente_creacion", "incompleto"]):
            self._pedido(990001 + i, estado, [{"sku": a, "nombre": "A", "cantidad": 1}])
        assert self._contar()[a] == 0

    def test_solo_los_ultimos_30_dias(self):
        a, _ = self.SKUS
        self._pedido(990001, "confirmado", [{"sku": a}], hace="29 days")
        self._pedido(990002, "confirmado", [{"sku": a}], hace="31 days")
        assert self._contar()[a] == 1

    def test_el_sku_se_compara_sin_distinguir_mayusculas(self):
        a, _ = self.SKUS
        self._pedido(990001, "confirmado", [{"sku": a.lower()}])
        assert self._contar()[a] == 1  # la clave sale en mayúsculas

    def test_un_pedido_con_dos_lineas_del_mismo_sku_cuenta_una_vez(self):
        a, _ = self.SKUS
        self._pedido(990001, "confirmado", [{"sku": a, "cantidad": 1}, {"sku": a, "cantidad": 2}])
        assert self._contar()[a] == 1

    @pytest.mark.parametrize("payload", [None, {}, {"lineas": None}, {"lineas": "texto"}, {"lineas": [{"nombre": "sin sku"}]}, {"lineas": []}])
    def test_un_payload_raro_no_rompe_ni_cuenta(self, payload):
        self._pedido(990001, "confirmado", None, payload=payload if payload is not None else {})
        assert self._contar() == {self.SKUS[0]: 0, self.SKUS[1]: 0}
