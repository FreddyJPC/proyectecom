import re
from dataclasses import asdict
from decimal import Decimal

from flask import g, jsonify, request
from marshmallow import ValidationError

from src.integrations.rocketfy import RocketfyAuthError, RocketfyBusinessError, RocketfyRequestError
from src.routes.productos.exceptions import SkuNoExisteEnRocketfyError

from . import productos_bot_bp
from .contenido_ia import ContenidoIAService
from .exceptions import (
    IAFalloError,
    IANoDisponibleError,
    ProductoBotNoEncontradoError,
    ProductoBotYaExisteError,
    PublicacionBloqueadaError,
    SkuInvalidoError,
    TopeDeIAAlcanzadoError,
    TransicionInvalidaError,
)
from .redaccion import NotasDelDueno
from .schemas import (
    borrador_contenido_schema,
    crear_input_schema,
    detalle_schema,
    editar_input_schema,
    generar_contenido_input_schema,
    recomendacion_precio_schema,
    resumen_lista_schema,
    uso_ia_schema,
)
from .services import ProductosBotService

_ERRORES_ROCKETFY = (RocketfyAuthError, RocketfyBusinessError, RocketfyRequestError)


def _build_service() -> ProductosBotService:
    return ProductosBotService()


def _build_contenido_service() -> ContenidoIAService:
    return ContenidoIAService()


def _usuario():
    """Correo de quien hace la petición (lo deja el login en src/app.py)."""
    return (getattr(g, "usuario", None) or {}).get("email")


def _detalle(dto, status=200):
    return jsonify(detalle_schema.dump(asdict(dto))), status


def _responder_error(exc):
    """Traduce las excepciones de la gestión de productos a respuestas HTTP.
    Devuelve None si no es una de las conocidas."""
    if isinstance(exc, ProductoBotNoEncontradoError):
        return jsonify(error=str(exc)), 404
    if isinstance(exc, (ProductoBotYaExisteError, TransicionInvalidaError)):
        return jsonify(error=str(exc)), 409
    if isinstance(exc, PublicacionBloqueadaError):
        return jsonify(error="El producto no cumple lo mínimo para esa acción.", bloqueos=exc.bloqueos), 422
    if isinstance(exc, (SkuInvalidoError, SkuNoExisteEnRocketfyError)):
        return jsonify(error=str(exc)), 422
    if isinstance(exc, _ERRORES_ROCKETFY):
        return jsonify(error=f"No se pudo consultar Rocketfy: {exc}"), 502
    if isinstance(exc, TopeDeIAAlcanzadoError):
        return jsonify(error=str(exc), uso={"tope": exc.tope, "usadas": exc.usadas, "restantes": 0}), 429
    if isinstance(exc, IANoDisponibleError):
        return jsonify(error=str(exc)), 503
    if isinstance(exc, IAFalloError):
        return jsonify(error=str(exc)), 502
    return None


_ERRORES_CONOCIDOS = (
    ProductoBotNoEncontradoError,
    ProductoBotYaExisteError,
    TransicionInvalidaError,
    PublicacionBloqueadaError,
    SkuInvalidoError,
    SkuNoExisteEnRocketfyError,
    TopeDeIAAlcanzadoError,
    IANoDisponibleError,
    IAFalloError,
) + _ERRORES_ROCKETFY


@productos_bot_bp.get("")
def listar_productos_bot():
    incluir_archivados = request.args.get("incluirArchivados", "false").lower() == "true"
    resultado = _build_service().listar(incluir_archivados=incluir_archivados)
    return jsonify(resumen_lista_schema.dump([asdict(r) for r in resultado])), 200


@productos_bot_bp.get("/contenido/uso")
def uso_de_la_ia():
    """Cuántos borradores de IA quedan hoy (para mostrarlo antes de pedir uno)."""
    try:
        return jsonify(uso_ia_schema.dump(asdict(_build_contenido_service().uso()))), 200
    except _ERRORES_CONOCIDOS as exc:
        return _responder_error(exc)


