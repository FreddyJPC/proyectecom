"""
«Por gestionar» (ADR-012): lo que necesita al dueño y cómo se le avisa.

Dos canales con papeles distintos, a propósito:
  - La solicitud guardada en la base es el REGISTRO: no se pierde aunque algo falle.
  - Telegram es el TIMBRE: llega al instante, pero es best-effort (si falla, no se detiene nada).
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.integrations.telegram import get_telegram_notifier
from src.routes.anuncios.servicio import AnuncioServicio
from src.routes.ventas.reglas import acciones_disponibles

from .repository import ResultadoUpsert, SolicitudGestionRepository
from .tipos import ESTADOS, tipo as tipo_de

logger = logging.getLogger(__name__)

LIMITE_DE_LA_LISTA = 100
LARGO_MAXIMO_NOTA = 500


class SolicitudNoEncontradaError(Exception):
    pass


class SolicitudYaAtendidaError(Exception):
    pass


class EstadoInvalidoError(ValueError):
    pass


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if valor else None


@dataclass
class ResultadoSolicitud:
    solicitud: ResultadoUpsert
    traspasa: bool
    etiqueta: str


class GestionService:
    def __init__(self, repo=None, telegram=None, anuncios=None):
        self._repo = repo or SolicitudGestionRepository()
        self._telegram_fijo = telegram
        self._anuncios_fijo = anuncios

    def describir_origen(self, conversacion_id: int) -> str:
        """De dónde viene este cliente, en una línea, para los avisos de Telegram (best-effort: nunca lanza)."""
        try:
            return (self._anuncios_fijo or AnuncioServicio()).describir_origen(conversacion_id)
        except Exception:
            logger.exception("No se pudo describir el origen de la conversación %s", conversacion_id)
            return ""

    @property
    def _telegram(self):
        return self._telegram_fijo or get_telegram_notifier()

    # -- Lo que usa Victoria ------------------------------------------------
    def solicitar(
        self,
        conversacion_id: int,
        lead_id: Optional[int],
        clave_tipo: str,
        detalle: Optional[str],
        telefono: str,
    ) -> ResultadoSolicitud:
        """Registra (o completa) la solicitud pendiente de la conversación y avisa al dueño por Telegram
        la primera vez o cuando la solicitud sube de categoría (p. ej. de «quiere comprar» a «quiere
        pagar»). Seguir hablando del mismo tema no vuelve a molestar."""
        tipo = tipo_de(clave_tipo)
        detalle = (detalle or "").strip()[:LARGO_MAXIMO_NOTA] or None
        resultado = self._repo.solicitar(conversacion_id, lead_id, tipo.clave, detalle)
        if resultado.creada or resultado.cambio_de_tipo:
            etiqueta = tipo_de(resultado.tipo).etiqueta
            origen = self.describir_origen(conversacion_id)
            self._avisar(lambda t: t.notificar_gestion(etiqueta, conversacion_id, telefono, detalle or "", origen=origen))
        return ResultadoSolicitud(solicitud=resultado, traspasa=tipo.traspasa, etiqueta=tipo.etiqueta)

    def avisar_pedido_cerrado(self, datos: Dict[str, Any]) -> None:
        if "origen" not in datos and datos.get("conversacion_id") is not None:
            datos = {**datos, "origen": self.describir_origen(datos["conversacion_id"])}
        self._avisar(lambda t: t.notificar_pedido_cerrado(datos))

    def _avisar(self, enviar) -> None:
        try:
            enviar(self._telegram)
        except Exception:
            logger.exception("No se pudo avisar la gestión por Telegram (la solicitud ya quedó guardada)")

    # -- Lo que usa la app --------------------------------------------------
    def listar(self, estado: str = "pendiente") -> List[Dict[str, Any]]:
        if estado not in ESTADOS:
            raise EstadoInvalidoError(f"El estado debe ser uno de: {', '.join(ESTADOS)}.")
        return [self._a_dto(f) for f in self._repo.listar(estado, LIMITE_DE_LA_LISTA)]

    def pendientes(self) -> int:
        return self._repo.contar_pendientes()

    def atender(self, solicitud_id: int, usuario: Optional[str], nota: Optional[str]) -> Dict[str, Any]:
        nota = (nota or "").strip()[:LARGO_MAXIMO_NOTA] or None
        fila = self._repo.atender(solicitud_id, usuario, nota)
        if fila is None:
            if self._repo.obtener(solicitud_id) is None:
                raise SolicitudNoEncontradaError(f"No existe la solicitud {solicitud_id}.")
            raise SolicitudYaAtendidaError("Esa solicitud ya estaba atendida.")
        return self._a_dto(fila)

    @staticmethod
    def _a_dto(fila: Dict[str, Any]) -> Dict[str, Any]:
        tipo = tipo_de(fila["tipo"])
        total = fila.get("venta_total")
        # Lo que se puede hacer con la venta (cobrar, cancelar…) lo decide el código, no la pantalla.
        acciones = acciones_disponibles(
            {"estado": fila.get("venta_estado"), "cobrada_en": fila.get("venta_cobrada_en"), "proveedor_cierre": fila.get("proveedor_cierre")}
        ) if fila.get("venta_id") is not None else {"puede_cobrar": False, "puede_deshacer_cobro": False, "puede_cancelar": False}
        return {
            "id": fila["id"],
            "conversacion_id": fila["conversacion_id"],
            "tipo": tipo.clave,
            "tipo_etiqueta": tipo.etiqueta,
            "detalle": fila.get("detalle"),
            "estado": fila["estado"],
            "nota_atencion": fila.get("nota_atencion"),
            "atendida_por": fila.get("atendida_por"),
            "creada_en": _iso(fila.get("creada_en")),
            "atendida_en": _iso(fila.get("atendida_en")),
            "telefono": fila.get("telefono"),
            "nombre_cliente": fila.get("nombre_cliente"),
            "direccion": fila.get("direccion"),
            "canton": fila.get("canton"),
            "provincia": fila.get("provincia"),
            "producto": fila.get("producto_nombre"),
            "variante": fila.get("producto_variante"),
            "cantidad": fila.get("cantidad"),
            "metodo_pago": fila.get("metodo_pago"),
            "entrega": fila.get("entrega_nombre"),
            "total": f"{total:.2f}" if total is not None else None,
            "proveedor": fila.get("proveedor_nombre"),
            "tiene_pedido": fila.get("venta_id") is not None,
            "venta_id": fila.get("venta_id"),
            "venta_estado": fila.get("venta_estado"),
            "venta_cobrada_en": _iso(fila.get("venta_cobrada_en")),
            "venta_cobrada_por": fila.get("venta_cobrada_por"),
            "venta_nota_cobro": fila.get("venta_nota_cobro"),
            "venta_cancelada_en": _iso(fila.get("venta_cancelada_en")),
            "venta_cancelada_por": fila.get("venta_cancelada_por"),
            "venta_motivo_cancelacion": fila.get("venta_motivo_cancelacion"),
            **acciones,
        }
