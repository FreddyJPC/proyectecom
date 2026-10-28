"""
Arranque de los jobs de fondo (reconciliación + stock watcher).

Contexto: en producción el servidor es gunicorn, que importa `app` y nunca
ejecuta el bloque `if __name__ == "__main__"` de src/app.py. Por eso
create_app() enciende el scheduler cuando ENABLE_SCHEDULER=true. Estos tests
usan un BackgroundScheduler falso: no arrancan hilos ni esperan 45 minutos.
"""
from unittest.mock import MagicMock, patch

import pytest

import src.app as app_module


@pytest.fixture(autouse=True)
def scheduler_limpio(monkeypatch):
    """Cada test parte sin scheduler (el módulo guarda uno por proceso)."""
    monkeypatch.setattr(app_module, "_scheduler", None)
    monkeypatch.delenv("ENABLE_SCHEDULER", raising=False)


@pytest.fixture
def scheduler_falso():
    with patch("apscheduler.schedulers.background.BackgroundScheduler") as clase:
        yield clase


class TestStartScheduler:
    def test_registra_los_dos_jobs_y_arranca(self, scheduler_falso):
        app_module.start_scheduler()

        instancia = scheduler_falso.return_value
        ids = {llamada.kwargs["id"] for llamada in instancia.add_job.call_args_list}
        assert ids == {"reconciliacion_pedidos", "stock_watcher"}
        instancia.start.assert_called_once()

    def test_es_idempotente_no_crea_dos_schedulers(self, scheduler_falso):
        primero = app_module.start_scheduler()
        segundo = app_module.start_scheduler()

        assert primero is segundo
        scheduler_falso.assert_called_once()
        scheduler_falso.return_value.start.assert_called_once()


class TestCreateAppYScheduler:
    def test_por_defecto_no_arranca_el_scheduler(self, scheduler_falso):
        app_module.create_app()
        scheduler_falso.assert_not_called()

    def test_con_enable_scheduler_true_lo_arranca_una_sola_vez(self, scheduler_falso, monkeypatch):
        monkeypatch.setenv("ENABLE_SCHEDULER", "true")

        app_module.create_app()
        app_module.create_app()  # el factory puede ejecutarse dos veces por proceso

        scheduler_falso.return_value.start.assert_called_once()

    def test_health_informa_si_el_scheduler_esta_encendido(self, scheduler_falso, monkeypatch):
        apagado = app_module.create_app().test_client().get("/health").get_json()
        assert apagado == {"status": "ok", "scheduler": False}

        monkeypatch.setenv("ENABLE_SCHEDULER", "true")
        encendido = app_module.create_app().test_client().get("/health").get_json()
        assert encendido == {"status": "ok", "scheduler": True}

    @pytest.mark.parametrize("valor", ["false", "0", "", "no"])
    def test_valores_falsos_no_lo_arrancan(self, scheduler_falso, monkeypatch, valor):
        monkeypatch.setenv("ENABLE_SCHEDULER", valor)
        app_module.create_app()
        scheduler_falso.assert_not_called()
