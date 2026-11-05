from dataclasses import asdict

from flask import g, jsonify, request
from marshmallow import ValidationError

from . import ajustes_bp
from .exceptions import AjustesInvalidosError
from .schemas import guardar_input_schema, respuesta_schema
from .services import AjustesService


def _build_service() -> AjustesService:
    return AjustesService()


@ajustes_bp.get("/negocio")
def ver_ajustes():
    return jsonify(respuesta_schema.dump(asdict(_build_service().obtener()))), 200


@ajustes_bp.put("/negocio")
def guardar_ajustes():
    try:
        datos = guardar_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    usuario = (getattr(g, "usuario", None) or {}).get("email")
    try:
        respuesta = _build_service().guardar(datos, usuario)
    except AjustesInvalidosError as exc:
        return jsonify(error="Datos inválidos.", detalle={"ajustes": exc.mensajes}), 422
    return jsonify(respuesta_schema.dump(asdict(respuesta))), 200
