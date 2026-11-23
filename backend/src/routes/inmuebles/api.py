"""
API del módulo «Inmuebles» (migración 037). Tres grupos de rutas:

- /inmuebles: fichas de propiedades, su material (fotos y videos) y los anuncios que hablan de cada una.
- /visitas: la agenda (el asistente registra los pedidos; el dueño confirma, reprograma, marca y avisa al cliente).
- /numeros-whatsapp: qué asistente atiende cada número del negocio.

Todas piden sesión (el login general de la app en src/app.py).
"""
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from .logica import ZONA_ECUADOR
from .repository import CodigoDeInmuebleRepetidoError, MaterialYaRegistradoError
from .schemas import (
    AnuncioInput,
    AsistenteConversacionInput,
    AvisarInput,
    EstadoInput,
    InmuebleDetalleSchema,
    InmuebleInput,
    InmuebleResumenSchema,
    MaterialInput,
    NumeroInput,
    NumeroSchema,
    OrdenInput,
    VisitaConfirmarInput,
    VisitaCrearInput,
    VisitaEstadoInput,
    VisitaNotasInput,
    VisitaSchema,
)
from .servicio import (
    DatosInvalidosError,
    EnvioFallidoError,
    InmuebleNoEncontradoError,
    InmueblesServicio,
    VentanaCerradaError,
    VisitaNoEncontradaError,
    VisitasServicio,
)

inmuebles_bp = Blueprint("inmuebles", __name__, url_prefix="/inmuebles")
visitas_bp = Blueprint("visitas", __name__, url_prefix="/visitas")
numeros_bp = Blueprint("numeros_whatsapp", __name__, url_prefix="/numeros-whatsapp")

_detalle = InmuebleDetalleSchema()
_resumenes = InmuebleResumenSchema(many=True)
_visita = VisitaSchema()
_visitas = VisitaSchema(many=True)
_numero = NumeroSchema()
_numeros = NumeroSchema(many=True)


def _inmuebles() -> InmueblesServicio:
    return InmueblesServicio()


def _agenda() -> VisitasServicio:
    return VisitasServicio()


def _usuario():
    return (getattr(g, "usuario", None) or {}).get("email")


def _cargar(schema, partial=False):
    return schema().load(request.get_json(force=True, silent=True) or {}, partial=partial)


def _error(exc: Exception):
    """Traduce los errores del servicio a respuestas HTTP con un mensaje que el dueño entiende."""
    if isinstance(exc, ValidationError):
        return jsonify(error="Revisa los datos.", detalle=exc.messages), 422
    if isinstance(exc, (InmuebleNoEncontradoError, VisitaNoEncontradaError)):
        return jsonify(error=str(exc)), 404
    if isinstance(exc, (CodigoDeInmuebleRepetidoError, MaterialYaRegistradoError)):
        return jsonify(error=str(exc)), 409
    if isinstance(exc, VentanaCerradaError):
        return jsonify(error=str(exc)), 409
    if isinstance(exc, EnvioFallidoError):
        return jsonify(error=str(exc)), 502
    if isinstance(exc, DatosInvalidosError):
        return jsonify(error=str(exc)), 422
    raise exc


_ERRORES = (
    ValidationError, InmuebleNoEncontradoError, VisitaNoEncontradaError, CodigoDeInmuebleRepetidoError, MaterialYaRegistradoError,
    VentanaCerradaError, EnvioFallidoError, DatosInvalidosError,
)


# -- /inmuebles ---------------------------------------------------------------------------------------------------------

@inmuebles_bp.get("")
def listar_inmuebles():
    incluir = request.args.get("incluirArchivados") == "true"
    return jsonify(_resumenes.dump(_inmuebles().listar(incluir))), 200


@inmuebles_bp.post("")
def crear_inmueble():
    try:
        return jsonify(_detalle.dump(_inmuebles().crear(_cargar(InmuebleInput)))), 201
    except _ERRORES as exc:
        return _error(exc)


@inmuebles_bp.get("/<int:inmueble_id>")
def ver_inmueble(inmueble_id: int):
    try:
        return jsonify(_detalle.dump(_inmuebles().detalle(inmueble_id))), 200
    except _ERRORES as exc:
        return _error(exc)


@inmuebles_bp.put("/<int:inmueble_id>")
def editar_inmueble(inmueble_id: int):
    try:
        return jsonify(_detalle.dump(_inmuebles().actualizar(inmueble_id, _cargar(InmuebleInput, partial=True)))), 200
    except _ERRORES as exc:
        return _error(exc)


@inmuebles_bp.put("/<int:inmueble_id>/estado")
def cambiar_estado_inmueble(inmueble_id: int):
    try:
        datos = _cargar(EstadoInput)
        return jsonify(_detalle.dump(_inmuebles().cambiar_estado(inmueble_id, datos["estado"]))), 200
    except _ERRORES as exc:
        return _error(exc)


@inmuebles_bp.post("/<int:inmueble_id>/material")
def agregar_material(inmueble_id: int):
    try:
        datos = _cargar(MaterialInput)
        return jsonify(_detalle.dump(_inmuebles().agregar_material(inmueble_id, datos["storage_path"], _usuario()))), 200
    except _ERRORES as exc:
        return _error(exc)


@inmuebles_bp.put("/<int:inmueble_id>/material/orden")
def ordenar_material(inmueble_id: int):
    try:
        datos = _cargar(OrdenInput)
        return jsonify(_detalle.dump(_inmuebles().ordenar_material(inmueble_id, datos["ids"]))), 200
    except _ERRORES as exc:
        return _error(exc)


