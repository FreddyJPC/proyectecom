import logging
from datetime import datetime, timedelta

from flask import Flask, g, jsonify, request
from flask_cors import CORS

from src.config.logging_config import configure_logging
from src.config.parametros import parametros
from src.config.settings import load_settings
from src.config.supabase_auth import verificar_token
from src.integrations.rocketfy import get_rocketfy_client
from src.jobs.latido import LatidoService, estado_latido
from src.jobs.reconciliacion import ReconciliacionService
from src.jobs.seguimiento import SeguimientoService
from src.jobs.stock_watcher import StockWatcherService
from src.routes.ajustes import ajustes_bp
from src.routes.anuncios import anuncios_bp
from src.routes.categorias import categorias_bp
from src.routes.cuentas_bancarias import cuentas_bancarias_bp
from src.routes.catalogos import catalogos_bp
from src.routes.conversaciones import conversaciones_bp
from src.routes.gestion import gestion_bp
from src.routes.incidencias import incidencias_bp
from src.routes.instrucciones import instrucciones_bp
from src.routes.leads import contactos_bp, leads_bp
from src.routes.leads.servicio import LeadsServicio
from src.routes.metricas import metricas_bp
from src.routes.parametros import parametros_bp
from src.routes.pedidos import pedidos_bp
from src.routes.productos import productos_bp
from src.routes.productos_bot import productos_bot_bp
from src.routes.productos_bot.sincronizacion import SincronizacionProductosService
from src.routes.ventas import ventas_bp
from src.routes.webhooks import webhooks_bp
from src.routes.whatsapp import whatsapp_bp
from src.routes.whatsapp.factory import get_bot_worker


# Rutas que NO pasan por el login del frontend: /health (sondeo técnico) y
# el webhook de Rocketfy (tiene su propia autenticación por token en la URL,
# ver src/routes/webhooks/controllers.py -- Rocketfy no puede loguearse).
_RUTAS_SIN_LOGIN = {"/health"}

# Scheduler del proceso (singleton). Ver start_scheduler().
_scheduler = None


