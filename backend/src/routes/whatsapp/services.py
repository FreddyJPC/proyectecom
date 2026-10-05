"""
Lógica de negocio del webhook de WhatsApp (Fase 3.1 -- sin IA todavía).

Regla de oro, igual que el webhook de Rocketfy (ver
src/routes/webhooks/services.py): un fallo interno NUNCA debe traducirse
en una respuesta no-200 a Meta -- procesar_mensaje_entrante() nunca lanza.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.integrations.telegram import TelegramNotifier, get_telegram_notifier
from src.integrations.whatsapp import WhatsAppClient, WhatsAppError, get_whatsapp_client

from .dto import MensajeEntranteDTO
from .factory import get_bot_worker
from .repository import ConversacionRepository, LeadRepository, MensajeRepository
from .worker import BotWorker

logger = logging.getLogger(__name__)

FEP_VENTANA_HORAS = 72

_MENSAJE_POSTVENTA = "¡Hola de nuevo! Ya te conecto con nuestro equipo de atención, en un momento te responden 🙋"
_MENSAJE_COMPROBANTE_RECIBIDO = (
    "¡Gracias! Ya recibimos tu comprobante, en un momento uno de nuestros asesores lo confirma ✅"
)


class WebhookService:
    def __init__(
        self,
        whatsapp_client: Optional[WhatsAppClient] = None,
        conversacion_repo: Optional[ConversacionRepository] = None,
        mensaje_repo: Optional[MensajeRepository] = None,
        lead_repo: Optional[LeadRepository] = None,
        telegram_notifier: Optional[TelegramNotifier] = None,
        bot_worker: Optional[BotWorker] = None,
    ):
        self._client = whatsapp_client or get_whatsapp_client()
        self._conversaciones = conversacion_repo or ConversacionRepository()
        self._mensajes = mensaje_repo or MensajeRepository()
        self._leads = lead_repo or LeadRepository()
        self._telegram = telegram_notifier or get_telegram_notifier()
        self._bot_worker = bot_worker or get_bot_worker()

    def procesar_mensaje_entrante(self, dto: MensajeEntranteDTO) -> None:
        """Se llama desde un hilo que el controller dispara DESPUÉS de
        responder 200 a Meta (ver controllers.py) -- nunca debe propagar
        una excepción, no hay nadie esperando una respuesta HTTP acá."""
        try:
            self._procesar(dto)
        except Exception:
            logger.exception("Fallo procesando mensaje de WhatsApp entrante", extra={"wamid": dto.wamid})

    def _procesar(self, dto: MensajeEntranteDTO) -> None:
        # 1. Idempotencia: Meta puede reenviar el mismo webhook si no
        # recibe confirmación a tiempo -- un wamid ya visto no se reprocesa.
        if self._mensajes.existe_por_wamid(dto.wamid):
            logger.info("Mensaje duplicado (wamid ya procesado) -- ignorado", extra={"wamid": dto.wamid})
            return

        # 2 y 3. Conversación: se reutiliza si el cliente ya nos había
        # escrito antes; si no, se crea (con detección de FEP incluida).
        conversacion = self._conversaciones.obtener_por_telefono(dto.telefono)
        if conversacion is None:
            conversacion = self._crear_conversacion(dto)
        else:
            self._conversaciones.actualizar_timestamp(conversacion["id"])

        # 4. Guardar el mensaje del cliente.
        mensaje = self._mensajes.crear(
            conversacion_id=conversacion["id"],
            rol="cliente",
            contenido=dto.contenido,
            tipo=dto.tipo,
            wamid=dto.wamid,
        )

        # 5. Marcar como leído -- buena práctica (dos ticks azules), pero
        # best-effort: un fallo acá no debe impedir que se encole la
        # respuesta al cliente.
        try:
            self._client.marcar_como_leido(dto.wamid)
        except WhatsAppError:
            logger.warning("No se pudo marcar el mensaje como leído", extra={"wamid": dto.wamid}, exc_info=True)

        # 6. Decidir qué encolar -- ver _encolar_respuesta para las 4
        # reglas deterministas (Fase 3.2, Tarea 6): tres de ellas escalan
        # a un humano SIN invocar al LLM siquiera, la última es el caso
        # normal donde Victoria responde.
        self._encolar_respuesta(conversacion, mensaje, dto)

    def _encolar_respuesta(self, conversacion: dict, mensaje: dict, dto: MensajeEntranteDTO) -> None:
        conversacion_id = conversacion["id"]

        # Regla 1: la conversación ya está escalada -- un humano ya está a
        # cargo, no se genera ninguna respuesta automática más.
        if conversacion["estado"] == "escalada":
            return

        # Regla 2: postventa mínimo -- un teléfono con un lead ya
        # despachado (pedido previo) que vuelve a escribir se escala
        # directo, nunca pasa por Victoria (versión mínima del "Flujo 3"
        # de docs/BotPlanifiacion.md -- no el árbol completo de postventa).
        if self._leads.existe_despachado_por_telefono(dto.telefono):
            self._escalar(conversacion_id, dto.telefono, motivo="Cliente con pedido previo escribió de nuevo")
            self._bot_worker.encolar(
                conversacion_id=conversacion_id,
                telefono=dto.telefono,
                modo="fijo",
                mensaje_id=mensaje["id"],
                texto_fijo=_MENSAJE_POSTVENTA,
            )
            return

        # Regla 3: posible comprobante de pago -- Victoria no tiene visión
        # de imágenes todavía, así que no puede verificarlo por su cuenta;
        # la regla es determinista en código, no una decisión del LLM.
        lead = self._leads.obtener_por_conversacion(conversacion_id)
        if dto.tipo == "imagen" and lead is not None and lead["estado"] == "esperando_pago":
            self._escalar(conversacion_id, dto.telefono, motivo="Cliente envió posible comprobante de pago")
            self._bot_worker.encolar(
                conversacion_id=conversacion_id,
                telefono=dto.telefono,
                modo="fijo",
                mensaje_id=mensaje["id"],
                texto_fijo=_MENSAJE_COMPROBANTE_RECIBIDO,
            )
            return

        # Regla 4: cualquier otro caso -- Victoria responde.
        self._bot_worker.encolar(
            conversacion_id=conversacion_id,
            telefono=dto.telefono,
            modo="ia",
            mensaje_id=mensaje["id"],
            texto_mensaje_cliente=dto.contenido,
        )

    def _escalar(self, conversacion_id: int, telefono: str, motivo: str) -> None:
        # marcar_escalada() (no actualizar_estado() genérico) para que
        # también limpie vista_en -- el módulo de Conversaciones del
        # dashboard necesita que CUALQUIER camino de escalado (este
        # determinista, o el de Victoria vía escalar_a_humano) deje la
        # conversación como "sin revisar" otra vez.
        self._conversaciones.marcar_escalada(conversacion_id)
        self._telegram.notificar_escalado(conversacion_id, telefono, motivo)

    def _crear_conversacion(self, dto: MensajeEntranteDTO) -> dict:
        # La presencia de "referral" es la señal de que el cliente llegó
        # desde un anuncio Click-to-WhatsApp -- aplica la ventana gratuita
        # de 72h (docs/BotPlanifiacion.md, sección 4, Flujo 1).
        if dto.referral:
            return self._conversaciones.crear(
                telefono=dto.telefono,
                origen="fep",
                fep_expira_en=datetime.now(timezone.utc) + timedelta(hours=FEP_VENTANA_HORAS),
                id_anuncio=dto.referral.get("source_id"),
                ctwa_clid=dto.referral.get("ctwa_clid"),
            )
        return self._conversaciones.crear(telefono=dto.telefono, origen="directo")
