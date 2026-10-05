"""
Configuración desde variables de entorno. Falla rápido (KeyError) si falta
algo indispensable, en vez de arrancar a medias con valores None silenciosos.
"""
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    rocketfy_base_url: str
    rocketfy_account_email: str
    rocketfy_api_token: str
    rocketfy_webhook_token: str
    supabase_db_url: str
    log_level: str
    frontend_origin: str
    supabase_url: str
    supabase_anon_key: str
    # Fase 3 - Bot de WhatsApp (Victoria). Requeridas ya (fail-fast): el
    # canal no tiene sentido sin ellas. Opcionales: se usan recién en fases
    # posteriores (3.2 para Claude, notificación de escalado para Telegram).
    whatsapp_api_token: str
    whatsapp_phone_number_id: str
    whatsapp_webhook_verify_token: str
    whatsapp_waba_id: Optional[str]
    anthropic_api_key: Optional[str]
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    # Fase 3.2 - cerebro conversacional de Victoria detrás de LLMProvider.
    # anthropic_api_key se queda opcional acá a propósito -- no todo el
    # sistema (p.ej. cualquier código que solo necesite Settings para
    # abrir una conexión a Postgres) debería dejar de arrancar solo porque
    # el LLM no está configurado todavía. El fail-fast condicional
    # ("requerida SOLO SI LLM_PROVIDER=anthropic") vive en
    # integrations/llm/factory.py::get_llm_client(), que es el único punto
    # que de verdad necesita la key -- ver PROGRESS.md, Fase 3.2, para el
    # razonamiento completo de por qué no vive acá.
    llm_provider: str
    llm_model: str
    bot_max_turnos_herramientas: int
    bot_max_mensajes_historial: int


def load_settings() -> Settings:
    return Settings(
        rocketfy_base_url=os.environ["ROCKETFY_BASE_URL"],
        rocketfy_account_email=os.environ["ROCKETFY_ACCOUNT_EMAIL"],
        rocketfy_api_token=os.environ["ROCKETFY_API_TOKEN"],
        rocketfy_webhook_token=os.environ["ROCKETFY_WEBHOOK_TOKEN"],
        supabase_db_url=os.environ["SUPABASE_DB_URL"],
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        supabase_url=os.environ["SUPABASE_URL"],
        supabase_anon_key=os.environ["SUPABASE_ANON_KEY"],
        whatsapp_api_token=os.environ["WHATSAPP_API_TOKEN"],
        whatsapp_phone_number_id=os.environ["WHATSAPP_PHONE_NUMBER_ID"],
        whatsapp_webhook_verify_token=os.environ["WHATSAPP_WEBHOOK_VERIFY_TOKEN"],
        whatsapp_waba_id=os.getenv("WHATSAPP_WABA_ID") or None,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        llm_provider=os.getenv("LLM_PROVIDER", "anthropic"),
        llm_model=os.getenv("LLM_MODEL", "claude-sonnet-5"),
        bot_max_turnos_herramientas=int(os.getenv("BOT_MAX_TURNOS_HERRAMIENTAS", "5")),
        bot_max_mensajes_historial=int(os.getenv("BOT_MAX_MENSAJES_HISTORIAL", "40")),
    )
