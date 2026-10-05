from decimal import Decimal
from unittest.mock import MagicMock

from src.integrations.rocketfy import RocketfyRequestError
from src.jobs.stock_watcher.service import StockWatcherService


class FakeStockWatcherRepository:
    def __init__(self, activos=None, ultimos=None, lock_disponible=True):
        self._activos = activos or []
        self._ultimos = ultimos or {}
        self._lock_disponible = lock_disponible
        self.lock_adquirido = False
        self.lock_liberado = False
        self.snapshots_guardados = []
        self.alertas_guardadas = []

    def acquire_lock(self, job_name):
        if not self._lock_disponible:
            return False
        self.lock_adquirido = True
        return True

    def release_lock(self, job_name):
        self.lock_liberado = True

    def listar_activos(self):
        return self._activos

    def obtener_ultimo_snapshot(self, sku):
        return self._ultimos.get(sku)

    def guardar_snapshot(self, sku, stock, price):
        self.snapshots_guardados.append((sku, stock, price))

    def guardar_alerta(self, sku, tipo, detalle):
        self.alertas_guardadas.append((sku, tipo, detalle))


def _client(stock=10, price="5.00", sku="RLJ-DEP-001"):
    client = MagicMock()
    client.listar_productos.return_value = {"data": [{"sku": sku, "stock": stock, "price": price}]}
    return client


class TestLock:
    def test_sin_lock_no_consulta_a_rocketfy(self):
        client = MagicMock()
        repo = FakeStockWatcherRepository(
            activos=[{"sku": "RLJ-DEP-001", "umbral_stock_minimo": 5}], lock_disponible=False
        )
        StockWatcherService(client=client, repo=repo).ejecutar()

        client.listar_productos.assert_not_called()
        assert repo.lock_liberado is False


class TestRevisionBasica:
    def test_guarda_snapshot_de_cada_sku_activo(self):
        client = _client()
        repo = FakeStockWatcherRepository(activos=[{"sku": "RLJ-DEP-001", "umbral_stock_minimo": 5}])
        StockWatcherService(client=client, repo=repo).ejecutar()

        assert repo.snapshots_guardados == [("RLJ-DEP-001", 10, Decimal("5.00"))]
        assert repo.lock_liberado is True

    def test_sin_skus_activos_no_llama_a_rocketfy(self):
        client = MagicMock()
        repo = FakeStockWatcherRepository(activos=[])
        StockWatcherService(client=client, repo=repo).ejecutar()

        client.listar_productos.assert_not_called()
        assert repo.lock_liberado is True

    def test_sku_ya_no_esta_en_el_catalogo_no_rompe(self):
        client = MagicMock()
        client.listar_productos.return_value = {"data": []}
        repo = FakeStockWatcherRepository(activos=[{"sku": "DESCONTINUADO", "umbral_stock_minimo": 5}])

        StockWatcherService(client=client, repo=repo).ejecutar()  # no debe lanzar
        assert repo.snapshots_guardados == []

    def test_busca_coincidencia_exacta_no_la_primera_del_listado(self):
        client = MagicMock()
        client.listar_productos.return_value = {
            "data": [
                {"sku": "RLJ-DEP-001-VARIANTE", "stock": 999, "price": "1.00"},
                {"sku": "RLJ-DEP-001", "stock": 10, "price": "5.00"},
            ]
        }
        repo = FakeStockWatcherRepository(activos=[{"sku": "RLJ-DEP-001", "umbral_stock_minimo": 5}])
        StockWatcherService(client=client, repo=repo).ejecutar()

        assert repo.snapshots_guardados == [("RLJ-DEP-001", 10, Decimal("5.00"))]


class TestAlertas:
    def test_stock_igual_o_bajo_el_umbral_se_loguea(self, caplog):
        client = _client(stock=2)
        repo = FakeStockWatcherRepository(activos=[{"sku": "RLJ-DEP-001", "umbral_stock_minimo": 5}])
        with caplog.at_level("WARNING"):
            StockWatcherService(client=client, repo=repo).ejecutar()

        assert any("STOCK BAJO" in r.message for r in caplog.records)
        assert repo.alertas_guardadas == [("RLJ-DEP-001", "stock_bajo", {"stock": 2, "umbral": 5})]

    def test_stock_por_encima_del_umbral_no_alerta(self, caplog):
        client = _client(stock=50)
        repo = FakeStockWatcherRepository(activos=[{"sku": "RLJ-DEP-001", "umbral_stock_minimo": 5}])
        with caplog.at_level("WARNING"):
            StockWatcherService(client=client, repo=repo).ejecutar()

        assert not any("STOCK BAJO" in r.message for r in caplog.records)
        assert repo.alertas_guardadas == []

    def test_cambio_de_precio_respecto_al_ultimo_snapshot_se_loguea(self, caplog):
        client = _client(price="7.50")
        repo = FakeStockWatcherRepository(
            activos=[{"sku": "RLJ-DEP-001", "umbral_stock_minimo": 5}],
            ultimos={"RLJ-DEP-001": {"stock": 10, "price": Decimal("5.00"), "capturado_en": None}},
        )
        with caplog.at_level("WARNING"):
            StockWatcherService(client=client, repo=repo).ejecutar()

        assert any("CAMBIO DE PRECIO" in r.message for r in caplog.records)
        assert repo.alertas_guardadas == [
            ("RLJ-DEP-001", "cambio_precio", {"precioAnterior": "5.00", "precioActual": "7.50"})
        ]

    def test_mismo_precio_que_el_ultimo_snapshot_no_alerta(self, caplog):
        client = _client(price="5.00")
        repo = FakeStockWatcherRepository(
            activos=[{"sku": "RLJ-DEP-001", "umbral_stock_minimo": 5}],
            ultimos={"RLJ-DEP-001": {"stock": 10, "price": Decimal("5.00"), "capturado_en": None}},
        )
        with caplog.at_level("WARNING"):
            StockWatcherService(client=client, repo=repo).ejecutar()

        assert not any("CAMBIO DE PRECIO" in r.message for r in caplog.records)

    def test_sin_snapshot_previo_no_intenta_comparar_precio(self, caplog):
        client = _client(price="5.00")
        repo = FakeStockWatcherRepository(activos=[{"sku": "RLJ-DEP-001", "umbral_stock_minimo": 5}])
        with caplog.at_level("WARNING"):
            StockWatcherService(client=client, repo=repo).ejecutar()  # no debe lanzar

        assert not any("CAMBIO DE PRECIO" in r.message for r in caplog.records)


class TestFalloEnUnSkuNoDetieneLosDemas:
    def test_continua_tras_error_de_red_en_uno(self):
        client = MagicMock()
        client.listar_productos.side_effect = [
            RocketfyRequestError("timeout"),
            {"data": [{"sku": "SKU-2", "stock": 10, "price": "1.00"}]},
        ]
        repo = FakeStockWatcherRepository(
            activos=[
                {"sku": "SKU-1", "umbral_stock_minimo": 5},
                {"sku": "SKU-2", "umbral_stock_minimo": 5},
            ]
        )
        StockWatcherService(client=client, repo=repo).ejecutar()

        assert repo.snapshots_guardados == [("SKU-2", 10, Decimal("1.00"))]
        assert repo.lock_liberado is True
