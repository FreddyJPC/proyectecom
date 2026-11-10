"""Transcripción con la API de OpenAI (`/v1/audio/transcriptions`). Solo usa `requests`: sin SDK nuevo que mantener."""
import logging
from typing import Optional

import requests

from .contratos import TranscripcionError, TranscriptionProvider

logger = logging.getLogger(__name__)

_URL = "https://api.openai.com/v1/audio/transcriptions"
# Formatos que la API acepta -> extensión que debe llevar el nombre del archivo. Los audios de WhatsApp suelen ser ogg (opus), aac,
# mp4 o mpeg; `amr` (llamadas antiguas) NO está soportado por el servicio y se rechaza antes de pedirlo.
_EXTENSION_POR_MIME = {
    "audio/ogg": "ogg", "audio/opus": "ogg", "audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/mp4": "m4a", "audio/m4a": "m4a",
    "audio/x-m4a": "m4a", "audio/aac": "m4a", "audio/wav": "wav", "audio/x-wav": "wav", "audio/webm": "webm", "audio/flac": "flac",
}


class OpenAITranscriptionProvider(TranscriptionProvider):
    def __init__(self, api_key: str, modelo: str, timeout: int = 60):
        self._api_key = api_key
        self._modelo = modelo
        self._timeout = timeout
        self._session = requests.Session()

    def transcribir(self, audio: bytes, mime: str, idioma: str = "es") -> str:
        tipo = (mime or "").split(";")[0].strip().lower()
        extension: Optional[str] = _EXTENSION_POR_MIME.get(tipo)
        if extension is None:
            raise TranscripcionError(f"Formato de audio no soportado para transcribir: {tipo or 'desconocido'}")
        try:
            respuesta = self._session.post(
                _URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"file": (f"audio.{extension}", audio, tipo)},
                data={"model": self._modelo, "language": idioma, "response_format": "json"},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise TranscripcionError(f"Error de red llamando al servicio de transcripción: {exc}") from exc
        if respuesta.status_code in (401, 403):
            raise TranscripcionError("El servicio de transcripción rechazó la clave (revisa OPENAI_API_KEY)")
        if respuesta.status_code >= 400:
            raise TranscripcionError(f"El servicio de transcripción respondió HTTP {respuesta.status_code}")
        try:
            return (respuesta.json().get("text") or "").strip()
        except ValueError as exc:
            raise TranscripcionError("Respuesta no-JSON del servicio de transcripción") from exc
