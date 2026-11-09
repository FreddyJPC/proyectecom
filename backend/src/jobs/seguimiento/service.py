"""
Seguimiento automático de leads (docs/PLAN_LEADS_CRM.md §6, pendiente #67): escribirle por iniciativa propia al cliente
interesado que dejó de contestar.

Dos formas, cada una con su interruptor (APAGADOS por defecto) y su texto editable en Parámetros:
- EMPUJÓN: texto libre, dentro de las 24 h del último mensaje del cliente (gratis).
- PLANTILLA: mensaje aprobado por Meta, pasadas las 24 h, solo a clientes de anuncio con la ventana gratuita abierta (en esa
  ventana Meta no cobra los mensajes).

Reglas que no se rompen (las hace cumplir el repositorio y las reglas puras, no la buena voluntad de este código):
- Nunca a un cliente marcado «no contactar», ni a leads perdidos o ganados, ni a una conversación que atiende el dueño.
- Máximo UN empujón y UNA plantilla por contacto en toda su vida (índice único de `seguimientos`).
- Tope diario y horario de Ecuador. Fuera de horario o sin cupo, no se envía nada.
- Si un envío falla, se anota; si fallan varios seguidos se frena (no se insiste contra una plantilla sin aprobar).
- El mensaje queda guardado en la conversación: si el cliente contesta, Victoria sabe qué se le dijo.

Nunca lanza: es una tarea de fondo y un fallo no debe tumbar nada. Un cliente que falla no impide escribirle a los demás.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.config.parametros import parametros
from src.integrations.canales import CanalNoDisponibleError, RegistroCanales, etiqueta_de_cliente, get_registro_canales
from src.integrations.telegram import TelegramNotifier, get_telegram_notifier
from src.integrations.whatsapp.exceptions import WhatsAppBusinessError, WhatsAppRequestError
from src.routes.anuncios.repository import AnuncioRepository
from src.routes.anuncios.ventana import ABIERTA, ventana_gratuita

from .reglas import (
    TIPO_EMPUJON,
    TIPO_PLANTILLA,
    cupo_restante,
    dentro_del_horario,
    es_momento_de_la_plantilla,
    es_momento_del_empujon,
    inicio_del_dia_de_ecuador,
    nombre_de_plantilla_valido,
)
from .repository import SeguimientoRepository

logger = logging.getLogger(__name__)

# Cuántos fallos seguidos de un tipo, en las últimas horas, frenan ese tipo en las corridas siguientes. La plantilla frena con
# uno solo: casi siempre es un problema de configuración (no aprobada, nombre mal) y no se arregla insistiendo.
FALLOS_QUE_FRENAN = {TIPO_EMPUJON: 3, TIPO_PLANTILLA: 1}
HORAS_DEL_FRENO = 3


def _wamid(respuesta: Optional[Dict[str, Any]]) -> Optional[str]:
    mensajes = (respuesta or {}).get("messages") or [{}]
    return mensajes[0].get("id")


class SeguimientoService:
    def __init__(
        self,
        repo: Optional[SeguimientoRepository] = None,
        canales: Optional[RegistroCanales] = None,
        telegram: Optional[TelegramNotifier] = None,
        anuncios: Optional[AnuncioRepository] = None,
    ):
        self._repo = repo or SeguimientoRepository()
        self._canales_fijos = canales
        self._telegram_fijo = telegram
        self._anuncios = anuncios or AnuncioRepository()

    @property
    def _canales(self) -> RegistroCanales:
        return self._canales_fijos or get_registro_canales()

    @property
    def _telegram(self) -> TelegramNotifier:
        return self._telegram_fijo or get_telegram_notifier()

    # ------------------------------------------------------------------ la tarea
    def ejecutar(self, ahora: Optional[datetime] = None) -> Dict[str, Any]:
        """Una corrida: escribe los seguimientos que toquen y devuelve un resumen (para el registro y las pruebas)."""
        resumen: Dict[str, Any] = {"enviados": [], "fallidos": 0, "motivo_de_pausa": None}
        try:
            self._correr(ahora or datetime.now(timezone.utc), resumen)
        except Exception:
            logger.exception("Fallo no controlado en el seguimiento automático")
        return resumen

    def _correr(self, ahora: datetime, resumen: Dict[str, Any]) -> None:
        empujon_activo = parametros.valor("seguimiento.empujon_activo")
        plantilla_activa = parametros.valor("seguimiento.plantilla_activa")
        if not (empujon_activo or plantilla_activa):
            resumen["motivo_de_pausa"] = "apagado"
            return
        if not dentro_del_horario(ahora, parametros.valor("seguimiento.hora_desde"), parametros.valor("seguimiento.hora_hasta")):
            resumen["motivo_de_pausa"] = "fuera_de_horario"
            return
        canales = list(self._canales.con_plantillas())
        if not canales:
            resumen["motivo_de_pausa"] = "sin_canales"
            return
        cupo = cupo_restante(
            parametros.valor("seguimiento.tope_diario"), self._repo.contar_del_dia(inicio_del_dia_de_ecuador(ahora))
        )
        if cupo <= 0:
            resumen["motivo_de_pausa"] = "tope_diario"
            return

        if empujon_activo and cupo > 0:
            cupo = self._enviar_tipo(TIPO_EMPUJON, canales, ahora, cupo, resumen)
        if plantilla_activa and cupo > 0:
            cupo = self._enviar_tipo(TIPO_PLANTILLA, canales, ahora, cupo, resumen)

        if resumen["enviados"]:
            logger.info("Seguimiento automático: %d mensaje(s) enviados, %d fallidos", len(resumen["enviados"]), resumen["fallidos"])
            self._avisar_al_dueno(resumen["enviados"])

    def _enviar_tipo(self, tipo: str, canales: List[str], ahora: datetime, cupo: int, resumen: Dict[str, Any]) -> int:
        """Envía los seguimientos de un tipo mientras haya cupo. Devuelve el cupo que queda."""
        if self._repo.contar_fallos(tipo, ahora - timedelta(hours=HORAS_DEL_FRENO)) >= FALLOS_QUE_FRENAN[tipo]:
            logger.warning("Seguimiento «%s» en pausa: hubo fallos en las últimas %d horas", tipo, HORAS_DEL_FRENO)
            return cupo
        if tipo == TIPO_PLANTILLA:
            nombre = parametros.valor("seguimiento.plantilla_nombre")
            if not nombre_de_plantilla_valido(nombre):
                logger.warning("Seguimiento: el nombre de la plantilla «%s» no es válido (solo minúsculas, números y _)", nombre)
                return cupo
            texto = parametros.valor("seguimiento.texto_plantilla")
        else:
            nombre = None
            texto = parametros.valor("seguimiento.texto_empujon")

        espera = parametros.valor("seguimiento.horas_empujon")
        # Se piden más candidatos de los que caben: la plantilla descarta a quien no tiene la ventana gratuita abierta.
        candidatos = self._repo.candidatos(tipo, canales, ahora, espera, limite=cupo * 3 + 5)
        for candidato in candidatos:
            if cupo <= 0:
                break
            if not self._le_toca(tipo, candidato, ahora, espera):
                continue
            resultado = self._enviar(tipo, candidato, texto, nombre)
            if resultado == "enviado":
                cupo -= 1
                resumen["enviados"].append({**candidato, "tipo": tipo})
            elif resultado == "fallido":
                resumen["fallidos"] += 1
                if tipo == TIPO_PLANTILLA:
                    break  # una plantilla que falla casi siempre es de configuración: no se insiste con los demás
        return cupo

    def _le_toca(self, tipo: str, candidato: Dict[str, Any], ahora: datetime, espera: int) -> bool:
        """El filtro fino que la consulta no hace: el momento exacto y, en la plantilla, la ventana gratuita de anuncio."""
        ultimo = candidato["ultimo_cliente_en"]
        if tipo == TIPO_EMPUJON:
            return es_momento_del_empujon(ultimo, ahora, espera)
        if not es_momento_de_la_plantilla(ultimo, ahora):
            return False
        llegadas = [l["creado_en"] for l in self._anuncios.llegadas_de(candidato["conversacion_id"])]
        mensajes = self._repo.mensajes_de(candidato["conversacion_id"])
        return ventana_gratuita(llegadas, mensajes, ahora)["estado"] == ABIERTA

    def _enviar(self, tipo: str, candidato: Dict[str, Any], texto: str, plantilla: Optional[str]) -> str:
        """Reserva, envía y anota. Devuelve «enviado», «fallido» u «omitido» (ya no corresponde: se le escribió antes o pidió
        que no lo contacten entre la consulta y ahora)."""
        seguimiento_id = self._repo.reservar(candidato["lead_id"], candidato["canal"], tipo, texto, plantilla)
        if seguimiento_id is None:
            return "omitido"
        try:
            canal = self._canales.para(candidato["canal"])
            if tipo == TIPO_EMPUJON:
                respuesta = canal.enviar_texto(candidato["id_externo"], texto)
            else:
                respuesta = canal.enviar_plantilla(candidato["id_externo"], plantilla)
        except (WhatsAppRequestError, WhatsAppBusinessError, CanalNoDisponibleError) as exc:
            self._fallo(seguimiento_id, tipo, candidato, str(exc))
            return "fallido"
        except Exception as exc:  # un fallo raro no debe impedir escribirle a los demás
            logger.exception("Error inesperado enviando el seguimiento %s", seguimiento_id)
            self._fallo(seguimiento_id, tipo, candidato, f"Error inesperado: {exc}")
            return "fallido"
        try:
            self._repo.marcar_enviado(seguimiento_id, candidato["conversacion_id"], texto, _wamid(respuesta))
        except Exception:
            # El mensaje YA salió. La fila queda «reservada» y cuenta: ese cliente no recibe un segundo mensaje.
            logger.exception("El seguimiento %s se envió pero no se pudo anotar en la conversación", seguimiento_id)
        return "enviado"

    def _fallo(self, seguimiento_id: int, tipo: str, candidato: Dict[str, Any], error: str) -> None:
        logger.warning("No se pudo enviar el seguimiento %s (%s) a la conversación %s: %s", seguimiento_id, tipo, candidato["conversacion_id"], error)
        try:
            self._repo.marcar_fallido(seguimiento_id, error)
        except Exception:
            logger.exception("No se pudo anotar el fallo del seguimiento %s", seguimiento_id)
        if tipo == TIPO_PLANTILLA:
            self._telegram.notificar_aviso(
                "⚠️ No se pudo enviar la plantilla de seguimiento",
                f"Meta respondió: {error}\n\nRevisa que la plantilla «{parametros.valor('seguimiento.plantilla_nombre')}» esté "
                "creada y aprobada. El sistema no vuelve a intentarlo durante unas horas.",
            )

    def _avisar_al_dueno(self, enviados: List[Dict[str, Any]]) -> None:
        lineas = []
        for e in enviados:
            nombre = f"{e['nombre']} · " if e.get("nombre") else ""
            tipo = "plantilla" if e["tipo"] == TIPO_PLANTILLA else "empujón"
            lineas.append(f"• {nombre}{etiqueta_de_cliente(e['canal'], e['id_externo'], e.get('telefono'))} ({tipo})")
        self._telegram.notificar_aviso(
            f"📨 Seguimiento automático: se le escribió a {len(enviados)} cliente{'s' if len(enviados) != 1 else ''}",
            "\n".join(lineas) + "\n\nSi contestan, Victoria los atiende. Míralos en la app: Leads.",
        )
