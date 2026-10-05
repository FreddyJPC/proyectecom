from src.routes.incidencias.services import IncidenciasService


class FakeIncidenciasRepository:
    def __init__(self, eventos=None, alertas=None):
        self._eventos = eventos or []
        self._alertas = alertas or []

    def listar_eventos_webhook(self, solo_incidencias, limit, offset):
        filas = [e for e in self._eventos if not solo_incidencias or e["status_id"] in (7, 9)]
        return filas[offset : offset + limit]

    def contar_eventos_webhook(self, solo_incidencias):
        return len([e for e in self._eventos if not solo_incidencias or e["status_id"] in (7, 9)])

    def listar_alertas_stock(self, sku, limit, offset):
        filas = [a for a in self._alertas if sku is None or a["sku"] == sku]
        return filas[offset : offset + limit]

    def contar_alertas_stock(self, sku):
        return len([a for a in self._alertas if sku is None or a["sku"] == sku])


def _evento(status_id, id_rocketfy=1):
    return {"id": 1, "id_rocketfy": id_rocketfy, "status_id": status_id, "shopify_order_id": 100}


class TestListarEventos:
    def test_por_defecto_solo_trae_incidencias(self):
        repo = FakeIncidenciasRepository(eventos=[_evento(2), _evento(7), _evento(9)])
        resultado = IncidenciasService(repo=repo).listar_eventos()

        assert resultado["total"] == 2
        assert all(e["status_id"] in (7, 9) for e in resultado["items"])

    def test_con_todos_trae_todo_el_historial(self):
        repo = FakeIncidenciasRepository(eventos=[_evento(2), _evento(7)])
        resultado = IncidenciasService(repo=repo).listar_eventos(solo_incidencias=False)

        assert resultado["total"] == 2

    def test_pagina_respeta_page_size(self):
        repo = FakeIncidenciasRepository(eventos=[_evento(7), _evento(7), _evento(7)])
        resultado = IncidenciasService(repo=repo).listar_eventos(page=1, page_size=2)

        assert resultado["total"] == 3
        assert len(resultado["items"]) == 2


class TestListarAlertas:
    def test_filtra_por_sku(self):
        repo = FakeIncidenciasRepository(
            alertas=[
                {"id": 1, "sku": "SKU-1", "tipo": "stock_bajo"},
                {"id": 2, "sku": "SKU-2", "tipo": "cambio_precio"},
            ]
        )
        resultado = IncidenciasService(repo=repo).listar_alertas(sku="SKU-1")

        assert resultado["total"] == 1
        assert resultado["items"][0]["sku"] == "SKU-1"

    def test_sin_filtro_trae_todas(self):
        repo = FakeIncidenciasRepository(
            alertas=[
                {"id": 1, "sku": "SKU-1", "tipo": "stock_bajo"},
                {"id": 2, "sku": "SKU-2", "tipo": "cambio_precio"},
            ]
        )
        resultado = IncidenciasService(repo=repo).listar_alertas()

        assert resultado["total"] == 2
