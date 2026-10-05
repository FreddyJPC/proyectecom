"""
Orquesta crear + confirmar un pedido en Rocketfy con idempotencia real.

Estados de pedidos.estado_local usados aquí:
  pendiente_creacion -> intento en curso / resultado desconocido (ambiguo)
  error              -> /orders/create falló con respuesta clara (nada se
                        creó en Rocketfy, seguro reintentar)
  incompleto         -> se creó pero products_stock no trae todas las líneas
  creado             -> creado en Rocketfy, aún no confirmado
  confirmado         -> /orders/confirm exitoso

Ver PROGRESS.md sección "Plan de Desarrollo — Etapa 3" y el doc del
proveedor, secciones 4 y 5, para la lógica de negocio que esto traduce.
"""
import json
import logging
from dataclasses import asdict
from decimal import Decimal
from typing import Optional

from src.catalogs.ecuador_locations import EcuadorLocationsCatalog, get_catalog
from src.integrations.rocketfy import RECAUDO_MINIMO_CONTRAENTREGA, RocketfyBusinessError, RocketfyClient

from .dto import (
    CrearPedidoInputDTO,
    LineaPedidoDTO,
    ModificarPedidoInputDTO,
    PedidoDetalleDTO,
    PedidoDTO,
    PedidoResumenDTO,
)
from .exceptions import (
    PedidoEnEstadoAmbiguoError,
    PedidoIncompletoError,
    PedidoNoEncontradoError,
    PedidoSinIdRocketfyError,
    RecaudoMinimoNoAlcanzadoError,
    UbicacionNoResueltaError,
)
from .repository import PedidoRepository

_MAPEO_CAMPOS_MODIFICACION_ROCKETFY = {
    "nombre_cliente": "name",
    "email": "email",
    "telefono": "phone",
    "direccion": "address",
    "direccion_2": "address_2",
    "canton": "city",
    "provincia": "province",
    "codigo_postal": "zip",
}

logger = logging.getLogger(__name__)


