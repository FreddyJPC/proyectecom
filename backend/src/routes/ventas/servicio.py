"""
Registro de ventas (ADR-012): el paso que une «se cerró una venta» con «queda guardada con sus números».

Dos entradas, una por cada forma de cerrar:
  - `registrar_venta_rocketfy`: el pedido YA se creó en Rocketfy. Guardar la foto de la venta es un extra
    para los reportes: si falla, se registra el error y nada se deshace (el pedido real manda).
  - `cerrar_manual`: producto propio. Aquí guardar la venta ES el cierre, así que si falla, falla el cierre
    (y la conversación se pasa a una persona).
"""
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from src.routes.ajustes.services import AjustesService

from .repository import VentasRepository
from .snapshot import armar_venta

logger = logging.getLogger(__name__)


class VentasService:
    def __init__(self, repo=None, ajustes_service=None):
        self._repo = repo or VentasRepository()
        self._ajustes = ajustes_service or AjustesService()

    def _envio_general(self) -> Decimal:
        try:
            return self._ajustes.obtener_ajustes().envio_estimado
        except Exception:
            logger.exception("No se pudo leer el envío estimado general; se usa 0 en la foto de la venta")
            return Decimal("0.00")

    def registrar_venta_rocketfy(
        self, lead: Dict[str, Any], producto: Dict[str, Any], conversacion: Optional[Dict[str, Any]], entrega: Optional[Dict[str, Any]]
    ) -> None:
        try:
            venta, lineas = armar_venta(lead, producto, conversacion, entrega, "despachada", self._envio_general())
            self._repo.registrar(venta, lineas)
        except Exception:
            logger.exception(
                "No se pudo guardar la venta del lead %s en `ventas` (el pedido de Rocketfy YA se creó; solo falta el registro)",
                lead.get("id"),
            )

    def cerrar_manual(
        self,
        lead: Dict[str, Any],
        producto: Dict[str, Any],
        conversacion: Optional[Dict[str, Any]],
        entrega: Optional[Dict[str, Any]],
        controla_stock: bool,
        detalle_solicitud: str,
    ) -> Dict[str, Any]:
        venta, lineas = armar_venta(lead, producto, conversacion, entrega, "por_gestionar", self._envio_general())
        return self._repo.cerrar_manual(
            venta, lineas, producto["sku"], int(lead.get("cantidad") or 1), controla_stock, detalle_solicitud
        )