@inmuebles_bp.delete("/<int:inmueble_id>/material/<int:material_id>")
def quitar_material(inmueble_id: int, material_id: int):
    try:
        return jsonify(_detalle.dump(_inmuebles().quitar_material(inmueble_id, material_id))), 200
    except _ERRORES as exc:
        return _error(exc)


@inmuebles_bp.post("/<int:inmueble_id>/anuncios")
def vincular_anuncio(inmueble_id: int):
    try:
        datos = _cargar(AnuncioInput)
        return jsonify(_detalle.dump(_inmuebles().vincular_anuncio(inmueble_id, datos["id_anuncio"], datos.get("nombre")))), 200
    except _ERRORES as exc:
        return _error(exc)


@inmuebles_bp.delete("/<int:inmueble_id>/anuncios/<id_anuncio>")
def desvincular_anuncio(inmueble_id: int, id_anuncio: str):
    try:
        return jsonify(_detalle.dump(_inmuebles().desvincular_anuncio(inmueble_id, id_anuncio))), 200
    except _ERRORES as exc:
        return _error(exc)


@inmuebles_bp.put("/conversaciones/<int:conversacion_id>/asistente")
def asistente_de_conversacion(conversacion_id: int):
    """El dueño cambia quién atiende una conversación (Victoria o el asistente de inmuebles, y de qué propiedad)."""
    try:
        datos = _cargar(AsistenteConversacionInput)
        _inmuebles().fijar_asistente_de_conversacion(conversacion_id, datos["asistente"], datos.get("inmueble_id"))
        return jsonify(status="ok"), 200
    except _ERRORES as exc:
        return _error(exc)


# -- /visitas -----------------------------------------------------------------------------------------------------------

def _dia(texto, por_defecto):
    """«2026-11-23» -> medianoche de ese día en Ecuador (la agenda se piensa en días de Ecuador)."""
    if not texto:
        return por_defecto
    try:
        return datetime.strptime(texto, "%Y-%m-%d").replace(tzinfo=ZONA_ECUADOR)
    except ValueError:
        raise DatosInvalidosError("Fecha no válida: usa AAAA-MM-DD.")


@visitas_bp.get("")
def listar_visitas():
    """`desde`/`hasta` (días, en Ecuador; `hasta` incluido), `estado` (varios separados por coma) e `inmuebleId`."""
    try:
        desde = _dia(request.args.get("desde"), None)
        hasta = _dia(request.args.get("hasta"), None)
        if hasta is not None:
            hasta = hasta + timedelta(days=1)
        estados = [e for e in (request.args.get("estado") or "").split(",") if e] or None
        visitas = _agenda().listar(desde=desde, hasta=hasta, estados=estados, inmueble_id=request.args.get("inmuebleId", type=int))
        return jsonify(_visitas.dump(visitas)), 200
    except _ERRORES as exc:
        return _error(exc)


@visitas_bp.get("/resumen")
def resumen_visitas():
    r = _agenda().resumen()
    return jsonify(porConfirmar=r["por_confirmar"], proximas=r["proximas"], hoy=r["hoy"]), 200


@visitas_bp.post("")
def crear_visita():
    try:
        return jsonify(_visita.dump(_agenda().crear_manual(_cargar(VisitaCrearInput)))), 201
    except _ERRORES as exc:
        return _error(exc)


@visitas_bp.put("/<int:visita_id>/confirmar")
def confirmar_visita(visita_id: int):
    try:
        datos = _cargar(VisitaConfirmarInput)
        visita = _agenda().confirmar(visita_id, datos["fecha_hora"], datos.get("encargado"), datos.get("notas"))
        return jsonify(_visita.dump(visita)), 200
    except _ERRORES as exc:
        return _error(exc)


@visitas_bp.put("/<int:visita_id>/estado")
def estado_visita(visita_id: int):
    try:
        datos = _cargar(VisitaEstadoInput)
        return jsonify(_visita.dump(_agenda().cambiar_estado(visita_id, datos["estado"], datos.get("motivo")))), 200
    except _ERRORES as exc:
        return _error(exc)


@visitas_bp.put("/<int:visita_id>/notas")
def notas_visita(visita_id: int):
    try:
        datos = _cargar(VisitaNotasInput)
        return jsonify(_visita.dump(_agenda().actualizar_notas(visita_id, datos.get("notas"), datos.get("encargado")))), 200
    except _ERRORES as exc:
        return _error(exc)


@visitas_bp.get("/<int:visita_id>/aviso")
def texto_aviso(visita_id: int):
    """El mensaje que se le enviaría al cliente (para revisarlo o ajustarlo antes de enviarlo)."""
    try:
        return jsonify(texto=_agenda().texto_de_aviso(visita_id)), 200
    except _ERRORES as exc:
        return _error(exc)


@visitas_bp.post("/<int:visita_id>/avisar")
def avisar_visita(visita_id: int):
    try:
        datos = _cargar(AvisarInput)
        return jsonify(_visita.dump(_agenda().avisar_cliente(visita_id, datos.get("texto")))), 200
    except _ERRORES as exc:
        return _error(exc)


# -- /numeros-whatsapp ---------------------------------------------------------------------------------------------------

@numeros_bp.get("")
def listar_numeros():
    return jsonify(_numeros.dump(_inmuebles().listar_numeros())), 200


@numeros_bp.put("")
def guardar_numero():
    try:
        return jsonify(_numero.dump(_inmuebles().guardar_numero(_cargar(NumeroInput)))), 200
    except _ERRORES as exc:
        return _error(exc)


@numeros_bp.delete("/<phone_number_id>")
def quitar_numero(phone_number_id: str):
    try:
        _inmuebles().quitar_numero(phone_number_id)
        return jsonify(status="ok"), 200
    except _ERRORES as exc:
        return _error(exc)
