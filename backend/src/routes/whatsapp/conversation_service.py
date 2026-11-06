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
import functools
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from src.config.settings import load_settings
from src.integrations.llm.contratos import LLMProvider, MensajeLLM
from src.integrations.llm.factory import get_llm_client

from .ficha import formatear_ficha_producto
from .repository import ConversacionRepository, LeadRepository, MensajeRepository, ProductoBotRepository
from .tools import HerramientasVictoria, herramientas_de_victoria

logger = logging.getLogger(__name__)

_RUTA_SYSTEM_PROMPT = Path(__file__).resolve().parent / "victoria_system_prompt.txt"
_ZONA_ECUADOR = timezone(timedelta(hours=-5))
_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
_MENSAJE_LIMITE_ALCANZADO = (
    "Disculpa la demora — ya te conecto con un asesor humano que te ayuda enseguida 🙋"
)


@functools.lru_cache(maxsize=1)
def _plantilla_system_prompt() -> str:
    return _RUTA_SYSTEM_PROMPT.read_text(encoding="utf-8")


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
    ):
        settings = load_settings()
        self._llm = llm_client or get_llm_client()
        self._leads = lead_repo or LeadRepository()
        self._conversaciones = conversacion_repo or ConversacionRepository()
        self._mensajes = mensaje_repo or MensajeRepository()
        self._productos = producto_repo or ProductoBotRepository()
        self._ejecutor = ejecutor_herramientas or HerramientasVictoria()
        self._max_turnos = (
            max_turnos_herramientas if max_turnos_herramientas is not None else settings.bot_max_turnos_herramientas
        )
        self._max_historial = (
            max_mensajes_historial if max_mensajes_historial is not None else settings.bot_max_mensajes_historial
        )
        # Fase G2: la herramienta de la foto solo se ofrece si está encendida (BOT_ENVIAR_FOTOS).
        self._herramientas = herramientas_de_victoria(settings.bot_enviar_fotos)

    def procesar_turno(self, conversacion_id: int, mensaje_cliente: str) -> str:
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        lead = self._leads.obtener_o_crear(conversacion_id, telefono=conversacion["telefono"])

        producto_contexto = self._resolver_producto_contexto(lead, conversacion)
        system_prompt = _plantilla_system_prompt().format(
            contexto_producto=self._aviso_producto_no_disponible(lead, producto_contexto)
            + self._formatear_contexto_producto(producto_contexto),
            contexto_lead_actual=self._formatear_contexto_lead(lead),
            fecha_actual=_fecha_legible_ecuador(),
        )

        mensajes: List[MensajeLLM] = self._construir_historial(conversacion_id)
        mensajes.append(MensajeLLM(rol="user", texto=mensaje_cliente))

        texto_final = ""
        ya_escalo = False

        for _ in range(self._max_turnos):
            respuesta = self._llm.generar_respuesta(
                system=system_prompt, mensajes=mensajes, herramientas=self._herramientas
            )
            texto_final += respuesta.texto

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

            mensajes.append(MensajeLLM(rol="user", resultados_herramientas=resultados))

            if ya_escalo:
                # Se permite UNA iteración más para que el LLM redacte la
                # despedida con el resultado que le llegó -- después de
                # esa, se corta pase lo que pase (no es criterio del
                # modelo seguir la conversación tras escalar).
                despedida = self._llm.generar_respuesta(
                    system=system_prompt, mensajes=mensajes, herramientas=self._herramientas
                )
                texto_final += despedida.texto
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
            texto_final = _MENSAJE_LIMITE_ALCANZADO

        self._mensajes.crear(conversacion_id=conversacion_id, rol="bot", contenido=texto_final, tipo="texto", wamid=None)
        return texto_final

    def _construir_historial(self, conversacion_id: int) -> List[MensajeLLM]:
        """Excluye la última fila a propósito: para cuando procesar_turno()
        corre, el mensaje del cliente que se está por responder YA quedó
        guardado en `mensajes` (WebhookService lo guarda antes de encolar
        -- ver services.py) -- incluirlo acá Y agregarlo de nuevo como
        mensaje_cliente lo duplicaría en lo que ve el LLM."""
        filas = self._mensajes.obtener_por_conversacion(conversacion_id)
        anteriores = filas[:-1] if filas else []
        if self._max_historial:
            anteriores = anteriores[-self._max_historial:]
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
            return formatear_ficha_producto(producto)

        activos = self._productos.listar_activos()
        if not activos:
            return "Todavía no hay productos cargados en el catálogo. Si el cliente pregunta por algo, usa escalar_a_humano."
        lista = "\n".join(f"- {p['nombre']} (SKU {p['sku']}): ${p['precio']}" for p in activos)
        return (
            "Todavía no se identificó un producto específico para esta conversación. "
            "Estos son los productos disponibles -- identifica cuál le interesa al cliente "
            "antes de seguir. Si el cliente pregunta por uno de ellos, usa ver_ficha_producto "
            "para leer su información completa antes de responder:\n" + lista
        )

    @staticmethod
    def _formatear_contexto_lead(lead: dict) -> str:
        campos = {
            "Nombre": lead.get("nombre_cliente"),
            "Dirección": lead.get("direccion"),
            "Cantón": lead.get("canton"),
            "Provincia": lead.get("provincia"),
            "Producto": lead.get("producto_nombre"),
            "Método de pago": lead.get("metodo_pago"),
        }
        conocidos = [f"{etiqueta}: {valor}" for etiqueta, valor in campos.items() if valor]
        faltantes = [etiqueta for etiqueta, valor in campos.items() if not valor]

        partes = []
        if conocidos:
            partes.append("Ya se sabe: " + "; ".join(conocidos) + ".")
        if faltantes:
            partes.append("Todavía falta: " + ", ".join(faltantes) + ".")
        return "\n".join(partes) if partes else "Todavía no se sabe nada de este cliente."