class PedidoService:
    def __init__(
        self,
        client: RocketfyClient,
        catalogo: Optional[EcuadorLocationsCatalog] = None,
        repo: Optional[PedidoRepository] = None,
    ):
        self._client = client
        self._catalogo = catalogo or get_catalog()
        self._repo = repo or PedidoRepository()

    def crear_y_confirmar(self, dto: CrearPedidoInputDTO) -> PedidoDTO:
        existente = self._repo.obtener(dto.id_local)

        if existente and existente["estado_local"] == "confirmado":
            logger.info("Pedido ya confirmado, no-op idempotente", extra={"order_id": dto.id_local})
            return self._to_dto(existente)

        if existente and existente["estado_local"] == "pendiente_creacion":
            raise PedidoEnEstadoAmbiguoError(
                f"El pedido {dto.id_local} quedó en un estado ambiguo en un intento "
                "anterior (no se sabe si Rocketfy llegó a crearlo). No se reintenta "
                "automáticamente — ver PedidoEnEstadoAmbiguoError."
            )

        reintentable = existente is None or (
            existente["estado_local"] == "error" and existente["id_rocketfy"] is None
        )
        if reintentable:
            if self._catalogo.resolver(dto.provincia, dto.canton) is None:
                raise UbicacionNoResueltaError(
                    f"'{dto.canton}' / '{dto.provincia}' no existe en el catálogo de Rocketfy."
                )
            if not dto.no_contra_entrega and dto.total < RECAUDO_MINIMO_CONTRAENTREGA:
                raise RecaudoMinimoNoAlcanzadoError(
                    f"El pedido {dto.id_local} es contraentrega y su total (${dto.total}) "
                    f"es menor al recaudo mínimo que exige Rocketfy para confirmarlo "
                    f"(${RECAUDO_MINIMO_CONTRAENTREGA}). Márquelo como prepagado "
                    "(no_contra_entrega=true) si el cliente ya pagó, o ajuste el monto."
                )
            self._repo.upsert_pendiente(dto.id_local, asdict(dto))
            existente = self._crear_en_rocketfy(dto)

        if existente["estado_local"] == "incompleto":
            raise PedidoIncompletoError(
                f"El pedido {dto.id_local} (id_rocketfy={existente['id_rocketfy']}) quedó con "
                "líneas incompletas en Rocketfy. Revisar manualmente antes de confirmar."
            )

        return self._confirmar_en_rocketfy(existente)

    def _crear_en_rocketfy(self, dto: CrearPedidoInputDTO) -> dict:
        payload = self._construir_payload(dto)
        try:
            respuesta = self._client.crear_pedido(payload)
        except RocketfyBusinessError as exc:
            # Respuesta clara de Rocketfy (p.ej. 405): "la transacción se
            # revierte por completo" según el doc -> seguro marcar 'error'
            # y permitir reintento limpio la próxima vez.
            self._repo.marcar_error_creacion(dto.id_local, exc.message)
            logger.error(
                "Fallo definitivo creando pedido en Rocketfy: %s", exc.message,
                extra={"order_id": dto.id_local},
            )
            raise
        # RocketfyRequestError (red/timeout) se propaga SIN tocar el estado:
        # queda en 'pendiente_creacion' (ambiguo) a propósito.

        id_rocketfy = respuesta["id"]
        products_stock = respuesta.get("products_stock", [])
        skus_simples = {linea.sku for linea in dto.lineas}
        completo = len(products_stock) >= len(skus_simples)
        estado = "creado" if completo else "incompleto"

        if not completo:
            logger.warning(
                "products_stock incompleto (%d/%d): posible SKU inexistente descartado en silencio",
                len(products_stock), len(skus_simples),
                extra={"order_id": dto.id_local, "id_rocketfy": id_rocketfy},
            )

        self._repo.marcar_creado(dto.id_local, id_rocketfy, estado)
        logger.info(
            "Pedido creado en Rocketfy", extra={"order_id": dto.id_local, "id_rocketfy": id_rocketfy}
        )
        return self._repo.obtener(dto.id_local)

    def _confirmar_en_rocketfy(self, existente: dict) -> PedidoDTO:
        id_local = existente["id_local"]
        try:
            self._client.confirmar_pedido(order_id=existente["id_rocketfy"])
        except RocketfyBusinessError as exc:
            # Errores de negocio en confirm son mayormente accionables (sin
            # cobertura, cantón no resuelto, saldo insuficiente...) — se
            # guarda el mensaje pero el pedido SIGUE en 'creado' (no se
            # marca como rechazado), porque el flujo recomendado por el
            # proveedor es corregir y reintentar confirmar, no recrear.
            self._repo.marcar_error_confirmacion(id_local, exc.message)
            logger.warning(
                "Confirmación rechazada por Rocketfy: %s", exc.message,
                extra={"order_id": id_local, "id_rocketfy": existente["id_rocketfy"]},
            )
            raise

        self._repo.marcar_confirmado(id_local)
        logger.info(
            "Pedido confirmado en Rocketfy",
            extra={"order_id": id_local, "id_rocketfy": existente["id_rocketfy"]},
        )
        return self._to_dto(self._repo.obtener(id_local))

    def modificar(self, id_local: int, cambios: ModificarPedidoInputDTO) -> PedidoDTO:
        """POST /orders/modify (Requerimiento 5). Solo valida localmente lo
        que es CIERTO de antemano (que exista y tenga id_rocketfy) — el
        resto de las reglas de negocio (estado del pedido en Rocketfy) las
        arbitra Rocketfy mismo, nunca las replicamos a ciegas localmente."""
        existente = self._repo.obtener(id_local)
        if existente is None:
            raise PedidoNoEncontradoError(f"No existe un pedido local con id_local={id_local}.")
        if existente["id_rocketfy"] is None:
            raise PedidoSinIdRocketfyError(
                f"El pedido {id_local} no tiene id_rocketfy asignado (estado_local="
                f"{existente['estado_local']}) — no se puede modificar en Rocketfy todavía."
            )

        # Si se cambia cantón o provincia, validar la combinación resultante
        # ANTES de enviar: el doc advierte que /orders/modify solo actualiza
        # el texto, no valida contra el catálogo — un cantón mal escrito
        # volverá a bloquear la confirmación más tarde si no lo atajamos aquí.
        if cambios.canton is not None or cambios.provincia is not None:
            actual = existente["payload_creacion"] or {}
            canton_final = cambios.canton or actual.get("canton")
            provincia_final = cambios.provincia or actual.get("provincia")
            if self._catalogo.resolver(provincia_final, canton_final) is None:
                raise UbicacionNoResueltaError(
                    f"'{canton_final}' / '{provincia_final}' no existe en el catálogo de Rocketfy."
                )

        payload = self._construir_payload_modificacion(existente["id_rocketfy"], cambios)
        self._client.modificar_pedido(payload)

        campos_cambiados = {k: v for k, v in asdict(cambios).items() if v is not None}
        self._repo.actualizar_datos_contacto(id_local, campos_cambiados)
        logger.info("Pedido modificado en Rocketfy", extra={"order_id": id_local, "id_rocketfy": existente["id_rocketfy"]})
        return self._to_dto(self._repo.obtener(id_local))

    def rechazar(self, id_local: int) -> PedidoDTO:
        """POST /orders/reject (Requerimiento 5). Posible hasta que se
        imprime la guía — a partir de ahí Rocketfy responde con un
        RocketfyBusinessError explícito que simplemente se propaga."""
        existente = self._repo.obtener(id_local)
        if existente is None:
            raise PedidoNoEncontradoError(f"No existe un pedido local con id_local={id_local}.")
        if existente["id_rocketfy"] is None:
            raise PedidoSinIdRocketfyError(
                f"El pedido {id_local} no tiene id_rocketfy asignado — no hay nada que rechazar en Rocketfy."
            )

        self._client.rechazar_pedido(existente["id_rocketfy"])
        self._repo.marcar_rechazado(id_local)
        logger.info("Pedido rechazado en Rocketfy", extra={"order_id": id_local, "id_rocketfy": existente["id_rocketfy"]})
        return self._to_dto(self._repo.obtener(id_local))

    def listar(self, estado: Optional[str] = None, page: int = 1, page_size: int = 20) -> dict:
        """Requerimiento del dashboard (Fase 2 - Etapa 2). Solo lee de
        nuestra propia base -- no llama a Rocketfy, por eso no hace falta
        manejar sus excepciones acá."""
        offset = (page - 1) * page_size
        filas = self._repo.listar(estado=estado, limit=page_size, offset=offset)
        return {
            "items": [self._to_resumen_dto(fila) for fila in filas],
            "total": self._repo.contar(estado=estado),
            "page": page,
            "page_size": page_size,
        }

    def obtener_detalle(self, id_local: int) -> PedidoDetalleDTO:
        fila = self._repo.obtener(id_local)
        if fila is None:
            raise PedidoNoEncontradoError(f"No existe un pedido local con id_local={id_local}.")
        return self._to_detalle_dto(fila)

    @staticmethod
    def _to_resumen_dto(row: dict) -> PedidoResumenDTO:
        payload = row["payload_creacion"] or {}
        return PedidoResumenDTO(
            id_local=row["id_local"],
            id_rocketfy=row["id_rocketfy"],
            estado_local=row["estado_local"],
            status_id_rocketfy=row["status_id_rocketfy"],
            nombre_cliente=payload.get("nombre_cliente", ""),
            telefono=payload.get("telefono", ""),
            canton=payload.get("canton", ""),
            provincia=payload.get("provincia", ""),
            total=Decimal(payload.get("total") or "0"),
            creado_en=row["creado_en"].isoformat() if row["creado_en"] else None,
            actualizado_en=row["actualizado_en"].isoformat() if row["actualizado_en"] else None,
        )

    @staticmethod
    def _to_detalle_dto(row: dict) -> PedidoDetalleDTO:
        payload = row["payload_creacion"] or {}
        return PedidoDetalleDTO(
            id_local=row["id_local"],
            id_rocketfy=row["id_rocketfy"],
            estado_local=row["estado_local"],
            status_id_rocketfy=row["status_id_rocketfy"],
            mensaje_error=row["mensaje_error"],
            nombre_cliente=payload.get("nombre_cliente", ""),
            telefono=payload.get("telefono", ""),
            direccion=payload.get("direccion", ""),
            direccion_2=payload.get("direccion_2", ""),
            canton=payload.get("canton", ""),
            provincia=payload.get("provincia", ""),
            codigo_postal=payload.get("codigo_postal"),
            total=Decimal(payload.get("total") or "0"),
            no_contra_entrega=payload.get("no_contra_entrega", False),
            observaciones_transportista=payload.get("observaciones_transportista", ""),
            lineas=[LineaPedidoDTO(**linea) for linea in payload.get("lineas", [])],
            creado_en=row["creado_en"].isoformat() if row["creado_en"] else None,
            confirmado_en=row["confirmado_en"].isoformat() if row["confirmado_en"] else None,
            actualizado_en=row["actualizado_en"].isoformat() if row["actualizado_en"] else None,
        )

    @staticmethod
    def _construir_payload_modificacion(id_rocketfy: int, cambios: ModificarPedidoInputDTO) -> dict:
        payload = {"order_id": id_rocketfy}
        for campo_interno, campo_rocketfy in _MAPEO_CAMPOS_MODIFICACION_ROCKETFY.items():
            valor = getattr(cambios, campo_interno)
            if valor is not None:
                payload[campo_rocketfy] = valor
        return payload

    @staticmethod
    def _construir_payload(dto: CrearPedidoInputDTO) -> dict:
        payload = {
            "id": dto.id_local,
            "name": dto.nombre_cliente,
            "phone": dto.telefono,
            "address": dto.direccion,
            "address_2": dto.direccion_2,
            "city": dto.canton,
            "province": dto.provincia,
            # Decimal -> string decimal con dos cifras: el proveedor advierte
            # no tratar los importes como número en coma flotante.
            "total": f"{dto.total:.2f}",
            "order_details": json.dumps(
                [{"sku": l.sku, "name": l.nombre, "quantity": l.cantidad} for l in dto.lineas]
            ),
            "not_COD": 1 if dto.no_contra_entrega else 0,
            # Enviar siempre, aunque sea "": si se omite, Rocketfy rellena
            # con un texto por defecto heredado que no aplica a Ecuador.
            "carrier_observations": dto.observaciones_transportista,
        }
        opcionales = {
            "email": dto.email,
            "zip": dto.codigo_postal,
            "store_id": dto.tienda_id,
            "ip": dto.ip,
            "latitude": dto.latitud,
            "longitude": dto.longitud,
        }
        payload.update({k: v for k, v in opcionales.items() if v is not None})
        return payload

    @staticmethod
    def _to_dto(row: dict) -> PedidoDTO:
        return PedidoDTO(
            id_local=row["id_local"],
            id_rocketfy=row["id_rocketfy"],
            estado_local=row["estado_local"],
            status_id_rocketfy=row["status_id_rocketfy"],
            mensaje_error=row["mensaje_error"],
            creado_en=row["creado_en"].isoformat() if row["creado_en"] else None,
            confirmado_en=row["confirmado_en"].isoformat() if row["confirmado_en"] else None,
            actualizado_en=row["actualizado_en"].isoformat() if row["actualizado_en"] else None,
        )
