from flask import g, jsonify, request
from marshmallow import ValidationError

from . import gestion_bp
from .schemas import atender_input_schema, solicitud_schema
from .services import EstadoInvalidoError, GestionService, SolicitudNoEncontradaError, SolicitudYaAtendidaError


def _build_service() -> GestionService:
    return GestionService()


@gestion_bp.get("")
def listar_solicitudes():
    """Lista las solicitudes (por defecto las pendientes: «Por gestionar»)."""
    try:
        items = _build_service().listar(request.args.get("estado", "pendiente"))
    except EstadoInvalidoError as exc:
        return jsonify(error=str(exc)), 422
    return jsonify(solicitud_schema.dump(items, many=True)), 200


@gestion_bp.get("/resumen")
def resumen():
    """Cuántas solicitudes esperan al dueño (para la insignia del menú)."""
    return jsonify(pendientes=_build_service().pendientes()), 200


@gestion_bp.post("/<int:solicitud_id>/atender")
def atender_solicitud(solicitud_id: int):
    try:
        datos = atender_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    usuario = (getattr(g, "usuario", None) or {}).get("email")
    try:
        solicitud = _build_service().atender(solicitud_id, usuario, datos.get("nota"))
    except SolicitudNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    except SolicitudYaAtendidaError as exc:
        return jsonify(error=str(exc)), 409
    return jsonify(solicitud_schema.dump(solicitud)), 200