@productos_bot_bp.get("/<sku>")
def ver_producto_bot(sku: str):
    try:
        return _detalle(_build_service().obtener_detalle(sku))
    except _ERRORES_CONOCIDOS as exc:
        return _responder_error(exc)


@productos_bot_bp.post("")
def crear_producto_bot():
    try:
        data = crear_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    try:
        return _detalle(_build_service().crear_borrador(data["sku"], _usuario()), 201)
    except _ERRORES_CONOCIDOS as exc:
        return _responder_error(exc)


@productos_bot_bp.patch("/<sku>")
def editar_producto_bot(sku: str):
    try:
        cambios = editar_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    try:
        return _detalle(_build_service().editar(sku, cambios, _usuario()))
    except _ERRORES_CONOCIDOS as exc:
        return _responder_error(exc)


@productos_bot_bp.post("/<sku>/contenido/generar")
def generar_contenido(sku: str):
    """Pide un BORRADOR de contenido a la IA. No guarda nada: la persona lo
    acepta campo por campo y lo guarda desde la ficha."""
    try:
        data = generar_contenido_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    notas = NotasDelDueno(producto_de_salud=data["producto_de_salud"], **data["notas"])
    try:
        borrador = _build_contenido_service().generar(sku, notas, data["campos"], _usuario())
    except _ERRORES_CONOCIDOS as exc:
        return _responder_error(exc)
    return jsonify(borrador_contenido_schema.dump(asdict(borrador))), 200


_MONTO = re.compile(r"^\d{1,7}(\.\d{1,2})?$")


def _monto_de_consulta(nombre: str):
    """Lee un monto opcional de la URL. Devuelve (Decimal | None, error | None).
    Formato estricto (hasta 7 enteros y 2 decimales): nada de notación
    científica ni textos raros que lleguen hasta Decimal."""
    texto = (request.args.get(nombre) or "").strip()
    if not texto:
        return None, None
    if not _MONTO.match(texto) or Decimal(texto) <= 0:
        return None, f"«{nombre}» debe ser un monto mayor que cero, por ejemplo 24.99."
    return Decimal(texto), None


@productos_bot_bp.get("/<sku>/precio")
def recomendar_precio(sku: str):
    """Calculadora de precio. Solo lee: no guarda nada. `?precio=` evalúa un
    precio concreto y `?competencia=` prueba un precio de la competencia."""
    precio, error = _monto_de_consulta("precio")
    if error:
        return jsonify(error=error), 422
    competencia, error = _monto_de_consulta("competencia")
    if error:
        return jsonify(error=error), 422

    try:
        resultado = _build_service().recomendar_precio(sku, precio=precio, competencia=competencia)
    except _ERRORES_CONOCIDOS as exc:
        return _responder_error(exc)
    return jsonify(recomendacion_precio_schema.dump(asdict(resultado))), 200


@productos_bot_bp.post("/<sku>/actualizar-rocketfy")
def actualizar_desde_rocketfy(sku: str):
    try:
        return _detalle(_build_service().actualizar_desde_rocketfy(sku, _usuario()))
    except _ERRORES_CONOCIDOS as exc:
        return _responder_error(exc)


def _transicion(sku: str, accion: str):
    try:
        return _detalle(getattr(_build_service(), accion)(sku, _usuario()))
    except _ERRORES_CONOCIDOS as exc:
        return _responder_error(exc)


@productos_bot_bp.post("/<sku>/publicar")
def publicar_producto_bot(sku: str):
    return _transicion(sku, "publicar")


@productos_bot_bp.post("/<sku>/reanudar")
def reanudar_producto_bot(sku: str):
    return _transicion(sku, "reanudar")


@productos_bot_bp.post("/<sku>/pausar")
def pausar_producto_bot(sku: str):
    return _transicion(sku, "pausar")


@productos_bot_bp.post("/<sku>/archivar")
def archivar_producto_bot(sku: str):
    return _transicion(sku, "archivar")


@productos_bot_bp.post("/<sku>/restaurar")
def restaurar_producto_bot(sku: str):
    return _transicion(sku, "restaurar")
