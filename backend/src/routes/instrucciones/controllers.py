from dataclasses import asdict

from flask import g, jsonify, request
from marshmallow import ValidationError

from src.routes.whatsapp.instrucciones import InstruccionesInvalidas, SinBorradorError

from . import instrucciones_bp
from .exceptions import VersionNoExisteError
from .schemas import guardar_borrador_input_schema, instrucciones_schema, publicar_input_schema
from .services import InstruccionesAdminService


def _build_service() -> InstruccionesAdminService:
    return InstruccionesAdminService()


def _usuario():
    return (getattr(g, "usuario", None) or {}).get("email")


def _responder(dto, status=200):
    return jsonify(instrucciones_schema.dump(asdict(dto))), status


def _error(exc):
    if isinstance(exc, InstruccionesInvalidas):
        return jsonify(error="Las instrucciones no son válidas.", detalle=exc.errores), 422
    if isinstance(exc, SinBorradorError):
        return jsonify(error=str(exc)), 409
    if isinstance(exc, VersionNoExisteError):
        return jsonify(error=str(exc)), 404
    return None


_ERRORES = (InstruccionesInvalidas, SinBorradorError, VersionNoExisteError)


@instrucciones_bp.get("")
def ver_instrucciones():
    return _responder(_build_service().ver())


@instrucciones_bp.put("/borrador")
def guardar_borrador():
    try:
        datos = guardar_borrador_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    try:
        return _responder(_build_service().guardar_borrador(datos["secciones"], datos["nota"], _usuario()))
    except _ERRORES as exc:
        return _error(exc)


@instrucciones_bp.delete("/borrador")
def descartar_borrador():
    return _responder(_build_service().descartar_borrador())


@instrucciones_bp.post("/publicar")
def publicar():
    try:
        datos = publicar_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    try:
        return _responder(_build_service().publicar(datos["nota"], _usuario()))
    except _ERRORES as exc:
        return _error(exc)


@instrucciones_bp.post("/volver-a-la-original")
def volver_a_la_original():
    return _responder(_build_service().volver_a_la_original())


@instrucciones_bp.post("/versiones/<int:id_version>/cargar")
def cargar_version(id_version: int):
    try:
        return _responder(_build_service().cargar_version(id_version, _usuario()))
    except _ERRORES as exc:
        return _error(exc)
