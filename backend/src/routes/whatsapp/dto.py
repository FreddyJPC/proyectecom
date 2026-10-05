from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MensajeEntranteDTO:
    wamid: str          # ID único del mensaje asignado por WhatsApp (formato: wamid.xxx)
    telefono: str       # número del cliente en formato internacional (ej: 593987654321)
    contenido: str      # texto del mensaje (o descripción si es imagen/audio)
    tipo: str           # 'texto' | 'imagen' | 'audio'
    referral: Optional[dict] = None
    # Objeto referral completo si vino de anuncio Click-to-WhatsApp (FEP), None si no.
    # Cuando está presente, contiene: source_id (id_anuncio), ctwa_clid, headline, body, etc.
    # Su presencia es la señal de que aplica la ventana gratuita de 72 horas.


@dataclass
class EventoWebhookDTO:
    mensajes: List[MensajeEntranteDTO] = field(default_factory=list)
    es_evento_prueba: bool = False
    # True cuando Meta manda el POST de verificación vacío al registrar el webhook.
    # En ese caso no hay mensajes que procesar -- solo responder 200.


@dataclass
class TareaRespuestaDTO:
    """Lo que WebhookService encola en BotWorker (paso 6) -- ya con la
    conversación resuelta (creada o reutilizada), a diferencia de
    MensajeEntranteDTO que es el dato crudo tal cual llega de Meta.

    Representa una fila de `cola_mensajes` ya materializada en memoria
    (recién encolada, o recuperada al reiniciar el proceso -- ver
    worker.py, recuperar_pendientes())."""

    cola_mensajes_id: int
    conversacion_id: int
    telefono: str
    modo: str = "ia"
        # ia    -> invocar a VictoriaConversationService.procesar_turno()
        # fijo  -> enviar texto_fijo tal cual, sin pasar por el LLM
    texto_fijo: Optional[str] = None
    texto_mensaje_cliente: Optional[str] = None

