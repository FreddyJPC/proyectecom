from datetime import datetime

import pytest

from src.jobs.latido.service import LatidoService, estado_latido, reiniciar_estado


class FakeLatidoRepository:
    def __init__(self, falla=False):
        self._falla = falla
        self.llamadas = 0

    def registrar_latido(self):
        self.llamadas += 1
        if self._falla:
            raise RuntimeError("la base no responde")
        return datetime(2026, 11, 5, 12, 0, 0), self.llamadas


@pytest.fixture(autouse=True)
def estado_limpio():
    reiniciar_estado()
    yield
    reiniciar_estado()


class TestEjecutar:
    def test_registra_el_latido_y_guarda_el_estado(self):
        repo = FakeLatidoRepository()

        assert LatidoService(repo).ejecutar() is True

        assert repo.llamadas == 1
        estado = estado_latido()
        assert estado["fallos_seguidos"] == 0
        assert datetime.fromisoformat(estado["ultimo_ok"]).tzinfo is not None

    def test_si_la_base_falla_no_lanza_y_cuenta_el_fallo(self):
        servicio = LatidoService(FakeLatidoRepository(falla=True))

        assert servicio.ejecutar() is False
        assert servicio.ejecutar() is False

        estado = estado_latido()
        assert estado["ultimo_ok"] is None
        assert estado["fallos_seguidos"] == 2

    def test_un_exito_despues_de_fallos_pone_el_contador_en_cero(self):
        LatidoService(FakeLatidoRepository(falla=True)).ejecutar()
        LatidoService(FakeLatidoRepository()).ejecutar()

        estado = estado_latido()
        assert estado["fallos_seguidos"] == 0
        assert estado["ultimo_ok"] is not None

    def test_antes_de_cualquier_latido_el_estado_esta_vacio(self):
        assert estado_latido() == {"ultimo_ok": None, "fallos_seguidos": 0}
