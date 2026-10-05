from flask import jsonify

from src.integrations.rocketfy import RocketfyAuthError, RocketfyBusinessError, RocketfyRequestError, get_rocketfy_client

from . import metricas_bp
from .schemas import metricas_generales_response_schema

_ERRORES_ROCKETFY = (RocketfyAuthError, RocketfyBusinessError, RocketfyRequestError)

AVISO_NO_ES_SALDO_WALLET = (
    "Estos son agregados operativos de Rocketfy (pedidos y montos por estado), "
    "NO el saldo real de tu billetera. El detalle de liquidaciones y el saldo "
    "disponible para retiro requieren endpoints que Rocketfy aún no expone para "
    "vendedores (ver sección 10.2 del doc del proveedor y ADR-003 en PROGRESS.md)."
)


@metricas_bp.get("/generales")
def metricas_generales():
    """Requerimiento 6, PARCIAL. Cubre GET /api/statistics/general."""
    try:
        contenido = get_rocketfy_client().estadisticas_generales()
    except _ERRORES_ROCKETFY as exc:
        return jsonify(error=str(exc)), 502

    respuesta = metricas_generales_response_schema.dump(contenido)
    respuesta["avisoImportante"] = AVISO_NO_ES_SALDO_WALLET
    return jsonify(respuesta), 200
