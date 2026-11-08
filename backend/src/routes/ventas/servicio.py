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

from .reglas import acciones_disponibles
from .repository import VentasRepository
from .snapshot import armar_venta

logger = logging.getLogger(__name__)

LARGO_MAXIMO_TEXTO = 500


def _texto(valor: Optional[str]) -> Optional[str]:
    return (valor or "").strip()[:LARGO_MAXIMO_TEXTO] or None


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if valor else None


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

    # -- Lo que hace el dueño después de cerrar (ver `reglas.py`) -------------------------------
    def cobrar(self, venta_id: int, usuario: Optional[str], nota: Optional[str]) -> Dict[str, Any]:
        return self._a_dto(self._repo.cobrar(venta_id, usuario, _texto(nota)))

    def deshacer_cobro(self, venta_id: int) -> Dict[str, Any]:
        return self._a_dto(self._repo.deshacer_cobro(venta_id))

    def cancelar(self, venta_id: int, usuario: Optional[str], motivo: Optional[str]) -> Dict[str, Any]:
        return self._a_dto(self._repo.cancelar(venta_id, usuario, _texto(motivo)))

    @staticmethod
    def _a_dto(venta: Dict[str, Any]) -> Dict[str, Any]:
        total = venta.get("total")
        return {
            "id": venta["id"],
            "estado": venta["estado"],
            "total": f"{total:.2f}" if total is not None else None,
            "cobrada": venta.get("cobrada_en") is not None,
            "cobrada_en": _iso(venta.get("cobrada_en")),
            "cobrada_por": venta.get("cobrada_por"),
            "nota_cobro": venta.get("nota_cobro"),
            "cancelada_en": _iso(venta.get("cancelada_en")),
            "cancelada_por": venta.get("cancelada_por"),
            "motivo_cancelacion": venta.get("motivo_cancelacion"),
            "stock_devuelto": venta.get("stock_devuelto", 0),
            "producto_sigue_agotado": bool(venta.get("producto_sigue_agotado", False)),
            **acciones_disponibles(venta),
        }
