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
# Máximo de ids por consulta. La guía del proveedor dice "unos pocos miles",
# pero el servidor REAL responde 400 "El rango solicitado no puede superar los
# 1000 pedidos" (visto en los logs de producción el 2026-11-05: con 5000 todas
# las consultas fallaban y la reconciliación no actualizaba nada).
TAMANO_MAXIMO_RANGO = 1000


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

        for id_start, id_end in self._ventanas(ids):
            try:
                respuesta = self._client.consultar_pedidos_lote(id_start, id_end)
            except (RocketfyRequestError, RocketfyBusinessError):
                logger.exception(
                    "Fallo consultando lote %s-%s, se reintenta en la próxima corrida", id_start, id_end
                )
                continue

            if self._es_error(respuesta):
                # Rocketfy contesta los rechazos de este endpoint con
                # {"code": 400, "status": "error", ...} SIN el campo `ok`, así
                # que el cliente no lo reconoce como error y llega hasta acá.
                logger.error("Rocketfy rechazó el lote %s-%s: %s", id_start, id_end, respuesta)
                continue

            for pedido in self._extraer_pedidos(respuesta):
                self._actualizar_uno(pedido)

    def _ventanas(self, ids: List[int]) -> Iterator[Tuple[int, int]]:
        """Agrupa los ids REALES en ventanas de como máximo
        `tamano_maximo_rango` ids consecutivos (de primero a último de la
        ventana). Antes se partía el rango completo [mínimo, máximo] en
        bloques: con pocos pedidos muy separados entre sí (p. ej. ids 288645 y
        371782) eso eran ~84 consultas, casi todas sobre ids que no son
        nuestros. Así se hace una consulta por cada grupo de pedidos cercanos."""
        ordenados = sorted(set(ids))
        inicio = fin = ordenados[0]
        for id_actual in ordenados[1:]:
            if id_actual - inicio < self._tamano_maximo_rango:
                fin = id_actual
            else:
                yield inicio, fin
                inicio = fin = id_actual
        yield inicio, fin

    @staticmethod
    def _es_error(respuesta) -> bool:
        if not isinstance(respuesta, dict):
            return False
        codigo = respuesta.get("code")
        return respuesta.get("status") == "error" or (isinstance(codigo, int) and codigo >= 400)

    @staticmethod
    def _extraer_pedidos(respuesta) -> List[dict]:
        """Forma REAL de /orders/bulk/getInfo, vista en los logs de producción
        el 2026-11-05 (la guía del proveedor no trae ejemplo):

            {"code": 200, "status": "OK", "error": "", "message": "",
             "orders": {"288645": {"id": 288645, "external_id": ..., "status_id": 3,
                                   "status_record": [...], "tracking_code": None, ...},
                        "288726": {...}}}

        o sea `orders` es un DICCIONARIO indexado por el id del pedido, no una
        lista. Se siguen aceptando listas (en `orders`, `data` o `content`, o
        la respuesta misma) por si el proveedor cambia o por analogía con el
        resto de su API. Si ninguna forma calza se avisa, pero SIN volcar la
        respuesta completa: puede traer datos de clientes."""
        if isinstance(respuesta, list):
            return respuesta
        if isinstance(respuesta, dict):
            for clave in ("orders", "data", "content"):
                valor = respuesta.get(clave)
                if isinstance(valor, list):
                    return valor
                if isinstance(valor, dict):
                    pedidos = []
                    for id_clave, pedido in valor.items():
                        if not isinstance(pedido, dict):
                            continue
                        pedido = dict(pedido)
                        if not pedido.get("id") and str(id_clave).isdigit():
                            pedido["id"] = int(id_clave)
                        pedidos.append(pedido)
                    return pedidos
        logger.warning(
            "Forma de respuesta de bulk/getInfo no reconocida, se ignora este lote (claves: %s)",
            sorted(respuesta.keys()) if isinstance(respuesta, dict) else type(respuesta).__name__,
        )
        return []

    def _actualizar_uno(self, pedido: dict) -> None:
        id_rocketfy = pedido.get("id") or pedido.get("order_id")
        status_id = pedido.get("status_id")
        if not id_rocketfy or status_id is None:
            logger.warning("Registro de reconciliación sin id/status_id reconocible: %s", pedido)
            return
        self._repo.actualizar_status(id_rocketfy, status_id)
