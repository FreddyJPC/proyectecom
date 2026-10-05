from dataclasses import asdict

from flask import jsonify, request
from marshmallow import ValidationError

from src.integrations.rocketfy import (
    RocketfyAuthError,
    RocketfyBusinessError,
    RocketfyRequestError,
    get_rocketfy_client,
)

from . import pedidos_bp
from .dto import CrearPedidoInputDTO, LineaPedidoDTO, ModificarPedidoInputDTO
from .exceptions import (
    PedidoEnEstadoAmbiguoError,
    PedidoIncompletoError,
    PedidoNoEncontradoError,
    PedidoSinIdRocketfyError,
    RecaudoMinimoNoAlcanzadoError,
    UbicacionNoResueltaError,
)
from .schemas import (
    crear_pedido_input_schema,
    modificar_pedido_input_schema,
    pedido_detalle_schema,
    pedido_resumen_schema,
    pedido_response_schema,
)
from .services import PedidoService

_ERRORES_ROCKETFY = (RocketfyAuthError, RocketfyBusinessError, RocketfyRequestError)


def _build_service() -> PedidoService:
    return PedidoService(client=get_rocketfy_client())


def _responder_error_rocketfy(exc):
    if isinstance(exc, RocketfyAuthError):
        return jsonify(error=f"Rocketfy no autorizó la solicitud: {exc}"), 502
    if isinstance(exc, RocketfyBusinessError):
        return jsonify(error=exc.message, codigoRocketfy=exc.code), 422
    return jsonify(error=f"Error de comunicación con Rocketfy: {exc}"), 502


@pedidos_bp.get("")
def listar_pedidos():
    """Fase 2 - Etapa 2 del frontend: listado paginado, filtrable por
    estado_local. Solo lee de nuestra base, no llama a Rocketfy."""
    estado = request.args.get("estado")
    page = request.args.get("page", 1, type=int)
    page_size = min(request.args.get("pageSize", 20, type=int), 100)

    resultado = _build_service().listar(estado=estado, page=page, page_size=page_size)
    return jsonify(
        items=[pedido_resumen_schema.dump(asdict(item)) for item in resultado["items"]],
        total=resultado["total"],
        page=resultado["page"],
        pageSize=resultado["page_size"],
    ), 200


@pedidos_bp.get("/<int:id_local>")
def ver_pedido(id_local: int):
    try:
        detalle = _build_service().obtener_detalle(id_local)
    except PedidoNoEncontradoError as exc:
        return jsonify(error=str(exc)), 404
    return jsonify(pedido_detalle_schema.dump(asdict(detalle))), 200


@pedidos_bp.post("")
def crear_pedido():
    try:
        data = crear_pedido_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    lineas = [LineaPedidoDTO(**linea) for linea in data.pop("lineas")]
    dto = CrearPedidoInputDTO(lineas=lineas, **data)

    try:
        resultado = _build_service().crear_y_confirmar(dto)
        return jsonify(pedido_response_schema.dump(asdict(resultado))), 200
    except UbicacionNoResueltaError as exc:
        return jsonify(error=str(exc)), 422
    except RecaudoMinimoNoAlcanzadoError as exc:
        return jsonify(error=str(exc)), 422
    except PedidoEnEstadoAmbiguoError as exc:
        return jsonify(error=str(exc)), 409
    except PedidoIncompletoError as exc:
        return jsonify(error=str(exc)), 409
    except _ERRORES_ROCKETFY as exc:
        return _responder_error_rocketfy(exc)


@pedidos_bp.patch("/<int:id_local>")
def modificar_pedido(id_local: int):
    try:
        data = modificar_pedido_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    dto = ModificarPedidoInputDTO(**data)
    try:
        resultado = _build_service().modificar(id_local, dto)
        return jsonify(pedido_response_schema.dump(asdict(resultado))), 200
    except PedidoNoEncontradoError as exc:
        return jsonify(error=str(exc)), 404
    except PedidoSinIdRocketfyError as exc:
        return jsonify(error=str(exc)), 409
    except UbicacionNoResueltaError as exc:
        return jsonify(error=str(exc)), 422
    except _ERRORES_ROCKETFY as exc:
        return _responder_error_rocketfy(exc)


@pedidos_bp.post("/<int:id_local>/rechazar")
def rechazar_pedido(id_local: int):
    try:
        resultado = _build_service().rechazar(id_local)
        return jsonify(pedido_response_schema.dump(asdict(resultado))), 200
    except PedidoNoEncontradoError as exc:
        return jsonify(error=str(exc)), 404
    except PedidoSinIdRocketfyError as exc:
        return jsonify(error=str(exc)), 409
    except _ERRORES_ROCKETFY as exc:
        return _responder_error_rocketfy(exc)
