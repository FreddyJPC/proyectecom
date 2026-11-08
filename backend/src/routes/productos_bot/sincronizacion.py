"""
Operación continua de los productos publicados (Fase F del plan de gestión de
productos): cada hora vuelve a leer Rocketfy y mantiene la ficha al día sin que
nadie tenga que vigilarla.

Qué hace, por cada producto de ROCKETFY `activo` o `agotado` (los productos propios no están en
Rocketfy y no se sincronizan):
  1. Refresca costo, precio sugerido, stock, peso e imagen desde Rocketfy.
  2. AUTO-PAUSA por agotado (parámetro «Pausar solo un producto agotado»): si un producto `activo` queda con 0 unidades pasa a
     `agotado` (Victoria deja de ofrecerlo, igual que con una pausa manual), se
     anota en su historial, se avisa por Telegram y queda en Incidencias.
     Reanudar es SIEMPRE manual (al reanudar se vuelve a comprobar el stock).
  3. ALERTA de margen en riesgo (parámetro «Avisar cuando el margen está en riesgo»): si el costo cambió y con el precio actual el
     margen cae bajo el mínimo del dueño, se avisa (Incidencias + Telegram) UNA
     vez, cuando cruza el umbral. NUNCA cambia el precio solo: eso es del dueño.

Reglas de diseño:
- Si Rocketfy no responde, no se hace nada con ese producto (no se pausa por un
  fallo de red) y se sigue con el siguiente.
- La pausa es condicional (`where estado = 'activo'`): si una persona lo pausó
  mientras corría la sincronización, no se pisa.
- Avisar es secundario: un fallo de Telegram o de la alerta no deshace la pausa.
"""
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

from src.config.parametros import parametros
from src.integrations.rocketfy import RocketfyBusinessError, RocketfyRequestError
from src.integrations.telegram import get_telegram_notifier
from src.jobs._locks import acquire_lock, release_lock
from src.jobs.stock_watcher.repository import StockWatcherRepository
from src.routes.ajustes.services import AjustesService
from src.routes.productos.repository import SkuMonitoreadoRepository
from src.routes.ventas.origen import es_de_cierre_manual

from .calculadora import margen_en_riesgo
from .repository import ProductoBotGestionRepository
from .services import ProductosBotService, _dinero

logger = logging.getLogger(__name__)

JOB_NAME = "sync_productos"
ESTADOS_QUE_SE_SINCRONIZAN = ("activo", "agotado")
TIPO_ALERTA_AGOTADO = "producto_agotado"
TIPO_ALERTA_MARGEN = "margen_en_riesgo"
ACCION_AGOTADO = "agotado"


@dataclass
class ResultadoSincronizacion:
    revisados: int = 0
    actualizados: int = 0
    pausados_por_agotado: int = 0
    alertas_de_margen: int = 0
    fallidos: int = 0


