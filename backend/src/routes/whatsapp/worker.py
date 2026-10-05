"""
BotWorker: thread daemon que procesa en background la generación y el
envío de la respuesta del bot.

Por qué existe separado del webhook:
- El webhook de WhatsApp DEBE responder a Meta en menos de ~5 segundos o
  Meta considera que falló y reintenta el envío.
- Generar la respuesta completa (en Fase 3.2: consultar el historial de la
  conversación, llamar a la API de Claude, y recién ahí enviar por
  WhatsApp) puede tardar 5-15 segundos fácilmente.
- Solución: en cuanto WebhookService resuelve lo mínimo indispensable
  (idempotencia, conversación, guardar el mensaje del cliente), encola
  la tarea de "generar+enviar la respuesta" acá y sigue -- este worker la
  procesa en su propio thread, sin ninguna presión de tiempo.
- Escalabilidad futura: si hace falta más de un proceso o máquina, este
  contrato (encolar una tarea, un consumidor la procesa) ya está listo
  para migrar a Celery+Redis sin cambiar el código que llama a `encolar`.

Nota de diseño respecto al prompt original de esta fase: se le agregó a
BotWorker la resolución de conversacion_id ANTES de encolar (ver
WebhookService._procesar, paso 6) en vez de dejarla como
`conversacion_id=None` -- la columna `mensajes.conversacion_id` es
NOT NULL, así que guardar la respuesta del bot con None habría roto la
prueba end-to-end de la Tarea 5 con un error de base de datos. Ver
PROGRESS.md, Fase 3, para el detalle completo de esta decisión.

Persistencia de la cola (Fase 3.2, Tarea 1): la queue.Queue en memoria no
sobrevive a un reinicio del proceso -- un mensaje encolado y no procesado
se perdía en silencio. Ahora cada encolar() primero inserta una fila en
`cola_mensajes` (estado='pendiente') y recién después hace put() en la
queue en memoria, incluyendo ese id. Al arrancar (iniciar()),
_recuperar_pendientes() relee las filas que quedaron sin terminar y las
vuelve a poner en la queue -- así el trabajo pendiente sobrevive al
reinicio.

Conexión con Victoria (Fase 3.2, Tarea 9): modo='ia' ahora invoca de
verdad a VictoriaConversationService.procesar_turno(). Se construye de
forma PEREZOSA (recién en el primer uso, no en __init__): construirla
instancia un AnthropicProvider real (get_llm_client()), que falla rápido
si ANTHROPIC_API_KEY no está configurada. Si eso pasara en __init__, el
proceso entero (create_app(), y con él BotWorker) no arrancaría -- y con
él tampoco arrancarían las rutas de escalado (modo='fijo') que NO
necesitan ningún LLM. Con construcción perezosa, esas siguen funcionando
aunque el LLM todavía no esté configurado: la tarea 'ia' que sí lo
necesite simplemente queda en estado='error' (ver _loop()), sin tumbar
nada más.
"""
import logging
import queue
import threading
from typing import Optional

from src.integrations.whatsapp import WhatsAppClient

from .conversation_service import VictoriaConversationService
from .dto import TareaRespuestaDTO
from .repository import ColaMensajeRepository, MensajeRepository

logger = logging.getLogger(__name__)