def create_app() -> Flask:
    app = Flask(__name__)
    settings = load_settings()
    configure_logging(app, level=settings.log_level)

    CORS(app, origins=[settings.frontend_origin], allow_headers=["Content-Type", "Authorization"])

    @app.before_request
    def _requerir_login():
        # El preflight de CORS nunca manda el header Authorization -- debe
        # pasar siempre, o el navegador nunca llega a mandar la request real.
        if request.method == "OPTIONS":
            return None
        if request.path in _RUTAS_SIN_LOGIN or request.path.startswith("/webhooks/"):
            return None

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify(error="No autenticado."), 401

        usuario = verificar_token(auth_header.removeprefix("Bearer "), settings)
        if usuario is None:
            return jsonify(error="Sesión inválida o expirada."), 401

        g.usuario = usuario
        return None

    app.register_blueprint(ajustes_bp)
    app.register_blueprint(anuncios_bp)
    app.register_blueprint(catalogos_bp)
    app.register_blueprint(categorias_bp)
    app.register_blueprint(cuentas_bancarias_bp)
    app.register_blueprint(conversaciones_bp)
    app.register_blueprint(gestion_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(incidencias_bp)
    app.register_blueprint(instrucciones_bp)
    app.register_blueprint(leads_bp)
    app.register_blueprint(contactos_bp)
    app.register_blueprint(parametros_bp)
    app.register_blueprint(pedidos_bp)
    app.register_blueprint(productos_bp)
    app.register_blueprint(productos_bot_bp)
    app.register_blueprint(metricas_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(whatsapp_bp)

    # Fase 3 (bot de WhatsApp): arranca acá, DENTRO de create_app(), a
    # propósito distinto de como se pidió originalmente ("igual que
    # APScheduler se inicia hoy" -- eso solo pasa bajo
    # `if __name__ == "__main__"`, ver start_scheduler() más abajo). Si el
    # worker se arrancara solo ahí, `flask run` (que es exactamente el
    # comando que pide la Tarea 5 para la prueba end-to-end) nunca
    # arrancaría el thread, y ningún mensaje entrante generaría respuesta.
    # get_bot_worker().iniciar() es idempotente (ver worker.py) así que es
    # seguro llamarlo acá aunque create_app() se ejecute más de una vez en
    # el mismo proceso (pasa hoy: la línea `app = create_app()` de este
    # mismo archivo se suma a la que hace el factory de Flask). Ver
    # PROGRESS.md, Fase 3, para el detalle completo de esta decisión.
    get_bot_worker()

    # Jobs de fondo (reconciliación + stock watcher). En producción el
    # servidor es gunicorn, que importa `app` y nunca ejecuta el bloque
    # `if __name__ == "__main__"` del final -- por eso se encienden acá,
    # con ENABLE_SCHEDULER=true. Con gunicorn debe haber UN solo worker
    # (ver gunicorn.conf.py): cada worker tendría su propio scheduler.
    if settings.enable_scheduler:
        start_scheduler()

    @app.get("/health")
    def health():
        # `scheduler` permite confirmar desde fuera (curl /health) que los
        # jobs quedaron encendidos en producción, sin tener que leer logs.
        # `latido` dice cuándo fue el último latido exitoso a la base de
        # datos (guardado en memoria: /health NO consulta la DB, ver
        # src/jobs/latido/service.py).
        return jsonify(status="ok", scheduler=_scheduler is not None, latido=estado_latido()), 200

    return app


def _job_reconciliacion() -> None:
    try:
        ReconciliacionService(get_rocketfy_client()).ejecutar()
    except Exception:
        logging.getLogger(__name__).exception("Fallo no controlado en job de reconciliación")


def _job_stock_watcher() -> None:
    try:
        StockWatcherService(get_rocketfy_client()).ejecutar()
    except Exception:
        logging.getLogger(__name__).exception("Fallo no controlado en job de stock_watcher")


def _job_sync_productos() -> None:
    try:
        SincronizacionProductosService().ejecutar()
    except Exception:
        logging.getLogger(__name__).exception("Fallo no controlado en job de sincronización de productos")


def _job_enfriar_leads() -> None:
    try:
        LeadsServicio().enfriar_por_silencio()
    except Exception:
        logging.getLogger(__name__).exception("Fallo no controlado en job de enfriamiento de leads")


def _job_seguimiento() -> None:
    try:
        SeguimientoService().ejecutar()
    except Exception:
        logging.getLogger(__name__).exception("Fallo no controlado en job de seguimiento de clientes")


def _job_latido() -> None:
    try:
        LatidoService().ejecutar()
    except Exception:
        logging.getLogger(__name__).exception("Fallo no controlado en job de latido")


# Tarea automática -> parámetro con cada cuántos minutos corre (se cambia desde la app,
# pantalla Parámetros; ver _reprogramar). El latido de la base NO está acá a propósito:
# evita que Supabase pause el proyecto y no es un ajuste del negocio.
_INTERVALOS_DE_JOBS = {
    "reconciliacion_pedidos": "jobs.minutos_reconciliacion",
    "stock_watcher": "jobs.minutos_stock_watcher",
    "sync_productos": "jobs.minutos_sync_productos",
    "enfriar_leads": "jobs.minutos_enfriar_leads",
    "seguimiento": "jobs.minutos_seguimiento",
}


def _reprogramar(clave: str) -> None:
    """Se llama cuando alguien guarda o restaura un parámetro `jobs.*`: el reloj de esa
    tarea se reprograma ya, sin reiniciar el servidor. La próxima corrida cae a los
    minutos nuevos contados desde este momento."""
    scheduler = _scheduler
    if scheduler is None:
        return  # el scheduler está apagado (ENABLE_SCHEDULER=false): al encenderlo leerá el valor nuevo
    for id_job, clave_del_job in _INTERVALOS_DE_JOBS.items():
        if clave_del_job == clave:
            minutos = parametros.valor(clave)
            scheduler.reschedule_job(id_job, trigger="interval", minutes=minutos)
            logging.getLogger("src.scheduler").info("Tarea '%s' reprogramada: ahora corre cada %d min", id_job, minutos)


# Cada cuánto se escribe el latido. Supabase Free pide "unas pocas consultas
# por día" (sin garantía): 4 al día da margen sin costo apreciable.
HORAS_ENTRE_LATIDOS = 6
# La primera corrida se adelanta tras cada arranque para confirmar rápido que
# la base responde (si no, tras un despliegue se esperarían 6 h para saberlo).
SEGUNDOS_HASTA_PRIMER_LATIDO = 30
# La sincronización de productos (Fase F) tarda según cuántos haya publicados:
# se escalona unos minutos tras el arranque para no coincidir con el resto de jobs.
MINUTOS_HASTA_PRIMERA_SINCRONIZACION = 5


def start_scheduler():
    """Arranca APScheduler (reconciliación, stock watcher y sincronización de productos
    con los minutos de sus parámetros —por defecto 45, 60 y 60—, y latido de la DB cada 6 h).
    Idempotente: create_app() puede ejecutarse más de una vez en
    el mismo proceso (import del módulo + factory de Flask) y el bloque
    `__main__` también lo llama -- nunca debe haber dos schedulers.

    Con varios workers de gunicorn habría un scheduler por worker; el lock
    de job_locks (ReconciliacionRepository/StockWatcherRepository
    .acquire_lock) evita que dos ejecuciones reales se pisen, pero sigue
    siendo desperdicio. Por eso producción corre con un solo worker."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    from apscheduler.schedulers.background import BackgroundScheduler

    minutos = {id_job: parametros.valor(clave) for id_job, clave in _INTERVALOS_DE_JOBS.items()}
    scheduler = BackgroundScheduler()
    scheduler.add_job(_job_reconciliacion, "interval", minutes=minutos["reconciliacion_pedidos"], id="reconciliacion_pedidos")
    scheduler.add_job(_job_stock_watcher, "interval", minutes=minutos["stock_watcher"], id="stock_watcher")
    scheduler.add_job(
        _job_sync_productos,
        "interval",
        minutes=minutos["sync_productos"],
        id="sync_productos",
        next_run_time=datetime.now().astimezone() + timedelta(minutes=MINUTOS_HASTA_PRIMERA_SINCRONIZACION),
    )
    scheduler.add_job(_job_enfriar_leads, "interval", minutes=minutos["enfriar_leads"], id="enfriar_leads")
    scheduler.add_job(_job_seguimiento, "interval", minutes=minutos["seguimiento"], id="seguimiento")
    scheduler.add_job(
        _job_latido,
        "interval",
        hours=HORAS_ENTRE_LATIDOS,
        id="latido_db",
        next_run_time=datetime.now().astimezone() + timedelta(seconds=SEGUNDOS_HASTA_PRIMER_LATIDO),
    )
    scheduler.start()
    _scheduler = scheduler
    # Cambiar un intervalo desde la app reprograma el reloj al instante.
    parametros.suscribir("jobs.", _reprogramar)
    # Logger propio: el de Flask se llama igual que este módulo ("src.app")
    # y tiene su propio handler, así que un mensaje de __name__ salía doble.
    logging.getLogger("src.scheduler").info(
        "Scheduler iniciado (reconciliación %d min, stock watcher %d min, sincronización de productos %d min, enfriamiento de leads %d min, seguimiento de clientes %d min, latido DB %d h)",
        minutos["reconciliacion_pedidos"], minutos["stock_watcher"], minutos["sync_productos"], minutos["enfriar_leads"],
        minutos["seguimiento"], HORAS_ENTRE_LATIDOS,
    )
    return scheduler


app = create_app()

if __name__ == "__main__":
    start_scheduler()
    app.run(host="0.0.0.0", port=5000, debug=True)
