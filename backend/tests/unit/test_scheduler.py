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
    def test_registra_los_cuatro_jobs_y_arranca(self, scheduler_falso):
        app_module.start_scheduler()

        instancia = scheduler_falso.return_value
        ids = {llamada.kwargs["id"] for llamada in instancia.add_job.call_args_list}
        assert ids == {"reconciliacion_pedidos", "stock_watcher", "sync_productos", "latido_db"}
        instancia.start.assert_called_once()

    def test_el_latido_corre_cada_6_horas_y_arranca_pronto(self, scheduler_falso):
        app_module.start_scheduler()

        instancia = scheduler_falso.return_value
        latido = next(c for c in instancia.add_job.call_args_list if c.kwargs["id"] == "latido_db")
        assert latido.kwargs["hours"] == 6
        # Primera corrida adelantada (no esperar 6 h tras cada despliegue).
        assert latido.kwargs["next_run_time"] is not None

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
        assert apagado["status"] == "ok"
        assert apagado["scheduler"] is False

        monkeypatch.setenv("ENABLE_SCHEDULER", "true")
        encendido = app_module.create_app().test_client().get("/health").get_json()
        assert encendido["status"] == "ok"
        assert encendido["scheduler"] is True

    def test_health_informa_del_ultimo_latido_sin_consultar_la_base(self):
        from src.jobs.latido.service import reiniciar_estado

        reiniciar_estado()
        with patch("src.jobs.latido.repository.get_connection") as conexion:
            salud = app_module.create_app().test_client().get("/health").get_json()

        assert salud["latido"] == {"ultimo_ok": None, "fallos_seguidos": 0}
        conexion.assert_not_called()  # /health nunca debe depender de la DB

    def test_el_job_de_latido_nunca_propaga_excepciones(self):
        with patch("src.app.LatidoService") as servicio:
            servicio.return_value.ejecutar.side_effect = RuntimeError("boom")
            app_module._job_latido()  # no debe lanzar

    @pytest.mark.parametrize("valor", ["false", "0", "", "no"])
    def test_valores_falsos_no_lo_arrancan(self, scheduler_falso, monkeypatch, valor):
        monkeypatch.setenv("ENABLE_SCHEDULER", valor)
        app_module.create_app()
        scheduler_falso.assert_not_called()
