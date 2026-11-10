from dataclasses import asdict

from flask import Response, jsonify, request
from marshmallow import ValidationError

from . import conversaciones_bp
from .exceptions import (
    ArchivoNoDisponibleError,
    ConversacionNoEncontradaError,
    EnvioWhatsAppFallidoError,
    SinPedidoEnCursoError,
    VentanaMensajeriaCerradaError,
)
from .schemas import (
    conversacion_detalle_schema,
    continuar_input_schema,
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
    canal = request.args.get("canal")
    q = request.args.get("q")
    page = request.args.get("page", 1, type=int)
    page_size = min(request.args.get("pageSize", 20, type=int), 100)

    resultado = _build_service().listar_conversaciones(
        estado=estado, origen=origen, q=q, page=page, page_size=page_size, canal=canal
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
        return jsonify(error=f"El mensaje se guardó pero no se pudo enviar: {exc}"), 502

    return jsonify(mensaje_schema.dump(asdict(mensaje))), 200


@conversaciones_bp.get("/<int:conversacion_id>/mensajes/<int:mensaje_id>/archivo")
def ver_archivo_de_un_mensaje(conversacion_id: int, mensaje_id: int):
    """La foto, el audio o el PDF que mandó el cliente, para verlo en el panel (el servidor lo trae de Meta al momento)."""
    try:
        datos, mime = _build_service().obtener_archivo(conversacion_id, mensaje_id)
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    except ArchivoNoDisponibleError as exc:
        return jsonify(error=str(exc)), 404
    # `nosniff` + sin caché compartida: es un archivo de un cliente, no una página; nunca debe interpretarse como HTML.
    return Response(datos, mimetype=mime.split(";")[0], headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@conversaciones_bp.post("/<int:conversacion_id>/tomar")
def tomar_conversacion(conversacion_id: int):
    try:
        _build_service().tomar(conversacion_id)
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    return jsonify(status="ok"), 200


@conversaciones_bp.post("/<int:conversacion_id>/continuar")
def continuar_venta(conversacion_id: int):
    """Devuelve la conversación a Victoria para que siga cerrando la venta (con o sin pago confirmado, y con una nota opcional)."""
    try:
        datos = continuar_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    try:
        resultado = _build_service().continuar_venta(conversacion_id, bool(datos.get("pago_confirmado")), datos.get("nota"))
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    except SinPedidoEnCursoError as exc:
        return jsonify(error=str(exc)), 409
    return jsonify(status="ok", **resultado), 200


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
