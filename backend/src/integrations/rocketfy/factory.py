from functools import lru_cache

from src.config.settings import load_settings

from .client import RocketfyClient


@lru_cache(maxsize=1)
def get_rocketfy_client() -> RocketfyClient:
    """Cliente singleton por proceso — reutiliza la sesión HTTP (y su pool
    de conexiones) en vez de reconstruirla en cada request/tick de job."""
    settings = load_settings()
    return RocketfyClient(settings.rocketfy_base_url, settings.rocketfy_account_email, settings.rocketfy_api_token)
