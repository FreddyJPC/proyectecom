from dataclasses import asdict

from flask import jsonify, request
from marshmallow import ValidationError

from . import conversaciones_bp
from .exceptions import ConversacionNoEncontradaError, EnvioWhatsAppFallidoError, VentanaMensajeriaCerradaError
from .schemas import (
    conversacion_detalle_schema,
    conversacion_lista_schema,
    enviar_mensaje_input_schema,
    mensaje_schema,
    notas_input_schema,
)
from .services import ConversacionesService


def _build_service() -> ConversacionesService:
    return ConversacionesService()


@conversaciones_bp.get("")
def listar_conversaciones():
    estado = request.args.get("estado")
    origen = request.args.get("origen")
    q = request.args.get("q")
    page = request.args.get("page", 1, type=int)
    page_size = min(request.args.get("pageSize", 20, type=int), 100)

    resultado = _build_service().listar_conversaciones(
        estado=estado, origen=origen, q=q, page=page, page_size=page_size
    )
    return jsonify(conversacion_lista_schema.dump(asdict(resultado))), 200


@conversaciones_bp.get("/<int:conversacion_id>")
def ver_conversacion(conversacion_id: int):
    try:
        detalle = _build_service().obtener_detalle(conversacion_id)
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    return jsonify(conversacion_detalle_schema.dump(asdict(detalle))), 200


@conversaciones_bp.post("/<int:conversacion_id>/mensajes")
def enviar_mensaje(conversacion_id: int):
    try:
        data = enviar_mensaje_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    try:
        mensaje = _build_service().enviar_mensaje_manual(conversacion_id, data["contenido"])
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    except VentanaMensajeriaCerradaError as exc:
        return jsonify(error=str(exc)), 409
    except EnvioWhatsAppFallidoError as exc:
        return jsonify(error=f"El mensaje se guardó pero no se pudo enviar por WhatsApp: {exc}"), 502

    return jsonify(mensaje_schema.dump(asdict(mensaje))), 200


@conversaciones_bp.post("/<int:conversacion_id>/reactivar")
def reactivar_conversacion(conversacion_id: int):
    try:
        _build_service().reactivar(conversacion_id)
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    return jsonify(status="ok"), 200


@conversaciones_bp.patch("/<int:conversacion_id>/notas")
def actualizar_notas(conversacion_id: int):
    try:
        data = notas_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    try:
        _build_service().actualizar_notas(conversacion_id, data.get("notas_internas"))
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    return jsonify(status="ok"), 200
