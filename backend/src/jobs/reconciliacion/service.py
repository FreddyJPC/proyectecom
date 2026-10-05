"""
Reconciliación periódica: backstop del webhook (guía sección 6.4 del doc
del proveedor: "captura cualquier evento que el webhook no haya
entregado"). Corre cada 30-60 min, con lock para no solaparse entre
instancias.

Nota deliberada: este job SOLO sincroniza pedidos.status_id_rocketfy — no
dispara notificaciones. El webhook es el notificador en tiempo real; la
reconciliación es la red de seguridad de datos, no de mensajería (evitar
duplicar avisos al cliente sin la certeza de idempotencia que sí tiene el
webhook vía event_date). Ver PROGRESS.md si se quiere extender esto.
"""
import logging
from typing import Iterator, List, Optional, Tuple

from src.integrations.rocketfy import RocketfyBusinessError, RocketfyClient, RocketfyRequestError

from .repository import ReconciliacionRepository

logger = logging.getLogger(__name__)

JOB_NAME = "reconciliacion_pedidos"
TAMANO_MAXIMO_RANGO = 5000  # el proveedor advierte no pedir rangos de millones de ids


class ReconciliacionService:
    def __init__(
        self,
        client: RocketfyClient,
        repo: Optional[ReconciliacionRepository] = None,
        tamano_maximo_rango: int = TAMANO_MAXIMO_RANGO,
    ):
        self._client = client
        self._repo = repo or ReconciliacionRepository()
        self._tamano_maximo_rango = tamano_maximo_rango

    def ejecutar(self) -> None:
        if not self._repo.acquire_lock(JOB_NAME):
            logger.info("Reconciliación: lock ya tomado por otra instancia, se omite esta corrida")
            return
        try:
            self._reconciliar()
        finally:
            self._repo.release_lock(JOB_NAME)

    def _reconciliar(self) -> None:
        ids = self._repo.obtener_ids_en_curso()
        if not ids:
            logger.info("Reconciliación: no hay pedidos en curso")
            return

        for id_start, id_end in self._chunks(ids):
            try:
                respuesta = self._client.consultar_pedidos_lote(id_start, id_end)
            except (RocketfyRequestError, RocketfyBusinessError):
                logger.exception(
                    "Fallo consultando lote %s-%s, se reintenta en la próxima corrida", id_start, id_end
                )
                continue

            for pedido in self._extraer_pedidos(respuesta):
                self._actualizar_uno(pedido)

    def _chunks(self, ids: List[int]) -> Iterator[Tuple[int, int]]:
        id_min, id_max = ids[0], ids[-1]
        inicio = id_min
        while inicio <= id_max:
            fin = min(inicio + self._tamano_maximo_rango - 1, id_max)
            yield inicio, fin
            inicio = fin + 1

    @staticmethod
    def _extraer_pedidos(respuesta) -> List[dict]:
        """La forma exacta de /orders/bulk/getInfo no está confirmada por
        el proveedor (PROGRESS.md, dudas al proveedor). Se intentan las
        claves más probables por analogía con el resto de la API; si
        ninguna calza, se loguea la respuesta cruda para poder ajustar esto
        con un caso real en cuanto haya pedidos en curso."""
        if isinstance(respuesta, list):
            return respuesta
        if isinstance(respuesta, dict):
            for clave in ("orders", "data", "content"):
                valor = respuesta.get(clave)
                if isinstance(valor, list):
                    return valor
        logger.warning("Forma de respuesta de bulk/getInfo no reconocida, se ignora este lote: %s", respuesta)
        return []

    def _actualizar_uno(self, pedido: dict) -> None:
        id_rocketfy = pedido.get("id") or pedido.get("order_id")
        status_id = pedido.get("status_id")
        if not id_rocketfy or status_id is None:
            logger.warning("Registro de reconciliación sin id/status_id reconocible: %s", pedido)
            return
        self._repo.actualizar_status(id_rocketfy, status_id)
