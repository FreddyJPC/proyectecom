"""
Consulta de stock real en Rocketfy para Victoria, antes de registrar y de
cerrar una venta (Fase A del plan de gestión de productos, hueco H3).

Decisión deliberada: FALLA ABIERTO. Si Rocketfy no responde, o el SKU no sale
en la búsqueda, `stock_de()` devuelve None ("no sé") y la venta sigue: Rocketfy
rechazaría igual el pedido al confirmarlo si de verdad no hay stock, y eso ya
escala a una persona. Bloquear ventas por un fallo de red del proveedor
costaría más que el riesgo que evita. (Lo contrario, "fallar cerrado", es lo
que hace el webhook de WhatsApp con la firma: ahí sí es mejor no procesar.)

Caché corta (5 minutos) para no llamar a Rocketfy en cada mensaje; al cerrar
la venta se pide el dato fresco (`fresco=True`).
"""
import logging
import time
from typing import Callable, Dict, Optional, Tuple

from src.integrations.rocketfy import get_rocketfy_client

logger = logging.getLogger(__name__)

TTL_SEGUNDOS_POR_DEFECTO = 300


class StockChecker:
    def __init__(self, client=None, ttl_segundos: int = TTL_SEGUNDOS_POR_DEFECTO, reloj: Callable[[], float] = time.monotonic):
        self._client = client
        self._ttl = ttl_segundos
        self._reloj = reloj
        self._cache: Dict[str, Tuple[float, int]] = {}

    def _cliente(self):
        # Perezoso: no se arma el cliente HTTP hasta que hace falta.
        if self._client is None:
            self._client = get_rocketfy_client()
        return self._client

    def stock_de(self, sku: str, fresco: bool = False) -> Optional[int]:
        """Unidades disponibles del SKU exacto en Rocketfy, o None si no se
        pudo saber (red, SKU no encontrado, respuesta rara)."""
        clave = sku.strip().upper()
        ahora = self._reloj()

        if not fresco:
            guardado = self._cache.get(clave)
            if guardado is not None and ahora - guardado[0] < self._ttl:
                return guardado[1]

        try:
            contenido = self._cliente().listar_productos(q=sku)
            producto = self._buscar_exacto(contenido.get("data", []), clave)
            if producto is None:
                logger.warning(
                    "Stock: el SKU '%s' no aparece en el catálogo de Rocketfy -- no se puede verificar", sku
                )
                return None
            stock = int(producto.get("stock", 0))
        except Exception:
            logger.warning("Stock: no se pudo consultar Rocketfy para el SKU '%s' -- se sigue sin verificar", sku, exc_info=True)
            return None

        self._cache[clave] = (ahora, stock)
        return stock

    @staticmethod
    def _buscar_exacto(productos: list, clave: str) -> Optional[dict]:
        # "q" busca por nombre/SKU/descripción: hay que filtrar por coincidencia
        # exacta (mismo criterio que el vigilante de stock).
        for producto in productos:
            if str(producto.get("sku", "")).strip().upper() == clave:
                return producto
        return None
