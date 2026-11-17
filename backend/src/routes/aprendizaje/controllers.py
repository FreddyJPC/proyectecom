"""
API de «Aprendizaje de Victoria» (entrada 0.0.140):
- GET   /aprendizaje?estado=&tipo=&dias=&pagina=   -> casos, del más nuevo al más viejo
- GET   /aprendizaje/resumen?dias=                -> pendientes y conteo por tipo y por etapa
- PATCH /aprendizaje/<id>                          -> el dueño lo revisa: estado, categoría, acción y nota
"""
from typing import Optional

from flask import g, jsonify, request

from . import aprendizaje_bp
from . import logica
from .servicio import AprendizajeServicio, CasoNoEncontradoError, DatosInvalidosError


def _usuario() -> Optional[str]:
    return (getattr(g, "usuario", None) or {}).get("email")


def _entero(nombre: str, por_defecto: Optional[int]) -> Optional[int]:
    valor = request.args.get(nombre)
    if valor in (None, "", "todo"):
        return por_defecto
    try:
        return int(valor)
    except ValueError:
        return por_defecto


def _iso(valor):
    return valor.isoformat() if hasattr(valor, "isoformat") else valor


def _caso(fila: dict) -> dict:
    return {
        "id": fila["id"],
        "creadoEn": _iso(fila["creado_en"]),
        "conversacionId": fila.get("conversacion_id"),
        "leadId": fila.get("lead_id"),
        "cliente": fila.get("cliente"),
        "canal": fila.get("canal"),
        "tipo": fila["tipo"],
        "tipoNombre": logica.TIPOS.get(fila["tipo"], fila["tipo"]),
        "origen": fila["origen"],
        "motivo": fila["motivo"],
        "mensajeCliente": fila.get("mensaje_cliente"),
        "etapa": fila.get("etapa"),
        "productoSku": fila.get("producto_sku"),
        "mensajes": (fila.get("contexto") or {}).get("mensajes", []),
        "detalle": {k: v for k, v in (fila.get("contexto") or {}).items() if k != "mensajes"},
        "estado": fila["estado"],
        "categoria": fila.get("categoria"),
        "accion": fila.get("accion"),
        "nota": fila.get("nota"),
        "revisadoPor": fila.get("revisado_por"),
        "revisadoEn": _iso(fila.get("revisado_en")),
    }


@aprendizaje_bp.get("")
def listar_casos():
    try:
        datos = AprendizajeServicio().listar(
            request.args.get("estado") or None,
            request.args.get("tipo") or None,
            _entero("dias", None),
            _entero("pagina", 1),
            _entero("porPagina", 20),
        )
    except DatosInvalidosError as exc:
        return jsonify(error=str(exc)), 422
    return jsonify({**datos, "casos": [_caso(f) for f in datos["casos"]]}), 200


@aprendizaje_bp.get("/resumen")
def resumen():
    datos = AprendizajeServicio().resumen(_entero("dias", 30))
    return jsonify(
        pendientes=datos["pendientes"],
        total=datos["total"],
        porTipo=[{**f, "tipoNombre": logica.TIPOS.get(f["tipo"], f["tipo"])} for f in datos["por_tipo"]],
        porEtapa=datos["por_etapa"],
        tipos=[{"tipo": k, "nombre": v} for k, v in logica.TIPOS.items()],
        acciones=[{"accion": k, "nombre": v} for k, v in logica.ACCIONES.items()],
    ), 200


@aprendizaje_bp.patch("/<int:caso_id>")
def revisar_caso(caso_id: int):
    cuerpo = request.get_json(force=True, silent=True) or {}
    try:
        fila = AprendizajeServicio().revisar(
            caso_id, cuerpo.get("estado") or "", cuerpo.get("categoria"), cuerpo.get("accion"), cuerpo.get("nota"), _usuario()
        )
    except DatosInvalidosError as exc:
        return jsonify(error=str(exc)), 422
    except CasoNoEncontradoError as exc:
        return jsonify(error=str(exc)), 404
    return jsonify(_caso(fila)), 200
