from flask import jsonify, request

from . import incidencias_bp
from .schemas import alerta_stock_schema, evento_webhook_schema
from .services import IncidenciasService


def _build_service() -> IncidenciasService:
    return IncidenciasService()


@incidencias_bp.get("/eventos")
def eventos_webhook():
    """Fase 2 - Etapa 3. Por defecto solo trae NOVEDAD/DEVUELTO_EN_TRANSITO
    (lo que de verdad necesita atención humana, directriz 17) -- ?todos=true
    trae el historial completo de webhook_events."""
    solo_incidencias = request.args.get("todos", "false").lower() != "true"
    page = request.args.get("page", 1, type=int)
    page_size = min(request.args.get("pageSize", 20, type=int), 100)

    resultado = _build_service().listar_eventos(solo_incidencias=solo_incidencias, page=page, page_size=page_size)
    return jsonify(
        items=[evento_webhook_schema.dump(fila) for fila in resultado["items"]],
        total=resultado["total"],
        page=resultado["page"],
        pageSize=resultado["page_size"],
    ), 200


@incidencias_bp.get("/stock")
def alertas_stock():
    sku = request.args.get("sku")
    page = request.args.get("page", 1, type=int)
    page_size = min(request.args.get("pageSize", 20, type=int), 100)

    resultado = _build_service().listar_alertas(sku=sku, page=page, page_size=page_size)
    return jsonify(
        items=[alerta_stock_schema.dump(fila) for fila in resultado["items"]],
        total=resultado["total"],
        page=resultado["page"],
        pageSize=resultado["page_size"],
    ), 200
