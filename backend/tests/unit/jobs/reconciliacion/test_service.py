from unittest.mock import MagicMock

from src.integrations.rocketfy import RocketfyRequestError
from src.jobs.reconciliacion.service import ReconciliacionService


class FakeReconciliacionRepository:
    def __init__(self, ids_en_curso=None, lock_disponible=True):
        self._ids = ids_en_curso or []
        self._lock_disponible = lock_disponible
        self.lock_adquirido = False
        self.lock_liberado = False
        self.actualizaciones = []

    def acquire_lock(self, job_name, timeout_minutos=30):
        if not self._lock_disponible:
            return False
        self.lock_adquirido = True
        return True

    def release_lock(self, job_name):
        self.lock_liberado = True

    def obtener_ids_en_curso(self):
        return self._ids

    def actualizar_status(self, id_rocketfy, status_id):
        self.actualizaciones.append((id_rocketfy, status_id))


class TestLock:
    def test_sin_lock_disponible_no_consulta_rocketfy_ni_libera_nada(self):
        client = MagicMock()
        repo = FakeReconciliacionRepository(lock_disponible=False)
        ReconciliacionService(client=client, repo=repo).ejecutar()

        client.consultar_pedidos_lote.assert_not_called()
        assert repo.lock_liberado is False

    def test_lock_se_libera_incluso_si_algo_falla(self):
        client = MagicMock()
        client.consultar_pedidos_lote.side_effect = RuntimeError("boom inesperado")
        repo = FakeReconciliacionRepository(ids_en_curso=[1, 2])

        try:
            ReconciliacionService(client=client, repo=repo).ejecutar()
        except RuntimeError:
            pass

        assert repo.lock_liberado is True


class TestSinPedidosEnCurso:
    def test_no_llama_a_rocketfy_pero_libera_el_lock(self):
        client = MagicMock()
        repo = FakeReconciliacionRepository(ids_en_curso=[])
        ReconciliacionService(client=client, repo=repo).ejecutar()

        assert repo.lock_adquirido is True
        assert repo.lock_liberado is True
        client.consultar_pedidos_lote.assert_not_called()


class TestActualizacion:
    def test_actualiza_cada_pedido_devuelto_por_el_lote(self):
        client = MagicMock()
        client.consultar_pedidos_lote.return_value = {
            "orders": [{"id": 100, "status_id": 8}, {"id": 101, "status_id": 6}]
        }
        repo = FakeReconciliacionRepository(ids_en_curso=[100, 101])
        ReconciliacionService(client=client, repo=repo).ejecutar()

        client.consultar_pedidos_lote.assert_called_once_with(100, 101)
        assert (100, 8) in repo.actualizaciones
        assert (101, 6) in repo.actualizaciones

    def test_soporta_forma_de_respuesta_como_lista_plana(self):
        client = MagicMock()
        client.consultar_pedidos_lote.return_value = [{"id": 100, "status_id": 8}]
        repo = FakeReconciliacionRepository(ids_en_curso=[100])
        ReconciliacionService(client=client, repo=repo).ejecutar()

        assert (100, 8) in repo.actualizaciones

    def test_forma_de_respuesta_desconocida_no_rompe_y_no_actualiza(self):
        client = MagicMock()
        client.consultar_pedidos_lote.return_value = {"algo_inesperado": True}
        repo = FakeReconciliacionRepository(ids_en_curso=[100])
        ReconciliacionService(client=client, repo=repo).ejecutar()

        assert repo.actualizaciones == []
        assert repo.lock_liberado is True


class TestParticionDeRangos:
    def test_particiona_por_rango_no_por_cantidad_de_ids(self):
        client = MagicMock()
        client.consultar_pedidos_lote.return_value = {"orders": []}
        repo = FakeReconciliacionRepository(ids_en_curso=[1, 500_000])  # solo 2 ids, rango enorme

        ReconciliacionService(client=client, repo=repo, tamano_maximo_rango=1000).ejecutar()

        assert client.consultar_pedidos_lote.call_count == 500
        primera = client.consultar_pedidos_lote.call_args_list[0].args
        ultima = client.consultar_pedidos_lote.call_args_list[-1].args
        assert primera == (1, 1000)
        assert ultima == (499001, 500000)

    def test_rango_pequeno_es_un_solo_lote(self):
        client = MagicMock()
        client.consultar_pedidos_lote.return_value = {"orders": []}
        repo = FakeReconciliacionRepository(ids_en_curso=[10, 20, 30])
        ReconciliacionService(client=client, repo=repo).ejecutar()

        client.consultar_pedidos_lote.assert_called_once_with(10, 30)


class TestResilenciaAErroresDeRed:
    def test_fallo_en_un_lote_continua_con_los_demas(self):
        client = MagicMock()
        # ids_en_curso=[100, 160] con tamano_maximo_rango=50 -> 2 lotes: 100-149, 150-160
        client.consultar_pedidos_lote.side_effect = [
            RocketfyRequestError("timeout en el primer lote"),
            {"orders": [{"id": 155, "status_id": 8}]},
        ]
        repo = FakeReconciliacionRepository(ids_en_curso=[100, 160])
        ReconciliacionService(client=client, repo=repo, tamano_maximo_rango=50).ejecutar()

        assert client.consultar_pedidos_lote.call_count == 2
        assert (155, 8) in repo.actualizaciones
        assert repo.lock_liberado is True
