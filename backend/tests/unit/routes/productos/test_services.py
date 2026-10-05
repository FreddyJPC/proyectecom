from unittest.mock import MagicMock

import pytest

from src.routes.productos.dto import SkuMonitoreadoInputDTO
from src.routes.productos.exceptions import SkuNoExisteEnRocketfyError
from src.routes.productos.services import ProductosService


class FakeSkuMonitoreadoRepository:
    def __init__(self):
        self.filas = {}

    def upsert(self, sku, umbral_stock_minimo):
        self.filas[sku] = {
            "sku": sku, "umbral_stock_minimo": umbral_stock_minimo, "activo": True,
            "stock": None, "price": None, "capturado_en": None,
        }

    def desactivar(self, sku):
        if sku not in self.filas:
            return False
        self.filas[sku]["activo"] = False
        return True

    def listar(self, solo_activos=False):
        valores = list(self.filas.values())
        if solo_activos:
            valores = [f for f in valores if f["activo"]]
        return valores


def _client_con_catalogo(*skus):
    client = MagicMock()
    client.listar_productos.return_value = {
        "data": [{"sku": s, "stock": 10, "price": "5.00"} for s in skus]
    }
    return client


class TestAgregarSkuMonitoreado:
    def test_sku_existente_en_rocketfy_se_agrega(self):
        client = _client_con_catalogo("RLJ-DEP-001")
        repo = FakeSkuMonitoreadoRepository()
        ProductosService(client=client, repo=repo).agregar_sku_monitoreado(
            SkuMonitoreadoInputDTO(sku="RLJ-DEP-001", umbral_stock_minimo=5)
        )
        assert "RLJ-DEP-001" in repo.filas
        assert repo.filas["RLJ-DEP-001"]["umbral_stock_minimo"] == 5

    def test_sku_inexistente_no_se_agrega(self):
        client = _client_con_catalogo("OTRO-SKU")
        repo = FakeSkuMonitoreadoRepository()
        with pytest.raises(SkuNoExisteEnRocketfyError):
            ProductosService(client=client, repo=repo).agregar_sku_monitoreado(
                SkuMonitoreadoInputDTO(sku="SKU-INEXISTENTE")
            )
        assert repo.filas == {}

    def test_comparacion_ignora_mayusculas(self):
        client = _client_con_catalogo("rlj-dep-001")
        repo = FakeSkuMonitoreadoRepository()
        ProductosService(client=client, repo=repo).agregar_sku_monitoreado(
            SkuMonitoreadoInputDTO(sku="RLJ-DEP-001")
        )
        assert "RLJ-DEP-001" in repo.filas


class TestQuitarSkuMonitoreado:
    def test_desactiva_uno_existente(self):
        repo = FakeSkuMonitoreadoRepository()
        repo.upsert("RLJ-DEP-001", 5)
        assert ProductosService(client=MagicMock(), repo=repo).quitar_sku_monitoreado("RLJ-DEP-001") is True
        assert repo.filas["RLJ-DEP-001"]["activo"] is False

    def test_quitar_uno_inexistente_devuelve_false(self):
        repo = FakeSkuMonitoreadoRepository()
        assert ProductosService(client=MagicMock(), repo=repo).quitar_sku_monitoreado("NO-EXISTE") is False


class TestListarMonitoreados:
    def test_devuelve_dto_con_ultimo_snapshot_nulo_si_no_hay(self):
        repo = FakeSkuMonitoreadoRepository()
        repo.upsert("RLJ-DEP-001", 5)
        resultado = ProductosService(client=MagicMock(), repo=repo).listar_monitoreados()
        assert len(resultado) == 1
        assert resultado[0].sku == "RLJ-DEP-001"
        assert resultado[0].ultimo_stock is None
