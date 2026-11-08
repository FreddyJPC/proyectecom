from flask import g, jsonify, request
from marshmallow import ValidationError

from . import ventas_bp
from .exceptions import AccionDeVentaNoPermitidaError, VentaNoEncontradaError
from .schemas import cancelar_input_schema, cobrar_input_schema, venta_schema
from .servicio import VentasService


def _build_service() -> VentasService:
    return VentasService()


def _usuario():
    return (getattr(g, "usuario", None) or {}).get("email")


def _cuerpo(schema):
    return schema.load(request.get_json(force=True, silent=True) or {})


@ventas_bp.post("/<int:venta_id>/cobrar")
def cobrar_venta(venta_id: int):
    """Marca la venta como cobrada (el dinero ya llegó). «Atendida» no significa cobrada."""
    try:
        datos = _cuerpo(cobrar_input_schema)
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    try:
        venta = _build_service().cobrar(venta_id, _usuario(), datos.get("nota"))
    except VentaNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    except AccionDeVentaNoPermitidaError as exc:
        return jsonify(error=exc.motivo), 409
    return jsonify(venta_schema.dump(venta)), 200


@ventas_bp.post("/<int:venta_id>/deshacer-cobro")
def deshacer_cobro_de_venta(venta_id: int):
    """Quita la marca de cobrada (por si se marcó por error o hay que devolver el dinero)."""
    try:
        venta = _build_service().deshacer_cobro(venta_id)
    except VentaNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    except AccionDeVentaNoPermitidaError as exc:
        return jsonify(error=exc.motivo), 409
    return jsonify(venta_schema.dump(venta)), 200


@ventas_bp.post("/<int:venta_id>/cancelar")
def cancelar_venta(venta_id: int):
    """Cancela la venta de un producto propio: devuelve el stock que se descontó y deja libre la conversación."""
    try:
        datos = _cuerpo(cancelar_input_schema)
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    try:
        venta = _build_service().cancelar(venta_id, _usuario(), datos.get("motivo"))
    except VentaNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    except AccionDeVentaNoPermitidaError as exc:
        return jsonify(error=exc.motivo), 409
    return jsonify(venta_schema.dump(venta)), 200
