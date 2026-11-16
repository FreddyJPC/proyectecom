"""
Trabajo de anuncios de Meta (ADR-017, plan v2.0 §6.2–6.4). Cada pasada (si «Leer mis anuncios de Meta» está encendido):
  1. Lee de la cuenta publicitaria los anuncios y el gasto de los últimos días, y guarda una copia.
  2. Evalúa las alertas (R1–R9) y avisa por Telegram las NUEVAS (una vez por regla, objeto y día).
  3. Solo si «Pausar solo un anuncio que vende algo que ya no hay» está encendido: pausa en Meta los anuncios de R1/R2 (hechos, no
     rendimiento), como mucho 10 por día, y nunca dos veces el mismo anuncio el mismo día. Nunca reactiva ni toca presupuestos.
  4. Resumen diario por Telegram (si está encendido), una vez al día desde las 8 de la mañana.
Nunca lanza: una tarea de fondo no debe tumbar nada. Jamás escribe el token.
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from src.config.parametros import parametros
from src.integrations.meta import MetaError, MetaRechazoError, MetaRespuestaDudosaError
from src.integrations.meta import factory as meta_factory
from src.integrations.telegram import get_telegram_notifier
from src.routes.precios.repository import PreciosRepository, vigente

from .reglas import Alerta, Umbrales, alerta_de_regateo, evaluar
from .repository import MetaAnunciosRepository

logger = logging.getLogger(__name__)

ZONA = ZoneInfo("America/Guayaquil")
MAXIMO_PAUSAS_DIA = 10
HORA_RESUMEN = 8


def hoy_ecuador(ahora: Optional[datetime] = None) -> date:
    return (ahora or datetime.now(ZONA)).astimezone(ZONA).date()


class MetaAnunciosService:
    def __init__(self, repo: Optional[MetaAnunciosRepository] = None, cliente=None, telegram=None, precios=None, reloj=None):
        self._repo = repo or MetaAnunciosRepository()
        self._cliente = cliente
        self._telegram = telegram or get_telegram_notifier()
        self._precios = precios or PreciosRepository()
        self._reloj = reloj or (lambda: datetime.now(ZONA))
        self._advertido = False

    def _cliente_marketing(self):
        if self._cliente is not None:
            return self._cliente
        cliente, ausentes = meta_factory.get_marketing_client()
        if cliente is None and not self._advertido:
            logger.warning("Lectura de anuncios de Meta encendida pero falta: %s", ", ".join(ausentes))
            self._advertido = True
        return cliente

    # ------------------------------------------------------------------ pasada
    def ejecutar(self) -> Dict[str, Any]:
        if not parametros.valor("meta.anuncios_activo"):
            return {"estado": "apagado"}
        cliente = self._cliente_marketing()
        if cliente is None:
            return {"estado": "sin_configurar"}
        ahora = self._reloj()
        hoy = hoy_ecuador(ahora)
        try:
            leidos = self._repo.guardar_anuncios(cliente.listar_anuncios())
            dias = int(parametros.valor("meta.dias_metricas"))
            self._repo.guardar_metricas(cliente.metricas_diarias(hoy - timedelta(days=dias - 1), hoy))
        except MetaError as exc:
            logger.warning("No se pudieron leer los anuncios de Meta: %s", exc)
            if self._repo.registrar_alerta("lectura", "meta", str(exc)[:500], None, hoy):
                self._telegram.notificar_aviso("⚠️ No se pudieron leer tus anuncios de Meta", f"{exc}. Revisa los permisos de la app y la cuenta publicitaria.")
            return {"estado": "error", "motivo": str(exc)}
        except Exception:
            logger.exception("Fallo inesperado leyendo los anuncios de Meta")
            return {"estado": "error"}

        alertas: List[Alerta] = []
        try:
            alertas = self.alertas(hoy)
        except Exception:
            logger.exception("No se pudieron evaluar las alertas de anuncios")
        nuevas = []
        if parametros.valor("meta.alertas_activas"):
            nuevas = [a for a in alertas if self._repo.registrar_alerta(a.regla, a.objeto, a.mensaje, a.id_anuncio, hoy)]
        pausados = self._pausar_automatico(alertas, cliente, hoy) if parametros.valor("meta.pausa_automatica") else []
        if nuevas or pausados:
            lineas = [f"• {a.mensaje}" for a in nuevas] + [f"⏸️ {p}" for p in pausados]
            self._telegram.notificar_aviso("📣 Anuncios: revisa esto", "\n".join(lineas[:20]))
        self._resumen_diario(ahora, hoy)
        return {"estado": "ok", "anuncios": leidos, "alertas": len(nuevas), "pausados": len(pausados)}

    # ------------------------------------------------------------------ alertas
    def alertas(self, hoy: date) -> List[Alerta]:
        anuncios = self._repo.anuncios_con_vinculo()
        ids_ofertas = {a["oferta_id"] for a in anuncios if a.get("oferta_id")}
        ofertas = {}
        ahora = datetime.now(ZONA)
        for oferta in self._precios.ofertas(ids_ofertas, incluir_archivadas=True) if ids_ofertas else []:
            motivo = None
            if not vigente(oferta, ahora):
                motivo = "ya terminó o está pausada"
            elif oferta.get("cupo") is not None and self._precios.ventas_de_oferta(oferta["id"]) >= int(oferta["cupo"]):
                motivo = "ya agotó su cupo"
            ofertas[oferta["id"]] = {
                "nombre": oferta["nombre"], "vendible": motivo is None, "motivo": motivo,
                "skus": [i["producto_sku"] for i in oferta.get("items") or []],
            }
        skus = [a["producto_sku"] for a in anuncios if a.get("producto_sku")] + [s for o in ofertas.values() for s in o["skus"]]
        productos = self._repo.productos(skus)
        desde = hoy - timedelta(days=int(parametros.valor("meta.dias_alertas")) - 1)
        umbrales = Umbrales(
            stock_bajo=int(parametros.valor("stock.umbral_bajo")),
            gasto_sin_venta=Decimal(int(parametros.valor("meta.alerta_gasto_sin_venta"))),
            costo_conversacion=(Decimal(int(parametros.valor("meta.alerta_costo_conversacion"))) / 100),
            minimo_conversaciones=int(parametros.valor("meta.alerta_minimo_conversaciones")),
        )
        resultado = evaluar(
            anuncios, productos, ofertas, self._repo.metricas_por_anuncio(desde), self._repo.ventas_por_anuncio(desde), umbrales
        )
        resultado += alerta_de_regateo(self._repo.regateo_por_producto(hoy - timedelta(days=6)), int(parametros.valor("precios.alerta_regateo_pct")))
        return resultado

    # ------------------------------------------------------------------ pausas
    def _pausar_automatico(self, alertas: List[Alerta], cliente, hoy: date) -> List[str]:
        hechas = self._repo.pausas_de_hoy(hoy)
        ya = {p["id_anuncio"] for p in hechas if p["resultado"] in ("hecho", "dudoso")}
        cupo = MAXIMO_PAUSAS_DIA - len(hechas)
        salida = []
        for alerta in alertas:
            if not alerta.pausar or not alerta.id_anuncio or alerta.id_anuncio in ya or cupo <= 0:
                continue
            ya.add(alerta.id_anuncio)
            cupo -= 1
            salida.append(self._pausar(cliente, alerta.id_anuncio, alerta.regla, alerta.mensaje, None))
        return salida

    def pausar_manual(self, id_anuncio: str, usuario: Optional[str]) -> Dict[str, Any]:
        """El dueño pide pausar un anuncio desde el panel."""
        cliente = self._cliente_marketing()
        if cliente is None:
            return {"resultado": "sin_configurar", "mensaje": "Falta configurar la conexión con Meta (permisos y cuenta publicitaria)."}
        texto = self._pausar(cliente, id_anuncio, "manual", "Pausado desde el panel", usuario)
        return {"resultado": "ok", "mensaje": texto}

    def _pausar(self, cliente, id_anuncio: str, regla: str, motivo: str, usuario: Optional[str]) -> str:
        try:
            cliente.pausar_anuncio(id_anuncio)
        except MetaRespuestaDudosaError as exc:
            self._repo.registrar_accion(id_anuncio, regla, motivo, "dudoso", str(exc), usuario)
            return f"No se sabe si Meta pausó el anuncio {id_anuncio}: revísalo en el Administrador de anuncios."
        except MetaRechazoError as exc:
            self._repo.registrar_accion(id_anuncio, regla, motivo, "fallido", str(exc), usuario)
            return f"Meta no pausó el anuncio {id_anuncio}: {exc}"
        self._repo.registrar_accion(id_anuncio, regla, motivo, "hecho", None, usuario)
        logger.info("Anuncio %s pausado (%s)", id_anuncio, regla)
        return f"Se pausó el anuncio {id_anuncio}. Para reactivarlo, hazlo tú en el Administrador de anuncios."

    # ------------------------------------------------------------------ resumen
    def _resumen_diario(self, ahora: datetime, hoy: date) -> None:
        if not parametros.valor("meta.resumen_diario") or ahora.astimezone(ZONA).hour < HORA_RESUMEN:
            return
        ayer = hoy - timedelta(days=1)
        try:
            datos = self._repo.resumen_del_dia(ayer)
            gasto, ventas = Decimal(str(datos["gasto"])), int(datos["ventas"])
            partes = [
                f"Gasto: ${gasto:.2f}", f"Conversaciones (Meta): {int(datos['conversaciones'])}",
                f"Ventas de anuncios: {ventas} (${Decimal(str(datos['ingreso'])):.2f})",
            ]
            if ventas:
                partes.append(f"Costo por venta: ${(gasto / ventas):.2f}")
            if datos.get("ganancia") is not None:
                partes.append(f"Ganancia después del gasto: ${(Decimal(str(datos['ganancia'])) - gasto):.2f}")
            mensaje = " · ".join(partes)
            if self._repo.registrar_alerta("resumen", ayer.isoformat(), mensaje, None, hoy):
                self._telegram.notificar_aviso(f"📊 Resumen de anuncios del {ayer:%d/%m}", mensaje)
        except Exception:
            logger.exception("No se pudo enviar el resumen diario de anuncios")
