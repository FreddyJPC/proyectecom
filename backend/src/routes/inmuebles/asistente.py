"""
El asistente de inmuebles (módulo «Inmuebles», migración 037): contesta las conversaciones con `asistente = 'inmuebles'`.

Usa el MISMO motor que Victoria (lee el bloque de mensajes sin responder, entiende fotos y audios, guarda su respuesta y la
devuelve al worker para enviarla), pero con sus propias instrucciones y herramientas. No crea leads, no cotiza, no toca
Rocketfy: por eso hereda de VictoriaConversationService solo para reutilizar cómo se lee la conversación, y reemplaza el
turno completo.
"""
import logging
from pathlib import Path
from typing import List, Optional

from src.config.parametros import parametros
from src.integrations.llm.contratos import AdjuntoLLM, MensajeLLM
from src.integrations.llm.factory import get_llm_client
from src.routes.whatsapp.conversation_service import VictoriaConversationService, _fecha_legible_ecuador, armar_instrucciones

from .herramientas import HERRAMIENTAS_INMUEBLES, HerramientasInmuebles
from .logica import catalogo_para_el_asistente, ficha_para_el_asistente, visitas_para_el_asistente
from .repository import InmuebleRepository, MaterialInmuebleRepository, VisitaRepository

logger = logging.getLogger(__name__)

_RUTA_PLANTILLA = Path(__file__).with_name("asistente_prompt.txt")


def plantilla_del_asistente() -> str:
    return _RUTA_PLANTILLA.read_text(encoding="utf-8")


def presentacion(nombre: str, dueno: str) -> str:
    nombre = (nombre or "").strip()
    if nombre and nombre.lower() not in ("sin nombre", "ninguno", "-"):
        return (
            f"Te llamas {nombre} y atiendes los mensajes de {dueno} sobre sus propiedades. Si te presentas, di solo tu nombre "
            "(sin cargo)."
        )
    return f"Atiendes los mensajes de {dueno} sobre sus propiedades. No te presentas con un nombre ni con un cargo."


