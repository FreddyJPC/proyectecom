"""
Vigila stock y precio de los SKUs pautados (requerimientos 4 y 7).

Alcance de Fase 1: detecta y loguea (stock bajo el umbral / cambio de
precio). Pausar campañas en Meta/TikTok automáticamente queda FUERA de
alcance — es una automatización futura sobre este mismo evento. Ver
PROGRESS.md, sección de pendientes transversales: falta además definir un
canal de alerta que alguien realmente vea (hoy solo va al log).
"""
import logging
from decimal import Decimal
from typing import Optional

from src.integrations.rocketfy import RocketfyBusinessError, RocketfyClient, RocketfyRequestError

from .repository import StockWatcherRepository

logger = logging.getLogger(__name__)

JOB_NAME = "stock_watcher"


class StockWatcherService:
    def __init__(self, client: RocketfyClient, repo: Optional[StockWatcherRepository] = None):
        self._client = client
        self._repo = repo or StockWatcherRepository()

    def ejecutar(self) -> None:
        if not self._repo.acquire_lock(JOB_NAME):
            logger.info("Stock watcher: lock ya tomado por otra instancia, se omite esta corrida")
            return
        try:
            self._revisar_todos()
        finally:
            self._repo.release_lock(JOB_NAME)

    def _revisar_todos(self) -> None:
        activos = self._repo.listar_activos()
        if not activos:
            logger.info("Stock watcher: no hay SKUs monitoreados")
            return
        for item in activos:
            try:
                self._revisar_uno(item["sku"], item["umbral_stock_minimo"])
            except (RocketfyRequestError, RocketfyBusinessError):
                logger.exception("Fallo consultando SKU=%s, se reintenta en la próxima corrida", item["sku"])

    def _revisar_uno(self, sku: str, umbral: int) -> None:
        contenido = self._client.listar_productos(q=sku)
        producto = self._buscar_coincidencia_exacta(contenido.get("data", []), sku)
        if producto is None:
            logger.warning("SKU monitoreado '%s' ya no aparece en el catálogo de Rocketfy", sku)
            return

        stock_actual = int(producto.get("stock", 0))
        precio_actual = Decimal(str(producto.get("price", "0")))
        anterior = self._repo.obtener_ultimo_snapshot(sku)

        if stock_actual <= umbral:
            logger.warning(
                "STOCK BAJO: sku=%s stock=%s umbral=%s — considerar pausar campañas",
                sku, stock_actual, umbral,
            )
            self._repo.guardar_alerta(sku, "stock_bajo", {"stock": stock_actual, "umbral": umbral})

        if anterior is not None and Decimal(str(anterior["price"])) != precio_actual:
            logger.warning(
                "CAMBIO DE PRECIO: sku=%s precio_anterior=%s precio_actual=%s",
                sku, anterior["price"], precio_actual,
            )
            self._repo.guardar_alerta(
                sku,
                "cambio_precio",
                {"precioAnterior": str(anterior["price"]), "precioActual": str(precio_actual)},
            )

        self._repo.guardar_snapshot(sku, stock_actual, precio_actual)

    @staticmethod
    def _buscar_coincidencia_exacta(productos: list, sku: str) -> Optional[dict]:
        # Igual criterio que el ejemplo del proveedor (Anexo C): "q" busca
        # por nombre/SKU/descripción, hay que filtrar por coincidencia exacta.
        objetivo = sku.strip().upper()
        for producto in productos:
            if str(producto.get("sku", "")).strip().upper() == objetivo:
                return producto
        return None
