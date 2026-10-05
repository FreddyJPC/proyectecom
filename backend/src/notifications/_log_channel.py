"""
Canal por defecto: NO envía nada real, solo loguea qué se habría mandado.

Existe porque todavía no está definido qué mecanismo real se usará para
enviar WhatsApp a los clientes finales de este negocio (Meta Cloud API
directo, Twilio, u otro) — es una decisión pendiente del usuario, no algo
que se pueda inventar. Ver PROGRESS.md, sección de pendientes de Etapa 4.

Cuando se defina, se agrega un _whatsapp.py con la implementación real (el
resto del sistema no cambia: solo se inyecta otro NotificationChannel).
"""
import logging

from ._base import NotificationChannel, NotificationMessage

logger = logging.getLogger(__name__)


class LoggingNotificationChannel(NotificationChannel):
    def send(self, message: NotificationMessage) -> bool:
        logger.info(
            "[NOTIFICACION NO ENVIADA - canal real pendiente de definir] to=%s template=%s components=%s",
            message.to, message.template_name, message.components,
        )
        return True
