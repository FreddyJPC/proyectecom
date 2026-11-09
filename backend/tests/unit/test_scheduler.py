"""
Arranque de los jobs de fondo (reconciliación, stock watcher, sincronización de productos y latido).

Contexto: en producción el servidor es gunicorn, que importa `app` y nunca
ejecuta el bloque `if __name__ == "__main__"` de src/app.py. Por eso
create_app() enciende el scheduler cuando ENABLE_SCHEDULER=true. Estos tests
usan un BackgroundScheduler falso: no arrancan hilos ni esperan 45 minutos.
"""
from unittest.mock import MagicMock, patch

import pytest

import src.app as app_module
from src.config.parametros import parametros


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
    def test_registra_los_cinco_jobs_y_arranca(self, scheduler_falso):
        app_module.start_scheduler()

        instancia = scheduler_falso.return_value
        ids = {llamada.kwargs["id"] for llamada in instancia.add_job.call_args_list}
        assert ids == {"reconciliacion_pedidos", "stock_watcher", "sync_productos", "enfriar_leads", "seguimiento", "latido_db"}
        instancia.start.assert_called_once()

    def test_sin_nada_guardado_los_intervalos_son_los_de_siempre(self, scheduler_falso):
        app_module.start_scheduler()

        minutos = {c.kwargs["id"]: c.kwargs.get("minutes") for c in scheduler_falso.return_value.add_job.call_args_list}
        assert minutos == {"reconciliacion_pedidos": 45, "stock_watcher": 60, "sync_productos": 60, "enfriar_leads": 60, "seguimiento": 30, "latido_db": None}

    def test_los_intervalos_se_leen_de_los_parametros_al_arrancar(self, scheduler_falso):
        try:
            parametros.guardar("jobs.minutos_reconciliacion", 20, "test@ejemplo.com")
            parametros.guardar("jobs.minutos_sync_productos", 120, "test@ejemplo.com")
            app_module.start_scheduler()
        finally:
            parametros.restaurar("jobs.minutos_reconciliacion", "test@ejemplo.com")
            parametros.restaurar("jobs.minutos_sync_productos", "test@ejemplo.com")

        minutos = {c.kwargs["id"]: c.kwargs.get("minutes") for c in scheduler_falso.return_value.add_job.call_args_list}
        assert (minutos["reconciliacion_pedidos"], minutos["stock_watcher"], minutos["sync_productos"]) == (20, 60, 120)

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


class TestReprogramarEnVivo:
    """Guardar un intervalo en Parámetros reprograma el reloj sin reiniciar el servidor."""

    def test_guardar_un_intervalo_reprograma_solo_esa_tarea(self, scheduler_falso):
        app_module.start_scheduler()
        instancia = scheduler_falso.return_value
        try:
            parametros.guardar("jobs.minutos_sync_productos", 30, "test@ejemplo.com")
            instancia.reschedule_job.assert_called_once_with("sync_productos", trigger="interval", minutes=30)

            instancia.reschedule_job.reset_mock()
            parametros.restaurar("jobs.minutos_sync_productos", "test@ejemplo.com")
            instancia.reschedule_job.assert_called_once_with("sync_productos", trigger="interval", minutes=60)
        finally:
            parametros.restaurar("jobs.minutos_sync_productos", "test@ejemplo.com")

    def test_cada_parametro_reprograma_su_propia_tarea(self, scheduler_falso):
        app_module.start_scheduler()
        instancia = scheduler_falso.return_value
        try:
            parametros.guardar("jobs.minutos_reconciliacion", 25, "test@ejemplo.com")
            parametros.guardar("jobs.minutos_stock_watcher", 90, "test@ejemplo.com")
        finally:
            parametros.restaurar("jobs.minutos_reconciliacion", "test@ejemplo.com")
            parametros.restaurar("jobs.minutos_stock_watcher", "test@ejemplo.com")

        llamadas = [(c.args[0], c.kwargs["minutes"]) for c in instancia.reschedule_job.call_args_list]
        assert llamadas[:2] == [("reconciliacion_pedidos", 25), ("stock_watcher", 90)]

    def test_un_parametro_que_no_es_de_tareas_no_toca_el_reloj(self, scheduler_falso):
        app_module.start_scheduler()
        try:
            parametros.guardar("bot.max_mensajes_historial", 50, "test@ejemplo.com")
        finally:
            parametros.restaurar("bot.max_mensajes_historial", "test@ejemplo.com")
        scheduler_falso.return_value.reschedule_job.assert_not_called()

    def test_sin_scheduler_encendido_guardar_no_falla(self):
        # ENABLE_SCHEDULER=false: no hay reloj que reprogramar, pero el valor igual queda guardado.
        app_module._reprogramar("jobs.minutos_sync_productos")  # no debe lanzar

    def test_una_falla_al_reprogramar_no_impide_guardar(self, scheduler_falso):
        app_module.start_scheduler()
        scheduler_falso.return_value.reschedule_job.side_effect = RuntimeError("el reloj no responde")
        try:
            assert parametros.guardar("jobs.minutos_sync_productos", 30, "test@ejemplo.com").valor == 30
        finally:
            parametros.restaurar("jobs.minutos_sync_productos", "test@ejemplo.com")

    def test_suscribirse_dos_veces_no_duplica_los_avisos(self, scheduler_falso):
        app_module.start_scheduler()
        app_module._scheduler = None
        app_module.start_scheduler()  # segundo arranque en el mismo proceso (pasa en los tests)
        instancia = scheduler_falso.return_value
        try:
            parametros.guardar("jobs.minutos_sync_productos", 30, "test@ejemplo.com")
        finally:
            parametros.restaurar("jobs.minutos_sync_productos", "test@ejemplo.com")
        assert instancia.reschedule_job.call_count >= 1
        assert len([c for c in instancia.reschedule_job.call_args_list if c.args[0] == "sync_productos" and c.kwargs["minutes"] == 30]) == 1


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
