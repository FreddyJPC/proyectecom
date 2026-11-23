from dataclasses import asdict

from flask import Response, g, jsonify, request
from marshmallow import ValidationError

from . import conversaciones_bp
from .exceptions import (
    ArchivoNoDisponibleError,
    ConversacionNoEncontradaError,
    DatosEnvioInvalidosError,
    EnvioWhatsAppFallidoError,
    FotoInvalidaError,
    PedidoYaCerradoError,
    SinMaterialError,
    SinPedidoEnCursoError,
    VentanaMensajeriaCerradaError,
)
from .schemas import (
    conversacion_detalle_schema,
    continuar_input_schema,
    datos_envio_input_schema,
    conversacion_lista_schema,
    enviar_material_input_schema,
    enviar_mensaje_input_schema,
    mensaje_schema,
    notas_input_schema,
    pedido_rocketfy_input_schema,
)
from .pedido_externo import PedidoExternoInvalidoError, PedidoExternoService, RocketfyNoDisponibleError
from .services import MAXIMO_BYTES_FOTO, ConversacionesService


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

    asistente = request.args.get("asistente")
    resultado = _build_service().listar_conversaciones(
        estado=estado, origen=origen, q=q, page=page, page_size=page_size, canal=canal,
        **({"asistente": asistente} if asistente in ("ventas", "inmuebles") else {}),
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


@conversaciones_bp.post("/<int:conversacion_id>/material")
def enviar_material(conversacion_id: int):
    """El dueño le manda al cliente las fotos y los videos del producto desde el panel."""
    try:
        data = enviar_material_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422

    try:
        resultado = _build_service().enviar_material(conversacion_id, data["sku"], data["imagen_ids"])
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    except SinMaterialError as exc:
        return jsonify(error=str(exc)), 422
    except VentanaMensajeriaCerradaError as exc:
        return jsonify(error=str(exc)), 409
    except EnvioWhatsAppFallidoError as exc:
        return jsonify(error=f"No se pudo enviar todo: {exc}"), 502

    return jsonify(resultado), 200


@conversaciones_bp.post("/<int:conversacion_id>/foto")
def enviar_foto_propia(conversacion_id: int):
    """El dueño le manda al cliente una foto de su teléfono o computadora (formulario con `archivo` y `descripcion` opcional)."""
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify(error="Falta la foto."), 422
    # Se lee como mucho un byte más del máximo: alcanza para saber si se pasa sin cargar archivos enormes en memoria.
    datos = archivo.stream.read(MAXIMO_BYTES_FOTO + 1)
    try:
        resultado = _build_service().enviar_foto_propia(
            conversacion_id, datos, archivo.mimetype, request.form.get("descripcion")
        )
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    except FotoInvalidaError as exc:
        return jsonify(error=str(exc)), 422
    except VentanaMensajeriaCerradaError as exc:
        return jsonify(error=str(exc)), 409
    except EnvioWhatsAppFallidoError as exc:
        return jsonify(error=f"No se pudo enviar la foto: {exc}"), 502
    return jsonify(resultado), 200


@conversaciones_bp.get("/<int:conversacion_id>/mensajes/<int:mensaje_id>/archivo")
def ver_archivo_de_un_mensaje(conversacion_id: int, mensaje_id: int):
    """La foto, el audio o el PDF de un mensaje (del cliente, o una foto que el dueño mandó desde el panel), para verlo en el panel
    (el servidor lo trae de Meta al momento)."""
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


@conversaciones_bp.put("/<int:conversacion_id>/datos-envio")
def actualizar_datos_envio(conversacion_id: int):
    """El dueño corrige o completa los datos de envío del pedido en curso (p. ej. la agencia de Servientrega para retirar)."""
    try:
        datos = datos_envio_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    usuario = (getattr(g, "usuario", None) or {}).get("email")
    try:
        _build_service().actualizar_datos_envio(conversacion_id, datos, usuario)
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    except (SinPedidoEnCursoError, PedidoYaCerradoError) as exc:
        return jsonify(error=str(exc)), 409
    except DatosEnvioInvalidosError as exc:
        return jsonify(error=str(exc), sugerencias=exc.sugerencias, bloqueos=exc.sugerencias), 422
    return jsonify(status="ok"), 200


@conversaciones_bp.get("/<int:conversacion_id>/pedidos-rocketfy")
def pedidos_rocketfy_sin_vincular(conversacion_id: int):
    """Los pedidos de Rocketfy de los que llegó aviso y que no son de ninguna conversación (hechos a mano en su panel)."""
    try:
        items = PedidoExternoService().sin_vincular(conversacion_id)
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    return jsonify(items=items), 200


@conversaciones_bp.post("/<int:conversacion_id>/pedido-rocketfy")
def registrar_pedido_rocketfy(conversacion_id: int):
    """«Ya hice el pedido en Rocketfy»: une a esta venta un pedido que el dueño creó a mano en el panel de Rocketfy."""
    try:
        datos = pedido_rocketfy_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    usuario = (getattr(g, "usuario", None) or {}).get("email")
    try:
        resultado = PedidoExternoService().registrar(conversacion_id, datos["id_rocketfy"], usuario)
    except ConversacionNoEncontradaError as exc:
        return jsonify(error=str(exc)), 404
    except (SinPedidoEnCursoError, PedidoYaCerradoError, PedidoExternoInvalidoError) as exc:
        return jsonify(error=str(exc)), 409
    except RocketfyNoDisponibleError as exc:
        return jsonify(error=str(exc)), 502
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