class AsistenteInmueblesService(VictoriaConversationService):
    def __init__(
        self,
        llm_client=None,
        conversacion_repo=None,
        mensaje_repo=None,
        ejecutor: Optional[HerramientasInmuebles] = None,
        inmuebles: Optional[InmuebleRepository] = None,
        material: Optional[MaterialInmuebleRepository] = None,
        visitas: Optional[VisitaRepository] = None,
        max_turnos_herramientas: Optional[int] = None,
        max_mensajes_historial: Optional[int] = None,
        canales=None,
        transcriptor=None,
    ):
        super().__init__(
            llm_client=llm_client,
            conversacion_repo=conversacion_repo,
            mensaje_repo=mensaje_repo,
            max_turnos_herramientas=max_turnos_herramientas,
            max_mensajes_historial=max_mensajes_historial,
            canales=canales,
            transcriptor=transcriptor,
            ejecutor_herramientas=object(),  # no se usa: este asistente tiene sus propias herramientas
        )
        self._inmuebles = inmuebles or InmuebleRepository()
        self._material = material or MaterialInmuebleRepository()
        self._visitas = visitas or VisitaRepository()
        self._herramientas = ejecutor or HerramientasInmuebles(
            inmuebles=self._inmuebles, material=self._material, visitas=self._visitas,
            conversaciones=self._conversaciones, mensajes=self._mensajes, canales=canales,
        )

    # -- contexto ---------------------------------------------------------------------------------------------------------

    def _contexto_inmueble(self, conversacion: dict) -> str:
        """La ficha de la propiedad de la que se habla. Si todavía no se sabe y hay UNA sola disponible, es esa; si hay varias,
        la lista corta para preguntarle al cliente cuál le interesa."""
        inmueble = self._inmuebles.obtener(conversacion["inmueble_id"]) if conversacion.get("inmueble_id") else None
        if inmueble is None:
            activos = self._inmuebles.listar_activos()
            if len(activos) == 1:
                inmueble = activos[0]
                self._conversaciones.fijar_asistente(conversacion["id"], "inmuebles", inmueble["id"])
            else:
                return (
                    "Todavía no se sabe por cuál propiedad escribe. Pregúntale con amabilidad cuál le interesa (por la zona o el "
                    "tipo) y usa su código en las herramientas. Propiedades disponibles:\n" + catalogo_para_el_asistente(activos)
                )
        cantidad = len(self._material.listar(inmueble["id"]))
        return ficha_para_el_asistente(inmueble, cantidad)

    def _contexto_cliente(self, conversacion: dict) -> str:
        nombre = conversacion.get("contacto_nombre") or conversacion.get("nombre_perfil")
        lineas = [f"- Nombre en WhatsApp: {nombre}" if nombre else "- Nombre: no lo sabes todavía"]
        lineas.append("- Pedidos de visita:\n" + visitas_para_el_asistente(self._visitas.de_conversacion(conversacion["id"])))
        return "\n".join(lineas)

    # -- turno ------------------------------------------------------------------------------------------------------------

    def procesar_turno(self, conversacion_id: int, mensaje_cliente: Optional[str] = None) -> str:
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

        dueno = parametros.valor("inmuebles.como_llamar_al_dueno")
        system = armar_instrucciones(
            plantilla_del_asistente(),
            presentacion=presentacion(parametros.valor("inmuebles.nombre_asistente"), dueno),
            dueno=dueno,
            contexto_inmueble=self._contexto_inmueble(conversacion),
            contexto_cliente=self._contexto_cliente(conversacion),
            fecha_actual=_fecha_legible_ecuador(),
        )
        llm = self._llm_fijo or get_llm_client()
        max_turnos = self._max_turnos_fijo if self._max_turnos_fijo is not None else parametros.valor("bot.max_turnos_herramientas")
        max_historial = (
            self._max_historial_fijo if self._max_historial_fijo is not None else parametros.valor("bot.max_mensajes_historial")
        )
        mensajes: List[MensajeLLM] = self._construir_historial(historial_filas, max_historial)
        mensajes.append(MensajeLLM(rol="user", texto=texto_cliente, adjuntos=adjuntos))

        partes: List[str] = []
        paso_al_dueno = False
        for _ in range(max_turnos):
            respuesta = llm.generar_respuesta(system=system, mensajes=mensajes, herramientas=HERRAMIENTAS_INMUEBLES)
            partes.append(respuesta.texto)
            if respuesta.razon_de_parada in ("fin", "limite_alcanzado"):
                break
            # Igual que Victoria: lo escrito antes de usar una herramienta no le llega al cliente (ver _texto_para_el_cliente).
            mensajes.append(MensajeLLM(rol="assistant", texto="", llamadas_herramientas=respuesta.llamadas_herramientas))
            resultados = []
            for llamada in respuesta.llamadas_herramientas:
                resultados.append(self._herramientas.ejecutar(llamada.nombre, conversacion_id, llamada.entrada, llamada.id))
                if llamada.nombre == "pasar_al_dueno":
                    paso_al_dueno = True
            mensajes.append(MensajeLLM(rol="user", resultados_herramientas=resultados))
            if paso_al_dueno:
                despedida = llm.generar_respuesta(system=system, mensajes=mensajes, herramientas=HERRAMIENTAS_INMUEBLES)
                partes.append(despedida.texto)
                break
        else:
            logger.warning("El asistente de inmuebles dio demasiadas vueltas -- pasa al dueño", extra={"conversacion_id": conversacion_id})
            self._herramientas.ejecutar(
                "pasar_al_dueno", conversacion_id, {"motivo": "El asistente se trabó: dio demasiadas vueltas sin resolver"}, "limite-interno"
            )
            partes = [parametros.valor("inmuebles.texto_paso_al_dueno")]

        texto_final = self._texto_para_el_cliente(partes)
        if not texto_final:
            if not paso_al_dueno:
                self._herramientas.ejecutar(
                    "pasar_al_dueno", conversacion_id, {"motivo": "El asistente no supo qué responder"}, "sin-texto-interno"
                )
            texto_final = parametros.valor("inmuebles.texto_paso_al_dueno")
        self._guardar_respuesta(conversacion_id, texto_final, ultima_leida=filas[-1] if filas else None)
        return texto_final
