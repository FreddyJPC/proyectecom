from flask import g, jsonify, request
from marshmallow import ValidationError

from . import contactos_bp, leads_bp
from .exceptions import (
    ContactoNoEncontradoError,
    DatosInvalidosError,
    LeadNoEncontradoError,
    OtroLeadAbiertoError,
    VentaYaCerradaError,
)
from .schemas import (
    cambiar_temperatura_input_schema,
    no_contactar_input_schema,
    preparar_detalle,
    preparar_lista,
    preparar_resumen,
)
from .servicio import PERIODOS_VALIDOS_DIAS, LeadsServicio


def _servicio() -> LeadsServicio:
    return LeadsServicio()


def _usuario():
    return (getattr(g, "usuario", None) or {}).get("email")


def _entero(nombre: str, por_defecto=None):
    bruto = request.args.get(nombre)
    if bruto in (None, ""):
        return por_defecto
    try:
        return int(bruto)
    except ValueError:
        return por_defecto


def _booleano(nombre: str):
    bruto = (request.args.get(nombre) or "").lower()
    return {"true": True, "false": False}.get(bruto)


@leads_bp.get("")
def listar_leads():
    """La tabla de leads con sus filtros: temperatura (varias separadas por coma), etapa, origen, canal, producto, búsqueda,
    «no contactar», días sin respuesta y orden."""
    temperaturas = [t for t in (request.args.get("temperatura") or "").split(",") if t]
    try:
        resultado = _servicio().listar(
            temperaturas=temperaturas or None,
            etapa=request.args.get("etapa") or None,
            origen=request.args.get("origen") or None,
            canal=request.args.get("canal") or None,
            producto_sku=request.args.get("producto") or None,
            q=request.args.get("q"),
            no_contactar=_booleano("noContactar"),
            sin_respuesta_dias=_entero("sinRespuestaDias"),
            orden=request.args.get("orden", "actividad"),
            page=_entero("page", 1),
            page_size=_entero("pageSize", 20),
        )
    except DatosInvalidosError as exc:
        return jsonify(error=str(exc)), 422
    return jsonify(preparar_lista(resultado)), 200


@leads_bp.get("/resumen")
def resumen_de_leads():
    bruto = request.args.get("dias")
    dias = None
    if bruto not in (None, "", "0", "todo"):
        try:
            dias = int(bruto)
        except ValueError:
            dias = -1
        if dias not in PERIODOS_VALIDOS_DIAS:
            return jsonify(error=f"El periodo debe ser {', '.join(map(str, PERIODOS_VALIDOS_DIAS))} días o todo."), 422
    return jsonify(preparar_resumen(_servicio().resumen(dias))), 200


@leads_bp.get("/<int:lead_id>")
def ver_lead(lead_id: int):
    try:
        return jsonify(preparar_detalle(_servicio().detalle(lead_id))), 200
    except LeadNoEncontradoError as exc:
        return jsonify(error=str(exc)), 404


@leads_bp.patch("/<int:lead_id>")
def cambiar_temperatura(lead_id: int):
    """El dueño cambia la temperatura a mano (queda fijada unos días)."""
    try:
        datos = cambiar_temperatura_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    try:
        detalle = _servicio().cambiar_temperatura(
            lead_id, datos["temperatura"], datos["motivo_perdida"], datos["motivo"], _usuario()
        )
    except LeadNoEncontradoError as exc:
        return jsonify(error=str(exc)), 404
    except DatosInvalidosError as exc:
        return jsonify(error=str(exc)), 422
    except (VentaYaCerradaError, OtroLeadAbiertoError) as exc:
        return jsonify(error=str(exc)), 409
    return jsonify(preparar_detalle(detalle)), 200


@contactos_bp.put("/<int:contacto_id>/no-contactar")
def no_contactar(contacto_id: int):
    """Marca o quita «no contactar» en el contacto (vale para todos sus canales)."""
    try:
        datos = no_contactar_input_schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="Datos inválidos.", detalle=exc.messages), 422
    try:
        _servicio().marcar_no_contactar(contacto_id, datos["no_contactar"], datos["motivo"], _usuario())
    except ContactoNoEncontradoError as exc:
        return jsonify(error=str(exc)), 404
    return jsonify(ok=True), 200
