import os
from functools import lru_cache
from typing import Optional

from src.config.parametros import parametros

from .contratos import TranscriptionProvider
from .proveedor_openai import OpenAITranscriptionProvider


@lru_cache(maxsize=4)
def _proveedor_openai(api_key: str, modelo: str) -> OpenAITranscriptionProvider:
    return OpenAITranscriptionProvider(api_key=api_key, modelo=modelo)


def get_transcriptor() -> Optional[TranscriptionProvider]:
    """El servicio de transcripción activo, o None si no hay clave (OPENAI_API_KEY). Sin clave los audios no se transcriben y Victoria
    le pide al cliente que escriba; el resto del bot sigue igual. Se pide en cada uso para que un cambio de modelo desde la app se note
    en el siguiente audio."""
    clave = os.getenv("OPENAI_API_KEY") or None
    if not clave:
        return None
    return _proveedor_openai(clave, parametros.valor("bot.modelo_transcripcion"))
