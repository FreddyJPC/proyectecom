"""
Conexión con Meta (ADR-016, docs/PLAN_META_ADS.md): estado de la configuración y el botón «Preparar Meta».

«Preparar Meta» le pide a Meta el dataset (el buzón donde se reciben las compras) de la cuenta de WhatsApp, con el token que vive en el
servidor, y guarda su número. Así nadie tiene que ver ni copiar el token. Repetirlo es seguro: según la documentación de Meta, si el dataset
ya existe devuelve el mismo. Esta ruta NUNCA devuelve el token ni lo escribe en un error.
"""
import logging

from flask import g, jsonify

from src.integrations.meta import MetaRechazoError, MetaRespuestaDudosaError
from src.integrations.meta import factory as meta_factory
from src.config.parametros import parametros

from . import meta_bp
from .repository import MetaRepository

logger = logging.getLogger(__name__)


def _cliente_para_dataset():
    """Separado para poder cambiarlo en las pruebas."""
    return meta_factory.get_cliente_para_dataset()


def _usuario():
    return (getattr(g, "usuario", None) or {}).get("email")


def _jsonable(fila: dict) -> dict:
    return {
        "id": fila["id"],
        "ventaId": fila["venta_id"],
        "estado": fila["estado"],
        "motivo": fila.get("motivo"),
        "valor": str(fila["valor"]),  # el dinero viaja siempre como texto
        "moneda": fila["moneda"],
        "intentos": fila["intentos"],
        "creadoEn": fila["creado_en"].isoformat() if fila.get("creado_en") else None,
        "enviadoEn": fila["enviado_en"].isoformat() if fila.get("enviado_en") else None,
    }


@meta_bp.get("/estado")
def estado():
    dataset = meta_factory.dataset_id()
    return (
        jsonify(
            tokenConfigurado=meta_factory.token_configurado(),
            cuentaWhatsappConfigurada=meta_factory.cuenta_whatsapp_configurada(),
            datasetId=dataset,
            listo=bool(meta_factory.token_configurado() and meta_factory.cuenta_whatsapp_configurada() and dataset),
            avisosActivos=bool(parametros.valor("meta.activo")),
            eventos=MetaRepository.resumen_eventos(),
            ultimosEventos=[_jsonable(f) for f in MetaRepository.ultimos_eventos()],
        ),
        200,
    )


@meta_bp.post("/preparar")
def preparar():
    cliente, ausentes = _cliente_para_dataset()
    if cliente is None:
        return jsonify(error="Falta configurar en el servidor: " + ", ".join(ausentes) + "."), 409
    try:
        dataset_id = cliente.obtener_o_crear_dataset()
    except MetaRechazoError as exc:
        logger.warning("Meta no entregó el dataset: %s", exc)
        return jsonify(error=str(exc)), 502
    except MetaRespuestaDudosaError as exc:
        logger.warning("Respuesta dudosa de Meta al pedir el dataset: %s", exc)
        return jsonify(error=f"{exc}. Puedes volver a intentarlo: pedir el dataset es seguro de repetir."), 502
    MetaRepository.guardar_dataset_id(dataset_id)
    logger.info("Dataset de Meta preparado por %s (id %s)", _usuario() or "desconocido", dataset_id)
    return jsonify(datasetId=dataset_id), 200
