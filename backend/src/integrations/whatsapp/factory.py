from functools import lru_cache
from typing import Optional

from src.config.settings import load_settings

from .client import WhatsAppClient


@lru_cache(maxsize=1)
def get_whatsapp_client() -> WhatsAppClient:
    """Cliente singleton por proceso -- mismo motivo que get_rocketfy_client():
    reutiliza la sesión HTTP en vez de reconstruirla en cada uso."""
    settings = load_settings()
    return WhatsAppClient(settings.whatsapp_phone_number_id, settings.whatsapp_api_token)


def numero_principal() -> str:
    """El phone_number_id del número principal del negocio (el de Victoria, variable WHATSAPP_PHONE_NUMBER_ID)."""
    return load_settings().whatsapp_phone_number_id


def normalizar_numero_negocio(numero: Optional[str]) -> Optional[str]:
    """Cómo se guarda el número del negocio en una conversación (migración 037): None si es el principal o si no se sabe;
    el phone_number_id si es otro. Así las conversaciones de siempre no cambian de clave."""
    numero = (numero or "").strip()
    if not numero or numero == numero_principal():
        return None
    return numero


@lru_cache(maxsize=16)
def _cliente_de_otro_numero(numero: str) -> WhatsAppClient:
    # El mismo token de la cuenta sirve para todos los números que la cuenta administra.
    return WhatsAppClient(numero, load_settings().whatsapp_api_token)


def get_whatsapp_client_para(numero: Optional[str]) -> WhatsAppClient:
    """El cliente que envía DESDE ese número del negocio (None = el principal). Módulo «Inmuebles»: una propiedad puede
    atenderse por otro número de WhatsApp; la respuesta tiene que salir del mismo número al que escribió el cliente."""
    numero = normalizar_numero_negocio(numero)
    return get_whatsapp_client() if numero is None else _cliente_de_otro_numero(numero)
