from functools import lru_cache

from src.config.settings import load_settings

from .client import TelegramNotifier


@lru_cache(maxsize=1)
def get_telegram_notifier() -> TelegramNotifier:
    """Singleton por proceso -- mismo motivo que los otros factories
    (get_rocketfy_client, get_whatsapp_client): reutilizar la instancia en
    vez de reconstruirla en cada escalado."""
    settings = load_settings()
    return TelegramNotifier(bot_token=settings.telegram_bot_token, chat_id=settings.telegram_chat_id)
