from functools import lru_cache

from src.config.settings import load_settings

from .client import WhatsAppClient


@lru_cache(maxsize=1)
def get_whatsapp_client() -> WhatsAppClient:
    """Cliente singleton por proceso -- mismo motivo que get_rocketfy_client():
    reutiliza la sesión HTTP en vez de reconstruirla en cada uso."""
    settings = load_settings()
    return WhatsAppClient(settings.whatsapp_phone_number_id, settings.whatsapp_api_token)
