from flask import jsonify, request
from marshmallow import ValidationError

from . import anuncios_bp
from .exceptions import AnuncioInvalidoError, AnuncioNoVinculadoError, AnuncioYaVinculadoError, ProductoNoExisteError
from .schemas import (
    anuncio_schema,
    preparar_anuncio,
    preparar_resumen,
    resumen_schema,
    vincular_input_schema,
    vinculo_schema,
)
from .servicio import PERIODOS_VALIDOS_DIAS, AnuncioServicio


def _build_service() -> AnuncioServicio:
    return AnuncioServicio()


def _dias():
    """Periodo de las cifras: 7, 30 o 90 días; sin el parámetro (o 0) es todo el tiempo. Devuelve (dias, error)."""
    bruto = request.args.get("dias")
    if bruto in (None, "", "0", "todo"):
        return None, None
    try:
        dias = int(bruto)
    except ValueError:
        dias = -1
    if dias not in PERIODOS_VALIDOS_DIAS:
        return None, (jsonify(error=f"El periodo debe ser {', '.join(map(str, PERIODOS_VALIDOS_DIAS))} días o todo."), 422)
    return dias, None


@anuncios_bp.get("")
def listar_anuncios():
    """Los anuncios que han traído clientes (o que vinculaste de antemano), con su producto y lo que han vendido."""
    dias, error = _dias()
    if error:
        return error
    filas = _build_service().listar(dias)
    return jsonify(anuncio_schema.dump([preparar_anuncio(f) for f in filas], many=True)), 200


@anuncios_bp.get("/resumen")
def resumen_de_origenes():
    """«De dónde vienen tus clientes»: anuncio frente a directo, con conversaciones y ventas de cada uno."""
    dias, error = _dias()
    if error:
        return error
    return jsonify(resumen_schema.dump(preparar_resumen(_build_service().resumen(dias)))), 200


@anuncios_bp.put("/<id_anuncio>/producto")
def vincular_anuncio(id_anuncio: str):
    """Vincula el anuncio con un producto (también sirve para vincularlo ANTES de que llegue el primer cliente)."""
    try:
        datos = vincular_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    try:
        vinculo = _build_service().vincular(id_anuncio, datos["sku"], datos.get("nombre"), datos["reasignar"])
    except AnuncioInvalidoError as exc:
        return jsonify(error=str(exc)), 422
    except ProductoNoExisteError as exc:
        return jsonify(error=str(exc)), 404
    except AnuncioYaVinculadoError as exc:
        return jsonify(error=str(exc), vinculadoA={"sku": exc.sku_actual, "nombre": exc.nombre_actual}), 409
    return jsonify(vinculo_schema.dump(vinculo)), 200


@anuncios_bp.delete("/<id_anuncio>/producto")
def desvincular_anuncio(id_anuncio: str):
    """Quita el vínculo: Victoria vuelve a preguntar qué producto quiere el cliente que llegue por ese anuncio."""
    try:
        _build_service().desvincular(id_anuncio)
    except AnuncioInvalidoError as exc:
        return jsonify(error=str(exc)), 422
    except AnuncioNoVinculadoError as exc:
        return jsonify(error=str(exc)), 404
    # 200 con cuerpo (no 204): el cliente de la app siempre espera JSON en las respuestas correctas.
    return jsonify(ok=True), 200
