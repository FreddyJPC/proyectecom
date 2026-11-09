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

Ráfagas y fallos (huecos cerrados el 2026-11-09):
- Mucha gente escribe en pedacitos («Hola», «buenas tardes», «quiero unos audífonos»). Antes cada pedacito
  disparaba su propia respuesta. Ahora `encolar` ESPERA unos segundos (parámetro
  `bot.segundos_espera_mensajes`) y, si llega otro mensaje de la misma conversación, reinicia la espera y
  reutiliza la misma tarea: Victoria lee todo junto y responde una vez. La tarea ya está guardada en
  `cola_mensajes` mientras espera, así que un reinicio no la pierde.
- Si la IA falla al redactar (sobrecarga, corte de red), la tarea se reintenta hasta REINTENTOS_DE_GENERACION
  veces con pausa; si al final no se pudo responder, o la respuesta no se pudo ENVIAR, queda en 'error' y se
  avisa al dueño por Telegram (antes quedaba en silencio y el cliente sin respuesta).
"""
import logging
import queue
import threading
import time
from typing import Dict, Optional

from src.config.parametros import parametros
from src.integrations.canales import RegistroCanales
from src.integrations.telegram import TelegramNotifier, get_telegram_notifier

from .conversation_service import VictoriaConversationService
from .dto import TareaRespuestaDTO
from .repository import ColaMensajeRepository, MensajeRepository

logger = logging.getLogger(__name__)

# Cuántas veces más se intenta redactar la respuesta si la IA falla, y cuánto se espera antes de cada una.
REINTENTOS_DE_GENERACION = 2
PAUSAS_ENTRE_REINTENTOS = (10.0, 30.0)
# La espera para juntar mensajes se reinicia con cada mensaje nuevo, pero nunca pasa de esta cantidad de veces
# el valor configurado (si no, alguien que escribe sin parar nunca recibiría respuesta).
FACTOR_MAXIMO_DE_ESPERA = 3


class _ErrorDeEnvio(Exception):
    """La respuesta ya estaba redactada (y guardada) pero no se pudo entregar por el canal. No se reintenta sola:
    volver a generar y enviar podría duplicar lo que el cliente ya recibió a medias."""


class _Espera:
    """Una tarea 'ia' que aguarda unos segundos por si el cliente sigue escribiendo."""

    def __init__(self, tarea: TareaRespuestaDTO, inicio: float):
        self.tarea = tarea
        self.inicio = inicio
        self.version = 0
        self.temporizador: Optional[threading.Timer] = None


class BotWorker:
    def __init__(
        self,
        canales: RegistroCanales,
        mensaje_repository: MensajeRepository,
        cola_repository: Optional[ColaMensajeRepository] = None,
        conversation_service: Optional[VictoriaConversationService] = None,
        segundos_espera: Optional[float] = None,
        telegram: Optional[TelegramNotifier] = None,
        pausas_reintento: Optional[tuple] = None,
    ):
        self._cola: "queue.Queue[TareaRespuestaDTO]" = queue.Queue()
        self._canales = canales
        self._mensaje_repository = mensaje_repository
        self._cola_repository = cola_repository or ColaMensajeRepository()
        self._conversation_service = conversation_service
        # None = leer el parámetro en cada mensaje (se cambia desde la app); un número lo fija (tests).
        self._segundos_espera_fijo = segundos_espera
        self._telegram_fijo = telegram
        self._pausas_reintento = pausas_reintento if pausas_reintento is not None else PAUSAS_ENTRE_REINTENTOS
        self._esperando: Dict[int, _Espera] = {}
        self._candado = threading.Lock()
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

    def _espera_en_segundos(self) -> float:
        if self._segundos_espera_fijo is not None:
            return float(self._segundos_espera_fijo)
        try:
            return float(parametros.valor("bot.segundos_espera_mensajes"))
        except Exception:
            logger.exception("No se pudo leer la espera para juntar mensajes (se responde sin esperar)")
            return 0.0

    def encolar(
        self,
        conversacion_id: int,
        canal: str,
        id_externo: str,
        modo: str = "ia",
        mensaje_id: Optional[int] = None,
        texto_fijo: Optional[str] = None,
        texto_mensaje_cliente: Optional[str] = None,
    ) -> None:
        """Encola una tarea de respuesta para procesamiento en background.
        Primero deja registro en `cola_mensajes` (sobrevive a un
        reinicio), recién después la pone en la queue en memoria.

        Los mensajes de modo 'ia' esperan unos segundos antes de procesarse (ver la nota de ráfagas arriba): si
        ya hay una tarea esperando para esta conversación, no se crea otra, solo se reinicia la espera."""
        espera = self._espera_en_segundos() if modo == "ia" else 0.0
        if espera <= 0:
            self._poner_en_cola(self._crear_tarea(conversacion_id, canal, id_externo, modo, mensaje_id, texto_fijo, texto_mensaje_cliente))
            return

        with self._candado:
            ahora = time.monotonic()
            actual = self._esperando.get(conversacion_id)
            if actual is None:
                tarea = self._crear_tarea(conversacion_id, canal, id_externo, modo, mensaje_id, texto_fijo, texto_mensaje_cliente)
                actual = _Espera(tarea, inicio=ahora)
                self._esperando[conversacion_id] = actual
            else:
                actual.tarea.texto_mensaje_cliente = texto_mensaje_cliente
                if actual.temporizador is not None:
                    actual.temporizador.cancel()
            actual.version += 1
            restante = min(espera, actual.inicio + espera * FACTOR_MAXIMO_DE_ESPERA - ahora)
            version = actual.version
            actual.temporizador = threading.Timer(max(restante, 0.0), self._terminar_espera, args=(conversacion_id, version))
            actual.temporizador.daemon = True
            actual.temporizador.start()

    def _crear_tarea(self, conversacion_id, canal, id_externo, modo, mensaje_id, texto_fijo, texto_mensaje_cliente) -> TareaRespuestaDTO:
        fila = self._cola_repository.crear(
            conversacion_id=conversacion_id,
            mensaje_id=mensaje_id,
            modo=modo,
            texto_fijo=texto_fijo,
        )
        return TareaRespuestaDTO(
            cola_mensajes_id=fila["id"],
            conversacion_id=conversacion_id,
            canal=canal,
            id_externo=id_externo,
            modo=modo,
            texto_fijo=texto_fijo,
            texto_mensaje_cliente=texto_mensaje_cliente,
        )

    def _poner_en_cola(self, tarea: TareaRespuestaDTO) -> None:
        self._cola.put(tarea)

    def _terminar_espera(self, conversacion_id: int, version: int) -> None:
        """Se acabó la espera sin mensajes nuevos: la tarea pasa a la cola real. Si mientras tanto llegó otro
        mensaje (cambió la versión), este temporizador ya no manda y no hace nada."""
        with self._candado:
            actual = self._esperando.get(conversacion_id)
            if actual is None or actual.version != version:
                return
            del self._esperando[conversacion_id]
        self._poner_en_cola(actual.tarea)

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
                    canal=fila["canal"],
                    id_externo=fila["id_externo"],
                    modo=fila["modo"],
                    texto_fijo=fila["texto_fijo"],
                    texto_mensaje_cliente=fila.get("mensaje_cliente_texto"),
                    intentos=fila.get("intentos") or 0,
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
                try:
                    self._manejar_fallo(tarea, exc)
                except Exception:
                    logger.exception("No se pudo registrar el fallo de una tarea", extra={"conversacion_id": tarea.conversacion_id})
            finally:
                self._cola.task_done()

    def _manejar_fallo(self, tarea: TareaRespuestaDTO, exc: Exception) -> None:
        """Un fallo al REDACTAR (la IA, la base) se reintenta unas veces con pausa; uno al ENVIAR, o cuando ya no
        quedan reintentos, deja la tarea en 'error' y avisa al dueño."""
        detalle = str(exc)
        if tarea.modo == "ia" and not isinstance(exc, _ErrorDeEnvio) and tarea.intentos < REINTENTOS_DE_GENERACION:
            tarea.intentos = self._cola_repository.marcar_para_reintento(tarea.cola_mensajes_id, detalle)
            pausa = self._pausas_reintento[min(tarea.intentos - 1, len(self._pausas_reintento) - 1)]
            logger.warning("Se reintentará la respuesta en %.0f s (intento %d)", pausa, tarea.intentos)
            temporizador = threading.Timer(pausa, self._poner_en_cola, args=(tarea,))
            temporizador.daemon = True
            temporizador.start()
            return
        self._cola_repository.marcar_error(tarea.cola_mensajes_id, detalle)
        self._avisar_fallo(tarea, detalle)

    def _avisar_fallo(self, tarea: TareaRespuestaDTO, detalle: str) -> None:
        """Avisa al dueño por Telegram que un cliente se quedó sin respuesta. Best-effort: nunca lanza."""
        try:
            notificador = self._telegram_fijo or get_telegram_notifier()
            notificador.notificar_aviso(
                "🔴 Un cliente se quedó sin respuesta",
                f"Conversación ID: {tarea.conversacion_id} ({tarea.canal})\n"
                f"Motivo: {detalle[:300]}\n\n"
                "Ábrela en la app (Conversaciones) y respóndele a mano.",
            )
        except Exception:
            logger.exception("No se pudo avisar por Telegram del fallo de una respuesta")

    def _obtener_conversation_service(self) -> VictoriaConversationService:
        if self._conversation_service is None:
            self._conversation_service = VictoriaConversationService()
        return self._conversation_service

    def _procesar(self, tarea: TareaRespuestaDTO) -> None:
        """
        modo='ia': VictoriaConversationService.procesar_turno() ya guarda
        el texto final en `mensajes` con rol='bot' por su cuenta (Tarea 6,
        paso 7) -- acá no hay que guardarlo de nuevo, solo enviarlo. Si
        devuelve "" es que no había nada sin responder (otra tarea ya lo
        contestó): no se envía nada.

        modo='fijo': el texto ya viene decidido por WebhookService (una
        de las reglas deterministas de escalado) -- acá sí hay que
        guardarlo antes de enviarlo, nadie más lo hizo todavía.
        """
        if tarea.modo == "ia":
            texto_respuesta = self._obtener_conversation_service().procesar_turno(
                conversacion_id=tarea.conversacion_id,
                mensaje_cliente=tarea.texto_mensaje_cliente,
            )
            if not texto_respuesta:
                return
        else:
            texto_respuesta = tarea.texto_fijo
            self._mensaje_repository.crear(
                conversacion_id=tarea.conversacion_id,
                rol="bot",
                contenido=texto_respuesta,
                tipo="texto",
                wamid=None,
            )

        try:
            self._canales.para(tarea.canal).enviar_texto(tarea.id_externo, texto_respuesta)
        except Exception as exc:
            raise _ErrorDeEnvio(str(exc)) from exc
