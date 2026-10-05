import logging

from flask import Flask, g, jsonify, request
from flask_cors import CORS

from src.config.logging_config import configure_logging
from src.config.settings import load_settings
from src.config.supabase_auth import verificar_token
from src.integrations.rocketfy import get_rocketfy_client
from src.jobs.reconciliacion import ReconciliacionService
from src.jobs.stock_watcher import StockWatcherService
from src.routes.catalogos import catalogos_bp
from src.routes.conversaciones import conversaciones_bp
from src.routes.incidencias import incidencias_bp
from src.routes.metricas import metricas_bp
from src.routes.pedidos import pedidos_bp
from src.routes.productos import productos_bp
from src.routes.webhooks import webhooks_bp
from src.routes.whatsapp import whatsapp_bp
from src.routes.whatsapp.factory import get_bot_worker


# Rutas que NO pasan por el login del frontend: /health (sondeo técnico) y
# el webhook de Rocketfy (tiene su propia autenticación por token en la URL,
# ver src/routes/webhooks/controllers.py -- Rocketfy no puede loguearse).
_RUTAS_SIN_LOGIN = {"/health"}


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

    app.register_blueprint(catalogos_bp)
    app.register_blueprint(conversaciones_bp)
    app.register_blueprint(incidencias_bp)
    app.register_blueprint(pedidos_bp)
    app.register_blueprint(productos_bp)
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

    @app.get("/health")
    def health():
        return jsonify(status="ok"), 200

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


def start_scheduler():
    """Arranca APScheduler para el proceso dev-server (`__main__`).

    NOTA (Etapa 8 pendiente): con gunicorn multi-worker, cada worker
    importaría este módulo y arrancaría su propio scheduler — el lock de
    job_locks garantiza que solo una ejecución real ocurra a la vez (ver
    ReconciliacionRepository/StockWatcherRepository.acquire_lock), pero
    sigue siendo un desperdicio de recursos tener N schedulers idle.
    Definir el mecanismo de arranque de jobs en producción (proceso
    dedicado, hook de gunicorn, o cron externo) es tarea de la Etapa 8."""
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(_job_reconciliacion, "interval", minutes=45, id="reconciliacion_pedidos")
    scheduler.add_job(_job_stock_watcher, "interval", minutes=60, id="stock_watcher")
    scheduler.start()
    return scheduler


app = create_app()

if __name__ == "__main__":
    start_scheduler()
    app.run(host="0.0.0.0", port=5000, debug=True)
