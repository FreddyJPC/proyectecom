from dataclasses import asdict

from flask import g, jsonify, request
from marshmallow import ValidationError

from src.config.parametros import ParametroDesconocidoError, ValorInvalido

from . import parametros_bp
from .schemas import cambio_schema, guardar_input_schema, parametro_schema, respuesta_schema
from .services import ParametrosAdminService

LIMITE_HISTORIAL_POR_DEFECTO = 50
LIMITE_HISTORIAL_MAXIMO = 200


def _build_service() -> ParametrosAdminService:
    return ParametrosAdminService()


def _usuario():
    return (getattr(g, "usuario", None) or {}).get("email")


def _no_existe(clave: str):
    return jsonify(error=f"No existe el parámetro '{clave}'."), 404


@parametros_bp.get("")
def ver_parametros():
    return jsonify(respuesta_schema.dump(asdict(_build_service().listar()))), 200


@parametros_bp.get("/historial")
def ver_historial():
    try:
        limite = int(request.args.get("limite", LIMITE_HISTORIAL_POR_DEFECTO))
    except ValueError:
        return jsonify(error="El límite debe ser un número."), 422
    limite = max(1, min(limite, LIMITE_HISTORIAL_MAXIMO))
    return jsonify(cambio_schema.dump([asdict(c) for c in _build_service().historial(limite)])), 200


@parametros_bp.put("/<clave>")
def guardar_parametro(clave: str):
    try:
        datos = guardar_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    try:
        guardado = _build_service().guardar(clave, datos["valor"], _usuario())
    except ParametroDesconocidoError:
        return _no_existe(clave)
    except ValorInvalido as exc:
        return jsonify(error=str(exc), detalle={"valor": [str(exc)]}), 422
    return jsonify(parametro_schema.dump(asdict(guardado))), 200


@parametros_bp.delete("/<clave>")
def restaurar_parametro(clave: str):
    """Quita el valor guardado en la app: el parámetro vuelve a valer lo de la variable
    del servidor o, si no hay, su valor original del código."""
    try:
        restaurado = _build_service().restaurar(clave, _usuario())
    except ParametroDesconocidoError:
        return _no_existe(clave)
    return jsonify(parametro_schema.dump(asdict(restaurado))), 200
