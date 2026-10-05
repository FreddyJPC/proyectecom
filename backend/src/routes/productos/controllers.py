from dataclasses import asdict

from flask import jsonify, request
from marshmallow import ValidationError

from src.integrations.rocketfy import (
    RocketfyAuthError,
    RocketfyBusinessError,
    RocketfyRequestError,
    get_rocketfy_client,
)

from . import productos_bp
from .dto import SkuMonitoreadoInputDTO
from .exceptions import SkuNoExisteEnRocketfyError
from .schemas import sku_monitoreado_input_schema, skus_monitoreados_response_schema
from .services import ProductosService

_ERRORES_ROCKETFY = (RocketfyAuthError, RocketfyBusinessError, RocketfyRequestError)


def _build_service() -> ProductosService:
    return ProductosService(client=get_rocketfy_client())


# ---------------------------------------------------------------
# Proxy directo al catálogo de Rocketfy (requerimientos 4 y 7)
# ---------------------------------------------------------------
@productos_bp.get("")
def buscar_productos():
    q = request.args.get("q")
    page = request.args.get("page", 1, type=int)
    try:
        return jsonify(get_rocketfy_client().listar_productos(q=q, page=page)), 200
    except _ERRORES_ROCKETFY as exc:
        return jsonify(error=str(exc)), 502


@productos_bp.get("/<int:product_id>")
def ver_producto(product_id: int):
    try:
        return jsonify(get_rocketfy_client().ver_producto(product_id)), 200
    except _ERRORES_ROCKETFY as exc:
        return jsonify(error=str(exc)), 502


# ---------------------------------------------------------------
# Gestión de SKUs monitoreados (alimenta el job stock_watcher)
# ---------------------------------------------------------------
@productos_bp.get("/monitoreados")
def listar_monitoreados():
    solo_activos = request.args.get("soloActivos", "true").lower() != "false"
    resultado = _build_service().listar_monitoreados(solo_activos=solo_activos)
    return jsonify(skus_monitoreados_response_schema.dump([asdict(r) for r in resultado])), 200


@productos_bp.post("/monitoreados")
def agregar_monitoreado():
    try:
        data = sku_monitoreado_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    dto = SkuMonitoreadoInputDTO(**data)
    try:
        _build_service().agregar_sku_monitoreado(dto)
        return jsonify(message=f"SKU '{dto.sku}' agregado al monitoreo."), 201
    except SkuNoExisteEnRocketfyError as exc:
        return jsonify(error=str(exc)), 422
    except _ERRORES_ROCKETFY as exc:
        return jsonify(error=str(exc)), 502


@productos_bp.delete("/monitoreados/<sku>")
def quitar_monitoreado(sku: str):
    encontrado = _build_service().quitar_sku_monitoreado(sku)
    if not encontrado:
        return jsonify(error=f"SKU '{sku}' no estaba en la lista de monitoreo."), 404
    return jsonify(message=f"SKU '{sku}' desactivado del monitoreo."), 200
