"""
Transcripción de audio (voz -> texto), detrás de una interfaz — igual que el LLM (`integrations/llm`).

Por qué existe: la API de Claude entiende imágenes pero NO audio (docs/PLAN_IMAGENES_AUDIO.md), así que las notas de voz de los
clientes se pasan primero a texto con un servicio de transcripción y Victoria lee ese texto como si el cliente lo hubiera escrito.
Cambiar de proveedor es escribir otra clase que cumpla `TranscriptionProvider`; nada más del proyecto cambia.
"""
from abc import ABC, abstractmethod


class TranscripcionError(Exception):
    """No se pudo transcribir (servicio caído, formato no soportado, clave inválida…). El mensaje es para los logs."""


class TranscriptionProvider(ABC):
    @abstractmethod
    def transcribir(self, audio: bytes, mime: str, idioma: str = "es") -> str:
        """Devuelve lo que se dice en el audio, como texto. Puede devolver "" si no hay voz."""