class BotWorker:
    def __init__(
        self,
        whatsapp_client: WhatsAppClient,
        mensaje_repository: MensajeRepository,
        cola_repository: Optional[ColaMensajeRepository] = None,
        conversation_service: Optional[VictoriaConversationService] = None,
    ):
        self._cola: "queue.Queue[TareaRespuestaDTO]" = queue.Queue()
        self._whatsapp_client = whatsapp_client
        self._mensaje_repository = mensaje_repository
        self._cola_repository = cola_repository or ColaMensajeRepository()
        self._conversation_service = conversation_service
        self._thread = None

    def iniciar(self) -> None:
        """Arranca el thread. Idempotente a propósito: create_app() puede
        ejecutarse más de una vez en el mismo proceso (import del módulo +
        factory de Flask) -- llamar iniciar() dos veces no debe crear dos
        threads consumiendo la misma cola. Por ser idempotente,
        _recuperar_pendientes() también corre solo una vez por proceso."""
        if self._thread is not None:
            return
        self._recuperar_pendientes()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="bot-worker")
        self._thread.start()
        logger.info("BotWorker iniciado")

    def encolar(
        self,
        conversacion_id: int,
        telefono: str,
        modo: str = "ia",
        mensaje_id: Optional[int] = None,
        texto_fijo: Optional[str] = None,
        texto_mensaje_cliente: Optional[str] = None,
    ) -> None:
        """Encola una tarea de respuesta para procesamiento en background.
        Primero deja registro en `cola_mensajes` (sobrevive a un
        reinicio), recién después la pone en la queue en memoria."""
        fila = self._cola_repository.crear(
            conversacion_id=conversacion_id,
            mensaje_id=mensaje_id,
            modo=modo,
            texto_fijo=texto_fijo,
        )
        self._cola.put(
            TareaRespuestaDTO(
                cola_mensajes_id=fila["id"],
                conversacion_id=conversacion_id,
                telefono=telefono,
                modo=modo,
                texto_fijo=texto_fijo,
                texto_mensaje_cliente=texto_mensaje_cliente,
            )
        )

    def _recuperar_pendientes(self) -> None:
        """Se llama una única vez al iniciar el worker -- repone en la
        queue en memoria las tareas que quedaron sin terminar de un
        proceso anterior (ver ColaMensajeRepository.obtener_pendientes)."""
        pendientes = self._cola_repository.obtener_pendientes()
        for fila in pendientes:
            self._cola.put(
                TareaRespuestaDTO(
                    cola_mensajes_id=fila["id"],
                    conversacion_id=fila["conversacion_id"],
                    telefono=fila["telefono"],
                    modo=fila["modo"],
                    texto_fijo=fila["texto_fijo"],
                    texto_mensaje_cliente=fila.get("mensaje_cliente_texto"),
                )
            )
        if pendientes:
            logger.info("Tareas recuperadas de cola_mensajes tras reinicio: %d", len(pendientes))

    def _loop(self) -> None:
        while True:
            tarea = self._cola.get()
            try:
                self._cola_repository.marcar_procesando(tarea.cola_mensajes_id)
                self._procesar(tarea)
                self._cola_repository.marcar_completado(tarea.cola_mensajes_id)
            except Exception as exc:
                # NUNCA dejar que el worker muera por una excepción -- si
                # muere, deja de procesar todos los mensajes siguientes.
                logger.exception("Error procesando tarea en BotWorker", extra={"conversacion_id": tarea.conversacion_id})
                self._cola_repository.marcar_error(tarea.cola_mensajes_id, str(exc))
            finally:
                self._cola.task_done()

    def _obtener_conversation_service(self) -> VictoriaConversationService:
        if self._conversation_service is None:
            self._conversation_service = VictoriaConversationService()
        return self._conversation_service

    def _procesar(self, tarea: TareaRespuestaDTO) -> None:
        """
        modo='ia': VictoriaConversationService.procesar_turno() ya guarda
        el texto final en `mensajes` con rol='bot' por su cuenta (Tarea 6,
        paso 7) -- acá no hay que guardarlo de nuevo, solo enviarlo.

        modo='fijo': el texto ya viene decidido por WebhookService (una
        de las reglas deterministas de escalado) -- acá sí hay que
        guardarlo antes de enviarlo, nadie más lo hizo todavía.
        """
        if tarea.modo == "ia":
            texto_respuesta = self._obtener_conversation_service().procesar_turno(
                conversacion_id=tarea.conversacion_id,
                mensaje_cliente=tarea.texto_mensaje_cliente,
            )
        else:
            texto_respuesta = tarea.texto_fijo
            self._mensaje_repository.crear(
                conversacion_id=tarea.conversacion_id,
                rol="bot",
                contenido=texto_respuesta,
                tipo="texto",
                wamid=None,
            )

        self._whatsapp_client.enviar_texto(telefono=tarea.telefono, mensaje=texto_respuesta)
