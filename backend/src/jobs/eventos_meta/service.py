"""
Aviso de ventas a Meta (ADR-016, docs/PLAN_META_ADS.md, pendiente #68): le dice a Meta qué clics de anuncio terminaron en una compra.

Por qué es un trabajo aparte y no parte de «cerrar la venta»: si Meta se cae o tarda, la venta no se puede ver afectada. Cada pasada:
  1. Pasa a «dudoso» lo que quedó a medias (no se sabe si Meta lo recibió; NO se reenvía).
  2. Anota como evento las ventas de anuncio ya confirmadas que aún no tienen uno (esperando unos minutos por si se cancela).
  3. Envía los pendientes, de a pocos. Antes de cada envío vuelve a mirar la venta: si se canceló o se deshizo el cobro, no se avisa.

Reglas que no se rompen: apagado de fábrica (`meta.activo`); sin las tres variables del servidor no envía nada; un resultado dudoso (timeout,
error de Meta) nunca se reintenta a ciegas porque Meta no deduplica; nunca lanza (una tarea de fondo no debe tumbar nada); jamás escribe el token.
"""
import logging
from typing import Any, Dict, Optional

from src.config.parametros import parametros
from src.integrations.meta import MetaConversionesClient, MetaRechazoError, MetaRespuestaDudosaError, get_meta_client
from src.integrations.meta.factory import faltantes
from src.integrations.telegram import TelegramNotifier, get_telegram_notifier

from .reglas import minutos_para_reintentar, venta_confirmada
from .repository import EventosMetaRepository

logger = logging.getLogger(__name__)

_POR_PASADA = 20


class EventosMetaService:
    def __init__(
        self,
        repo: Optional[EventosMetaRepository] = None,
        cliente: Optional[MetaConversionesClient] = None,
        telegram: Optional[TelegramNotifier] = None,
    ):
        self._repo = repo or EventosMetaRepository()
        self._cliente = cliente
        self._telegram = telegram or get_telegram_notifier()
        self._advertido = False

    def ejecutar(self) -> int:
        """Una pasada. Devuelve cuántos eventos aceptó Meta."""
        if not parametros.valor("meta.activo"):
            return 0
        cliente = self._cliente
        if cliente is None:
            cliente, ausentes = get_meta_client()
            if cliente is None:
                if not self._advertido:
                    logger.warning("Aviso de ventas a Meta encendido pero faltan variables del servidor: %s", ", ".join(ausentes))
                    self._advertido = True
                return 0

        colgados = self._repo.recuperar_colgados()
        if colgados:
            self._telegram.notificar_aviso(
                "⚠️ Aviso de ventas a Meta: envío dudoso",
                f"{colgados} evento(s) quedaron a medias y no se sabe si Meta los recibió. No se reenvían solos para no duplicar la compra.",
            )

        self._repo.detectar(parametros.valor("meta.minutos_espera"), parametros.valor("meta.dias_maximos"))

        aceptados = 0
        problemas = []
        maximo = parametros.valor("meta.maximo_intentos")
        for evento in self._repo.reclamar(_POR_PASADA):
            try:
                resultado = self._enviar(cliente, evento, maximo)
            except Exception:
                # Un evento que falla de forma inesperada no impide los demás. Ya estaba reservado: queda dudoso, no se reenvía.
                logger.exception("Fallo inesperado enviando el evento %s a Meta", evento.get("id"))
                self._repo.marcar_dudoso(evento["id"], "Fallo inesperado al enviar; no se sabe si Meta lo recibió")
                resultado = "dudoso"
            if resultado == "enviado":
                aceptados += 1
            elif resultado in ("dudoso", "fallido"):
                problemas.append((evento["venta_id"], resultado))
        if problemas:
            resumen = ", ".join(f"venta {venta} ({estado})" for venta, estado in problemas)
            self._telegram.notificar_aviso(
                "⚠️ Aviso de ventas a Meta: hay eventos con problema",
                f"{resumen}. Revisa la pantalla de Anuncios. Los dudosos no se reenvían solos: podrían duplicar la compra.",
            )
        return aceptados

    def _enviar(self, cliente: MetaConversionesClient, evento: Dict[str, Any], maximo_intentos: int) -> str:
        if not venta_confirmada({"estado": evento["venta_estado"], "id_pedido_rocketfy": evento["id_pedido_rocketfy"], "cobrada_en": evento["cobrada_en"]}):
            self._repo.marcar_descartado(evento["id"], "La venta se canceló o se deshizo el cobro antes de avisar a Meta")
            return "descartado"
        try:
            respuesta = cliente.enviar_compra(evento["ctwa_clid"], evento["valor"], evento["moneda"], evento["ocurrido_en"])
        except MetaRespuestaDudosaError as exc:
            self._repo.marcar_dudoso(evento["id"], str(exc))
            return "dudoso"
        except MetaRechazoError as exc:
            if evento["intentos"] >= maximo_intentos:
                self._repo.marcar_fallido(evento["id"], str(exc))
                return "fallido"
            self._repo.reprogramar(evento["id"], str(exc), minutos_para_reintentar(evento["intentos"]))
            return "reprogramado"
        self._repo.marcar_enviado(evento["id"], respuesta)
        return "enviado"
