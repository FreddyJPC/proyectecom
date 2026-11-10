"""
VictoriaConversationService: arma todo el contexto, ejecuta el loop de
tool use, y devuelve el texto final para el cliente.

Trabaja EXCLUSIVAMENTE con los tipos neutrales de integrations/llm/contratos.py
-- no conoce ni le importa qué proveedor de LLM está detrás de LLMProvider.
Recibe el cliente LLM por inyección (vía get_llm_client()), nunca
instancia un proveedor concreto directamente.

Separación de responsabilidades: procesar_turno() recibe un mensaje del
cliente y devuelve el texto de respuesta -- sin llamar a WhatsAppClient
dentro de sí misma. Quien la llama (BotWorker en producción, o
tools/chat_con_victoria.py en pruebas) decide qué hacer con el texto
devuelto.
"""
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from src.config.parametros import parametros
from src.integrations.llm.contratos import AdjuntoLLM, LLMProvider, MensajeLLM
from src.integrations.llm.factory import get_llm_client
from src.routes.entregas.repository import EntregaRepository
from src.routes.gestion.tipos import ESTADOS_EN_MANOS_DEL_DUENO
from src.routes.ventas.origen import es_de_cierre_manual

from .contexto_contacto import formatear_historial
from .ficha import formatear_ficha_producto
from .instrucciones import instrucciones_vigentes
from .repository import ConversacionRepository, LeadRepository, MensajeRepository, ProductoBotRepository
from .tools import HerramientasVictoria, herramientas_de_victoria

logger = logging.getLogger(__name__)

# Lo que la IA puede ver (docs/PLAN_IMAGENES_AUDIO.md, F2). Un archivo más pesado se rechaza antes de pedirlo a Meta.
_MIMES_DE_IMAGEN = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MIME_PDF = "application/pdf"
# Quién le «habla» a Victoria: el cliente y el sistema (avisos internos del panel, que el cliente nunca ve).
ROLES_QUE_ESPERAN_RESPUESTA = ("cliente", "sistema")

_AUDIO_NO_ENTENDIDO = (
    "[audio {motivo}: dile con amabilidad que no lograste entender el audio y que, por favor, lo envíe de nuevo donde se "
    "escuche mejor o que te escriba su mensaje; no adivines ni inventes lo que dijo]"
)
_MAXIMO_BYTES_DE_ARCHIVO = 7_000_000  # la API acepta 10 MB en base64 (~7,5 MB reales)

_ZONA_ECUADOR = timezone(timedelta(hours=-5))
_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_legible_ecuador() -> str:
    momento = datetime.now(_ZONA_ECUADOR)
    return f"{momento.day} de {_MESES_ES[momento.month - 1]} de {momento.year}"