class SincronizacionProductosService:
    def __init__(self, productos=None, repo=None, alertas=None, monitoreo=None, ajustes_service=None, telegram=None):
        self._productos = productos or ProductosBotService()
        self._repo = repo or ProductoBotGestionRepository()
        self._alertas = alertas or StockWatcherRepository()
        self._monitoreo = monitoreo or SkuMonitoreadoRepository()
        self._ajustes = ajustes_service or AjustesService()
        self._telegram = telegram

    # ------------------------------------------------------------------
    def ejecutar(self) -> Optional[ResultadoSincronizacion]:
        """Una pasada completa. Con el lock de `job_locks`, dos instancias no se pisan."""
        if not acquire_lock(JOB_NAME):
            logger.info("Sincronización de productos: lock ya tomado por otra instancia, se omite esta corrida")
            return None
        try:
            return self.sincronizar_todos()
        finally:
            release_lock(JOB_NAME)

    def sincronizar_todos(self) -> ResultadoSincronizacion:
        resultado = ResultadoSincronizacion()
        # Los productos propios no están en Rocketfy: su stock lo lleva la propia app (ADR-012).
        filas = [
            f for f in self._repo.listar()
            if f["estado"] in ESTADOS_QUE_SE_SINCRONIZAN and not es_de_cierre_manual(f)
        ]
        if not filas:
            logger.info("Sincronización de productos: no hay productos activos ni agotados")
            return resultado
        for fila in filas:
            resultado.revisados += 1
            try:
                self._sincronizar_uno(fila, resultado)
            except (RocketfyRequestError, RocketfyBusinessError):
                resultado.fallidos += 1
                logger.exception("Sincronización: fallo consultando Rocketfy para '%s', se reintenta en la próxima corrida", fila["sku"])
            except Exception:
                # Un producto con problemas no debe impedir sincronizar los demás.
                resultado.fallidos += 1
                logger.exception("Sincronización: fallo no esperado con '%s'", fila["sku"])
        logger.info(
            "Sincronización de productos: %d revisados, %d actualizados, %d pausados por agotado, %d alertas de margen, %d fallidos",
            resultado.revisados, resultado.actualizados, resultado.pausados_por_agotado,
            resultado.alertas_de_margen, resultado.fallidos,
        )
        return resultado

    # ------------------------------------------------------------------
    def _sincronizar_uno(self, antes: Dict[str, Any], resultado: ResultadoSincronizacion) -> None:
        sku = antes["sku"]
        en_vivo = self._productos.consultar_rocketfy(sku)
        if en_vivo is None:
            # No se pausa solo: puede ser un fallo momentáneo del catálogo. Al reanudar o
            # publicar, la verificación en vivo bloquea si el SKU de verdad ya no existe.
            logger.warning("Sincronización: el SKU '%s' ya no aparece en el catálogo de Rocketfy", sku)
            return

        datos = self._productos._datos_de_rocketfy(en_vivo)
        despues = self._repo.guardar_datos_rocketfy(sku, datos)
        resultado.actualizados += 1

        cambios = {}
        for clave in ("costo_rocketfy", "precio_sugerido_rocketfy"):
            if antes.get(clave) != datos[clave]:
                cambios[clave] = [_dinero(antes.get(clave)), _dinero(datos[clave])]
        if cambios:
            self._repo.registrar_historial(sku, "actualizado_rocketfy", None, cambios)

        # Los dos automatismos se pueden apagar desde Parámetros; la actualización de datos de arriba no.
        if parametros.valor("sync.autopausa_agotado"):
            self._revisar_agotado(antes, despues, resultado)
        if parametros.valor("sync.alerta_margen"):
            self._revisar_margen(antes, despues, resultado)

    # -- agotado ---------------------------------------------------------
    def _revisar_agotado(self, antes: dict, despues: dict, resultado: ResultadoSincronizacion) -> None:
        stock = despues.get("stock_ultimo")
        # `None` = Rocketfy no dijo cuánto hay: no se pausa por no saber.
        if antes["estado"] != "activo" or stock is None or stock > 0:
            return
        pausado = self._repo.pausar_por_agotado(antes["sku"])
        if pausado is None:
            return  # alguien lo pausó o archivó en el medio: se respeta
        resultado.pausados_por_agotado += 1
        logger.warning("AUTO-PAUSA: '%s' sin stock en Rocketfy, pasa a agotado", antes["sku"])
        self._repo.registrar_historial(
            antes["sku"], ACCION_AGOTADO, None,
            {"estado": ["activo", "agotado"], "motivo": "Rocketfy reporta 0 unidades"},
        )
        self._avisar_alerta(antes["sku"], TIPO_ALERTA_AGOTADO, {"stock": stock})
        self._avisar_telegram(
            "🟠 Producto sin stock: se pausó solo",
            f"{antes['nombre']} ({antes['sku']}) tiene 0 unidades en Rocketfy. Victoria ya no lo ofrece. "
            "Cuando vuelva el stock, reanúdalo desde Catálogo → Mis productos.",
        )

    # -- margen ----------------------------------------------------------
    def _revisar_margen(self, antes: dict, despues: dict, resultado: ResultadoSincronizacion) -> None:
        costo_antes, costo_ahora = antes.get("costo_rocketfy"), despues.get("costo_rocketfy")
        if costo_ahora is None or costo_antes == costo_ahora:
            return  # el margen solo cambia aquí si cambió el costo
        ajustes = self._ajustes.obtener_ajustes()
        precio = Decimal(str(despues["precio"]))
        ahora = margen_en_riesgo(precio, Decimal(str(costo_ahora)), ajustes)
        if ahora is None:
            return
        # Se avisa al CRUZAR el umbral, no en cada corrida mientras siga igual.
        antes_en_riesgo = costo_antes is not None and margen_en_riesgo(precio, Decimal(str(costo_antes)), ajustes) is not None
        if antes_en_riesgo:
            return
        ganancia, margen = ahora
        resultado.alertas_de_margen += 1
        detalle = {
            "costoAnterior": _dinero(costo_antes),
            "costoActual": _dinero(costo_ahora),
            "precio": _dinero(precio),
            "margenPct": str(margen),
            "margenMinimoPct": f"{ajustes.margen_minimo_pct:.2f}",
        }
        self._avisar_alerta(antes["sku"], TIPO_ALERTA_MARGEN, detalle)
        perdida = "Con este precio pierdes dinero por unidad. " if ganancia <= 0 else ""
        self._avisar_telegram(
            "🟡 Margen en riesgo",
            f"{antes['nombre']} ({antes['sku']}): el costo en Rocketfy pasó de ${detalle['costoAnterior']} a ${detalle['costoActual']}. "
            f"{perdida}Tu margen con el precio actual (${detalle['precio']}) es {margen} %, bajo tu mínimo de {detalle['margenMinimoPct']} %. "
            "No se cambió el precio: revísalo en Catálogo → Mis productos.",
        )

    # -- avisos ------------------------------------------------------------
    def _avisar_alerta(self, sku: str, tipo: str, detalle: dict) -> None:
        """Deja la alerta en Incidencias. `alertas_stock` exige que el SKU esté
        en Vigilados: se asegura antes. Es secundario: si falla, no deshace nada."""
        try:
            vigilados = {m["sku"] for m in self._monitoreo.listar(solo_activos=False)}
            if sku not in vigilados:
                self._monitoreo.upsert(sku, parametros.valor("stock.umbral_bajo"))
            self._alertas.guardar_alerta(sku, tipo, detalle)
        except Exception:
            logger.exception("Sincronización: no se pudo guardar la alerta '%s' de '%s'", tipo, sku)

    def _avisar_telegram(self, titulo: str, detalle: str) -> None:
        try:
            telegram = self._telegram or get_telegram_notifier()
            telegram.notificar_aviso(titulo, detalle)
        except Exception:
            logger.exception("Sincronización: no se pudo avisar por Telegram")
