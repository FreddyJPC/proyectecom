"""
Procesa eventos del webhook de Rocketfy.

Regla de oro (guía del proveedor, sección 4.3/4.4): un fallo interno NUNCA
debe traducirse en una respuesta no-200 al webhook — el presupuesto de error
es de solo 10 fallos acumulados EN TODA LA VIDA de la URL, sin reset. Por
eso procesar_evento() atrapa cualquier excepción y solo loguea; el
controlador ya respondió (o está por responder) 200 en cuanto la
autenticación fue válida.
"""
import logging
from typing import Optional

from src.integrations.rocketfy.constants import RocketfyStatus
from src.notifications import LoggingNotificationChannel, NotificationMessage, NotificationService

from .repository import WebhookRepository

logger = logging.getLogger(__name__)

# Requerimiento original: avisar al cliente final cuando el paquete está en
# camino ("ten el efectivo listo").
EVENTOS_PARA_CLIENTE = {RocketfyStatus.EN_RUTA}
# Incidencias que ameritan atención del equipo interno, no del cliente.
EVENTOS_PARA_EQUIPO = {RocketfyStatus.NOVEDAD, RocketfyStatus.DEVUELTO_EN_TRANSITO}


class WebhookService:
    def __init__(self, repo: Optional[WebhookRepository] = None, notificador: Optional[NotificationService] = None):
        self._repo = repo or WebhookRepository()
        self._notificador = notificador or NotificationService(LoggingNotificationChannel())

    def procesar_evento(self, payload: dict) -> None:
        order_id = payload.get("order_id")
        if not order_id:
            return  # ping de validación de alta (cuerpo vacío) — nada que hacer

        try:
            self._procesar(payload, order_id)
        except Exception:
            logger.exception(
                "Fallo procesando evento de webhook (no se propaga — Rocket ya recibió 200)",
                extra={"order_id": order_id},
            )

    def _procesar(self, payload: dict, order_id: int) -> None:
        status_id = payload.get("status_id")
        event_date = payload.get("event_date")
        shopify_order_id = payload.get("shopify_order_id")

        es_nuevo = self._repo.guardar_evento(
            id_rocketfy=order_id,
            status_id=status_id,
            event_date=event_date,
            shopify_order_id=shopify_order_id,
            payload=payload,
        )
        if not es_nuevo:
            logger.info(
                "Evento duplicado (order_id, status_id, event_date) — ignorado",
                extra={"order_id": order_id},
            )
            return

        self._repo.actualizar_estado_pedido(id_rocketfy=order_id, status_id=status_id)
        self._repo.marcar_procesado(id_rocketfy=order_id, status_id=status_id, event_date=event_date)
        self._notificar_si_aplica(order_id, status_id, payload)

    def _notificar_si_aplica(self, order_id: int, status_id, payload: dict) -> None:
        try:
            estado = RocketfyStatus(status_id)
        except ValueError:
            logger.info(
                "status_id desconocido (%s) — evento guardado, sin notificación", status_id,
                extra={"order_id": order_id},
            )
            return

        if estado in EVENTOS_PARA_EQUIPO:
            logger.warning(
                "Incidencia en pedido: %s", payload.get("details", ""),
                extra={"order_id": order_id},
            )
            return

        if estado not in EVENTOS_PARA_CLIENTE:
            return

        datos_pedido = self._repo.obtener_datos_pedido(order_id) or {}
        telefono = datos_pedido.get("telefono")
        if not telefono:
            logger.info(
                "No se encontró teléfono local para notificar (pedido no gestionado por nosotros?)",
                extra={"order_id": order_id},
            )
            return

        self._notificador.send(
            NotificationMessage(
                to=telefono,
                template_name="rocketfy_en_ruta",
                components=[{"tipo": "status_name", "valor": payload.get("status_name", "")}],
            )
        )