class VictoriaConversationService:
    def __init__(
        self,
        llm_client: Optional[LLMProvider] = None,
        lead_repo: Optional[LeadRepository] = None,
        conversacion_repo: Optional[ConversacionRepository] = None,
        mensaje_repo: Optional[MensajeRepository] = None,
        producto_repo: Optional[ProductoBotRepository] = None,
        ejecutor_herramientas: Optional[HerramientasVictoria] = None,
        max_turnos_herramientas: Optional[int] = None,
        max_mensajes_historial: Optional[int] = None,
        enviar_fotos: Optional[bool] = None,
        plantilla: Optional[str] = None,
        entrega_repo: Optional[EntregaRepository] = None,
        canales=None,
        transcriptor=None,
    ):
        # Qué tan largo es el historial, cuántas vueltas con herramientas se permiten, si se
        # ofrece la foto y qué modelo responde son PARÁMETROS que se cambian desde la app
        # (src/config/parametros): se leen en cada turno, no una vez al construir el servicio
        # (el worker lo construye una sola vez por proceso). Los argumentos de abajo los fijan
        # a la fuerza: los usan los tests y «Probar con Victoria», que no deben depender de ellos.
        self._llm_fijo = llm_client
        self._leads = lead_repo or LeadRepository()
        self._conversaciones = conversacion_repo or ConversacionRepository()
        self._mensajes = mensaje_repo or MensajeRepository()
        self._productos = producto_repo or ProductoBotRepository()
        self._ejecutor = ejecutor_herramientas or HerramientasVictoria()
        self._entregas = entrega_repo or EntregaRepository()
        self._max_turnos_fijo = max_turnos_herramientas
        self._max_historial_fijo = max_mensajes_historial
        self._enviar_fotos_fijo = enviar_fotos
        # Las instrucciones de Victoria: por defecto las que rigen hoy (la versión publicada desde la app o,
        # si no hay, el archivo del código); «Probar con Victoria» puede pasar las del borrador.
        self._plantilla_fija = plantilla
        # Perezoso: el registro de canales (para bajar las fotos del cliente) solo se arma si llega una foto.
        self._canales_fijo = canales
        # Perezoso, igual: el servicio de transcripción (voz -> texto) solo se arma si llega un audio. None = el de producción.
        self._transcriptor_fijo = transcriptor

    def procesar_turno(self, conversacion_id: int, mensaje_cliente: Optional[str] = None) -> str:
        """Responde lo que el cliente escribió y Victoria todavía no contestó.

        Lee de `mensajes` TODO el bloque de mensajes seguidos del cliente que no tienen respuesta (si escribió
        «Hola», «buenas tardes» y «quiero unos audífonos», los ve juntos y contesta una vez). Si no queda nada sin
        responder (otro turno ya lo contestó, p. ej. tras un reinicio), devuelve "" y no se envía nada.
        `mensaje_cliente` solo sirve de respaldo cuando la conversación aún no tiene mensajes guardados."""
        filas = self._mensajes.obtener_por_conversacion(conversacion_id)
        historial_filas, pendientes = self._separar_sin_responder(filas)
        adjuntos: List[AdjuntoLLM] = []
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        if pendientes:
            texto_cliente, adjuntos = self._preparar_mensaje_del_cliente(conversacion, pendientes)
        elif not filas and mensaje_cliente:
            texto_cliente = mensaje_cliente
        else:
            return ""
        lead = self._leads.obtener_o_crear(
            conversacion_id,
            contacto_id=conversacion["contacto_id"],
            telefono=conversacion.get("telefono"),
            dias_atribucion=parametros.valor("leads.dias_atribucion"),
        )

        producto_contexto = self._resolver_producto_contexto(lead, conversacion)
        plantilla = self._plantilla_fija if self._plantilla_fija is not None else instrucciones_vigentes.plantilla()
        system_prompt = plantilla.format(
            contexto_producto=self._aviso_producto_no_disponible(lead, producto_contexto)
            + self._formatear_contexto_producto(producto_contexto),
            contexto_lead_actual=self._formatear_contexto_lead(lead, producto_contexto)
            + self._historial_del_cliente(conversacion, lead),
            fecha_actual=_fecha_legible_ecuador(),
        )

        # Una sola lectura de los parámetros por turno: si cambian mientras Victoria
        # responde, este mensaje termina con las reglas con que empezó.
        llm = self._llm_fijo or get_llm_client()
        max_turnos = self._max_turnos_fijo if self._max_turnos_fijo is not None else parametros.valor("bot.max_turnos_herramientas")
        max_historial = (
            self._max_historial_fijo if self._max_historial_fijo is not None else parametros.valor("bot.max_mensajes_historial")
        )
        # Fase G2: la herramienta de la foto solo se ofrece si está encendida (parámetro «Enviar fotos»).
        enviar_fotos = self._enviar_fotos_fijo if self._enviar_fotos_fijo is not None else parametros.valor("bot.enviar_fotos")
        herramientas = herramientas_de_victoria(enviar_fotos)

        mensajes: List[MensajeLLM] = self._construir_historial(historial_filas, max_historial)
        mensajes.append(MensajeLLM(rol="user", texto=texto_cliente, adjuntos=adjuntos))

        partes_de_texto: List[str] = []
        ya_escalo = False

        for _ in range(max_turnos):
            respuesta = llm.generar_respuesta(
                system=system_prompt, mensajes=mensajes, herramientas=herramientas
            )
            partes_de_texto.append(respuesta.texto)

            if respuesta.razon_de_parada in ("fin", "limite_alcanzado"):
                break

            # necesita_herramientas
            mensajes.append(
                MensajeLLM(rol="assistant", texto=respuesta.texto, llamadas_herramientas=respuesta.llamadas_herramientas)
            )

            resultados = []
            for llamada in respuesta.llamadas_herramientas:
                resultado = self._ejecutor.ejecutar(
                    nombre=llamada.nombre,
                    lead_id=lead["id"],
                    conversacion_id=conversacion_id,
                    entrada=llamada.entrada,
                    id_llamada=llamada.id,
                )
                resultados.append(resultado)
                if llamada.nombre == "escalar_a_humano":
                    ya_escalo = True

            # ADR-012: la conversación también pasa a manos del dueño sin escalar (un producto propio:
            # intención de compra que él debe atender, o pedido cerrado). Se mira el estado real.
            if ya_escalo or self._pasó_a_manos_de_una_persona(conversacion_id):
                ya_escalo = True

            mensajes.append(MensajeLLM(rol="user", resultados_herramientas=resultados))

            if ya_escalo:
                # Se permite UNA iteración más para que el LLM redacte la
                # despedida con el resultado que le llegó -- después de
                # esa, se corta pase lo que pase (no es criterio del
                # modelo seguir la conversación tras escalar).
                despedida = llm.generar_respuesta(
                    system=system_prompt, mensajes=mensajes, herramientas=herramientas
                )
                partes_de_texto.append(despedida.texto)
                break
        else:
            logger.warning(
                "Se alcanzó el límite de turnos de herramientas sin resolver -- se escala",
                extra={"conversacion_id": conversacion_id},
            )
            self._ejecutor.ejecutar(
                nombre="escalar_a_humano",
                lead_id=lead["id"],
                conversacion_id=conversacion_id,
                entrada={"motivo": "Se alcanzó el límite de turnos de herramientas sin resolver"},
                id_llamada="limite-interno",
            )
            partes_de_texto = [parametros.valor("bot.texto_limite_alcanzado")]

        # Lo que Victoria escribe antes y después de usar una herramienta («Un momento…» / «¡Listo!…») sale como
        # UN solo mensaje: se junta con un renglón en blanco, no pegado («Un momento…¡Listo!»).
        texto_final = "\n\n".join(p.strip() for p in partes_de_texto if p and p.strip())
        if not texto_final:
            # La IA terminó sin escribir nada. Un mensaje vacío no se puede enviar, y callar dejaría al cliente
            # esperando: se pasa la conversación a una persona y se le avisa.
            logger.warning("Victoria terminó sin texto para el cliente -- se escala", extra={"conversacion_id": conversacion_id})
            if not ya_escalo:
                self._ejecutor.ejecutar(
                    nombre="escalar_a_humano",
                    lead_id=lead["id"],
                    conversacion_id=conversacion_id,
                    entrada={"motivo": "La IA no generó ninguna respuesta para el cliente"},
                    id_llamada="sin-texto-interno",
                )
            texto_final = parametros.valor("bot.texto_limite_alcanzado")

        self._guardar_respuesta(conversacion_id, texto_final, ultima_leida=filas[-1] if filas else None)
        return texto_final

    def _guardar_respuesta(self, conversacion_id: int, texto: str, ultima_leida: Optional[dict]) -> None:
        """Guarda la respuesta del bot. Si el cliente escribió OTRO mensaje mientras Victoria redactaba, la
        respuesta se guarda con la hora del último mensaje que sí leyó: así el mensaje nuevo queda después de ella,
        sigue «sin responder» y el siguiente turno lo contesta (si no, parecería ya respondido y se perdería)."""
        creado_en = None
        if ultima_leida is not None and ultima_leida.get("id") is not None:
            llego_otro = any(
                f["rol"] == "cliente" and (f.get("id") or 0) > ultima_leida["id"]
                for f in self._mensajes.obtener_por_conversacion(conversacion_id)
            )
            if llego_otro:
                creado_en = ultima_leida.get("creado_en")
        if creado_en is not None:
            self._mensajes.crear(conversacion_id=conversacion_id, rol="bot", contenido=texto, tipo="texto", wamid=None, creado_en=creado_en)
        else:
            self._mensajes.crear(conversacion_id=conversacion_id, rol="bot", contenido=texto, tipo="texto", wamid=None)

    def _pasó_a_manos_de_una_persona(self, conversacion_id: int) -> bool:
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        return bool(conversacion) and conversacion.get("estado") in ESTADOS_EN_MANOS_DEL_DUENO

    @staticmethod
    def _separar_sin_responder(filas: List[dict]) -> tuple:
        """(lo anterior, mensajes seguidos del cliente al final sin respuesta). Lo «sin responder» es la racha de
        filas del cliente que cierra la conversación; en cuanto hay algo del bot (o del dueño) después, está contestado."""
        corte = len(filas)
        # Los avisos internos del sistema (p. ej. «el dueño confirmó el pago») también esperan respuesta de Victoria.
        while corte > 0 and filas[corte - 1]["rol"] in ROLES_QUE_ESPERAN_RESPUESTA:
            corte -= 1
        return filas[:corte], filas[corte:]

    @staticmethod
    def _construir_historial(anteriores: List[dict], max_historial: int) -> List[MensajeLLM]:
        """Lo que se habló ANTES de los mensajes que se están por responder (esos van aparte, juntos, como el último
        mensaje del cliente)."""
        if max_historial:
            anteriores = anteriores[-max_historial:]
        return [
            MensajeLLM(rol="user" if fila["rol"] in ROLES_QUE_ESPERAN_RESPUESTA else "assistant", texto=VictoriaConversationService._texto_del_historial(fila))
            for fila in anteriores
        ]

    @staticmethod
    def _texto_del_historial(fila: dict) -> str:
        """Un archivo viejo del cliente no se vuelve a mandar a la IA: en su lugar va lo que se entendió de él (la descripción de
        la foto, la transcripción del audio), si ya se guardó."""
        analisis = fila.get("analisis")
        if fila["rol"] == "cliente" and analisis and fila.get("tipo") in ("imagen", "documento", "audio"):
            etiqueta = {"imagen": "imagen del cliente", "documento": "documento del cliente", "audio": "audio del cliente (transcrito)"}[fila["tipo"]]
            leyenda = f" — pie de foto: {fila['contenido']}" if fila.get("tipo") != "audio" and not fila["contenido"].startswith("[") else ""
            return f"[{etiqueta}: {analisis}]{leyenda}"
        return fila["contenido"]

    def _preparar_mensaje_del_cliente(self, conversacion: dict, pendientes: List[dict]) -> Tuple[str, List[AdjuntoLLM]]:
        """Junta lo que el cliente escribió (y mandó) desde la última respuesta en UN mensaje para la IA. Las fotos y PDF del turno se
        bajan de Meta y se le entregan para que los VEA, hasta `bot.max_imagenes_por_mensaje`; lo demás va como texto. Si algo no se
        puede ver (apagado, tope, descarga fallida, formato no soportado) se le dice a Victoria con una nota, nunca se calla: así sabe
        qué pedirle al cliente."""
        entender = parametros.valor("bot.entender_imagenes")
        maximo = parametros.valor("bot.max_imagenes_por_mensaje")
        con_archivo = [f for f in pendientes if f.get("tipo") in ("imagen", "documento") and f.get("media_id")]
        # Si hay más que el tope, se miran las más recientes.
        a_ver = {id(f) for f in con_archivo[-maximo:]} if entender else set()

        lineas: List[str] = []
        adjuntos: List[AdjuntoLLM] = []
        for fila in pendientes:
            if id(fila) in a_ver:
                adjunto, nota = self._bajar_para_ver(conversacion, fila)
                if adjunto is not None:
                    adjuntos.append(adjunto)
                    lineas.append(self._etiqueta_adjunta(fila))
                else:
                    lineas.append(f"{fila['contenido']} {nota}".strip())
            elif fila.get("tipo") == "audio":
                lineas.append(self._texto_de_un_audio(conversacion, fila))
            elif fila.get("tipo") in ("imagen", "documento"):
                motivo = "(foto que no pudiste ver: la función está apagada)" if not entender else "(foto anterior, no se analizó: pasó el tope de fotos por mensaje)"
                lineas.append(f"{fila['contenido']} {motivo}".strip())
            else:
                lineas.append(fila["contenido"])
        return "\n".join(lineas), adjuntos

    def _texto_de_un_audio(self, conversacion: dict, fila: dict) -> str:
        """Lo que dijo el cliente en una nota de voz, ya en texto (se transcribe una sola vez y queda guardado). La API de Claude no
        entiende audio, por eso se usa un servicio de transcripción. Si no se puede, se le dice a Victoria para que le pida al cliente
        que escriba: nunca se finge que se escuchó."""
        if fila.get("analisis"):
            return f"[audio transcrito] {fila['analisis']}"
        no_se_pudo = "[audio que no pudiste escuchar: dile con amabilidad que por ahora no escuchas audios y pídele que escriba su mensaje]"
        if not parametros.valor("bot.entender_audios") or not fila.get("media_id"):
            return no_se_pudo
        try:
            transcriptor = self._transcriptor_fijo
            if transcriptor is None:
                from src.integrations.transcripcion import get_transcriptor  # perezoso: sin clave devuelve None

                transcriptor = get_transcriptor()
            if transcriptor is None:
                return no_se_pudo
            registro = self._canales_fijo
            if registro is None:
                from src.integrations.canales import get_registro_canales

                registro = self._canales_fijo = get_registro_canales()
            maximo = parametros.valor("bot.max_mb_audio") * 1024 * 1024
            datos, mime = registro.para(conversacion["canal"]).descargar_media(fila["media_id"], max_bytes=maximo)
            texto = transcriptor.transcribir(datos, fila.get("media_mime") or mime or "")
        except Exception:
            logger.warning("No se pudo transcribir el audio del cliente", extra={"conversacion_id": conversacion.get("id"), "mensaje_id": fila.get("id")}, exc_info=True)
            return _AUDIO_NO_ENTENDIDO.format(motivo="no se pudo escuchar")
        # Sin voz clara (silencio, ruido) estos servicios a veces inventan frases sueltas: un texto casi vacío no cuenta.
        if len(texto.strip()) < 3:
            return _AUDIO_NO_ENTENDIDO.format(motivo="sin voz clara")
        try:
            if fila.get("id") is not None:
                self._mensajes.guardar_analisis(fila["id"], texto)
        except Exception:
            logger.warning("No se pudo guardar la transcripción", exc_info=True, extra={"mensaje_id": fila.get("id")})
        return f"[audio transcrito] {texto}"

    @staticmethod
    def _etiqueta_adjunta(fila: dict) -> str:
        """El texto que acompaña a un archivo que la IA SÍ recibe (su pie de foto, si lo tiene)."""
        contenido = fila["contenido"]
        if fila.get("tipo") == "documento":
            return f"[documento adjunto: {fila.get('media_nombre') or 'sin nombre'}]" if contenido.startswith("[") else f"[documento adjunto] {contenido}"
        return "[imagen adjunta]" if contenido.startswith("[") else f"[imagen adjunta] {contenido}"

    def _bajar_para_ver(self, conversacion: dict, fila: dict) -> Tuple[Optional[AdjuntoLLM], str]:
        """(adjunto, nota). Si no se puede, adjunto es None y la nota le explica a Victoria por qué."""
        mime = (fila.get("media_mime") or "").split(";")[0].strip().lower()
        es_pdf = fila.get("tipo") == "documento" and mime == _MIME_PDF
        if mime not in _MIMES_DE_IMAGEN and not es_pdf:
            return None, f"(archivo que no puedes abrir: tipo {mime or 'desconocido'}; pídele al cliente una foto o que lo escriba)"
        try:
            registro = self._canales_fijo
            if registro is None:
                from src.integrations.canales import get_registro_canales  # perezoso: evita armar WhatsApp si no hace falta

                registro = self._canales_fijo = get_registro_canales()
            datos, _ = registro.para(conversacion["canal"]).descargar_media(fila["media_id"], max_bytes=_MAXIMO_BYTES_DE_ARCHIVO)
        except Exception:
            logger.warning("No se pudo bajar el archivo del cliente", extra={"conversacion_id": conversacion.get("id"), "mensaje_id": fila.get("id")}, exc_info=True)
            return None, "(archivo que no se pudo abrir: pídele con amabilidad que lo vuelva a enviar o que escriba lo que necesita)"
        return AdjuntoLLM(tipo="documento" if es_pdf else "imagen", mime=mime, datos_base64=base64.b64encode(datos).decode("ascii")), ""

    def _resolver_producto_contexto(self, lead: dict, conversacion: dict) -> Optional[dict]:
        """Producto cuya ficha completa se le muestra a Victoria. Solo cuenta
        si está ACTIVO: pausar un producto debe sacarlo de las conversaciones
        en curso y de los anuncios vinculados, no solo del listado (hueco H6
        del plan de gestión de productos)."""
        if lead.get("producto_sku"):
            producto = self._productos.obtener_por_sku(lead["producto_sku"])
            return producto if self._esta_activo(producto) else None
        if conversacion.get("id_anuncio"):
            producto = self._productos.obtener_por_id_anuncio(conversacion["id_anuncio"])
            if self._esta_activo(producto):
                return producto
        return None

    @staticmethod
    def _esta_activo(producto: Optional[dict]) -> bool:
        return producto is not None and bool(producto.get("activo", True))

    @staticmethod
    def _aviso_producto_no_disponible(lead: dict, producto_contexto: Optional[dict]) -> str:
        """Si el cliente ya había elegido un producto que ahora está pausado,
        Victoria debe saberlo en vez de seguir como si nada."""
        if lead.get("producto_sku") and producto_contexto is None:
            nombre = lead.get("producto_nombre") or lead["producto_sku"]
            return (
                f"AVISO: el producto que el cliente había elegido ({nombre}) ya no está disponible. "
                "Explícaselo con naturalidad y ofrécele los productos disponibles de la lista; "
                "si no hay alternativa, usa escalar_a_humano.\n\n"
            )
        return ""

    def _formatear_contexto_producto(self, producto: Optional[dict]) -> str:
        if producto:
            return formatear_ficha_producto(producto, self._entregas.listar(producto["sku"], solo_activas=True))

        activos = self._productos.listar_activos()
        if not activos:
            return "Todavía no hay productos cargados en el catálogo. Si el cliente pregunta por algo, usa escalar_a_humano."
        lista = "\n".join(
            f"- {p['nombre']} (SKU {p['sku']}): ${p['precio']}" + (" [cierre manual: lo gestiona el dueño]" if es_de_cierre_manual(p) else "")
            for p in activos
        )
        return (
            "Todavía no se identificó un producto específico para esta conversación. "
            "Estos son los productos disponibles -- identifica cuál le interesa al cliente "
            "antes de seguir. Si el cliente pregunta por uno de ellos, usa ver_ficha_producto "
            "para leer su información completa antes de responder:\n" + lista
        )

    def _historial_del_cliente(self, conversacion: dict, lead: dict) -> str:
        """Lo que se habló y compró antes con este contacto (como la ficha de un CRM), para que Victoria no lo trate como a un
        desconocido. Best-effort: si falla, Victoria responde igual sin el historial."""
        try:
            resumen = self._leads.resumen_del_contacto(conversacion["contacto_id"], lead["id"])
            texto = formatear_historial(
                resumen["previos"], resumen["compras"], nombre=lead.get("nombre_cliente") or conversacion.get("contacto_nombre")
            )
        except Exception:
            logger.exception("No se pudo armar el historial del cliente (se responde sin él)")
            return ""
        return f"\n\n{texto}" if texto else ""

    @staticmethod
    def _formatear_contexto_lead(lead: dict, producto: Optional[dict] = None) -> str:
        campos = {
            "Nombre": lead.get("nombre_cliente"),
            "Dirección": lead.get("direccion"),
            "Cantón": lead.get("canton"),
            "Provincia": lead.get("provincia"),
            "Producto": lead.get("producto_nombre"),
            "Método de pago": lead.get("metodo_pago"),
        }
        # La entrega solo se pide si el envío NO va incluido en el precio del producto (ADR-012).
        if producto is not None and not producto.get("envio_incluido", True):
            campos["Entrega"] = lead.get("entrega_nombre")
        conocidos = [f"{etiqueta}: {valor}" for etiqueta, valor in campos.items() if valor]
        faltantes = [etiqueta for etiqueta, valor in campos.items() if not valor]

        partes = []
        if lead.get("metodo_pago") == "transferencia" and lead.get("estado_pago") == "confirmado":
            partes.append("El pago por transferencia YA está CONFIRMADO por el dueño: no le pidas comprobante ni vuelvas a pedirle que pague.")
        if lead.get("datos_confirmados_en"):
            partes.append("El cliente ya confirmó el resumen de sus datos de envío.")
        elif lead.get("datos_confirmacion_pedida_en"):
            partes.append("Ya le enviaste el resumen para confirmar: espera su respuesta.")
        if conocidos:
            partes.append("Ya se sabe: " + "; ".join(conocidos) + ".")
        if faltantes:
            partes.append("Todavía falta: " + ", ".join(faltantes) + ".")
        return "\n".join(partes) if partes else "Todavía no se sabe nada de este cliente."
