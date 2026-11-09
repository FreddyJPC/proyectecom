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
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.config.parametros import parametros
from src.integrations.llm.contratos import LLMProvider, MensajeLLM
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

    def procesar_turno(self, conversacion_id: int, mensaje_cliente: Optional[str] = None) -> str:
        """Responde lo que el cliente escribió y Victoria todavía no contestó.

        Lee de `mensajes` TODO el bloque de mensajes seguidos del cliente que no tienen respuesta (si escribió
        «Hola», «buenas tardes» y «quiero unos audífonos», los ve juntos y contesta una vez). Si no queda nada sin
        responder (otro turno ya lo contestó, p. ej. tras un reinicio), devuelve "" y no se envía nada.
        `mensaje_cliente` solo sirve de respaldo cuando la conversación aún no tiene mensajes guardados."""
        filas = self._mensajes.obtener_por_conversacion(conversacion_id)
        historial_filas, pendientes = self._separar_sin_responder(filas)
        if pendientes:
            texto_cliente = "\n".join(f["contenido"] for f in pendientes)
        elif not filas and mensaje_cliente:
            texto_cliente = mensaje_cliente
        else:
            return ""

        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
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
        mensajes.append(MensajeLLM(rol="user", texto=texto_cliente))

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
        while corte > 0 and filas[corte - 1]["rol"] == "cliente":
            corte -= 1
        return filas[:corte], filas[corte:]

    @staticmethod
    def _construir_historial(anteriores: List[dict], max_historial: int) -> List[MensajeLLM]:
        """Lo que se habló ANTES de los mensajes que se están por responder (esos van aparte, juntos, como el último
        mensaje del cliente)."""
        if max_historial:
            anteriores = anteriores[-max_historial:]
        return [
            MensajeLLM(rol="user" if fila["rol"] == "cliente" else "assistant", texto=fila["contenido"])
            for fila in anteriores
        ]

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
        if conocidos:
            partes.append("Ya se sabe: " + "; ".join(conocidos) + ".")
        if faltantes:
            partes.append("Todavía falta: " + ", ".join(faltantes) + ".")
        return "\n".join(partes) if partes else "Todavía no se sabe nada de este cliente."
