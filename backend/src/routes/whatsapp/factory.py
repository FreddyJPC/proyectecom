from functools import lru_cache

from src.integrations.whatsapp import get_whatsapp_client

from .repository import ColaMensajeRepository, MensajeRepository
from .worker import BotWorker


@lru_cache(maxsize=1)
def get_bot_worker() -> BotWorker:
    """Worker singleton por proceso -- se crea Y se arranca la primera vez
    que se pide (BotWorker.iniciar() es idempotente). lru_cache garantiza
    una sola instancia real sin importar cuántas veces se llame, incluido
    el caso de que create_app() se ejecute más de una vez en el mismo
    proceso (ver PROGRESS.md, Fase 3, nota sobre app.py)."""
    worker = BotWorker(
        whatsapp_client=get_whatsapp_client(),
        mensaje_repository=MensajeRepository(),
        cola_repository=ColaMensajeRepository(),
    )
    worker.iniciar()
    return worker
