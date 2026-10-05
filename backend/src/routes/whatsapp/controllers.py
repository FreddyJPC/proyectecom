"""
Webhook de WhatsApp Cloud API (Meta). Mismo principio de diseño que el
webhook de Rocketfy (src/routes/webhooks/controllers.py): responder
siempre 200 lo más rápido posible, nunca propagar excepciones, idempotencia
por un identificador propio del proveedor (acá wamid, allá
order_id+status_id+event_date).

Diferencia con Rocketfy: acá la respuesta 200 se manda ANTES de cualquier
procesamiento -- Meta cancela y reintenta si no llega en ~5 segundos, y
generar+enviar la respuesta del bot puede tardar más que eso (ver
worker.py). El parseo del payload y la llamada a WebhookService ocurren en
un thread aparte, disparado después de responder.
"""
import hmac
import logging
import threading
from typing import List

from flask import jsonify, request

from src.config.settings import load_settings

from . import whatsapp_bp
from .dto import MensajeEntranteDTO
from .services import WebhookService

logger = logging.getLogger(__name__)


@whatsapp_bp.get("/whatsapp")
def verificar_webhook():
    """Handshake de verificación que Meta hace UNA vez al registrar/editar
    la URL del webhook en developers.facebook.com. Debe devolver el valor
    exacto de hub.challenge como texto plano, no como JSON."""
    settings = load_settings()
    modo = request.args.get("hub.mode", "")
    token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge", "")

    if modo == "subscribe" and hmac.compare_digest(token, settings.whatsapp_webhook_verify_token):
        return challenge, 200
    return jsonify(error="forbidden"), 403


@whatsapp_bp.post("/whatsapp")
def recibir_evento():
    mensajes = _extraer_mensajes(request.get_json(silent=True) or {})

    if mensajes:
        threading.Thread(target=_procesar_en_background, args=(mensajes,), daemon=True).start()

    return jsonify(status="ok"), 200


def _procesar_en_background(mensajes: List[MensajeEntranteDTO]) -> None:
    servicio = WebhookService()
    for dto in mensajes:
        servicio.procesar_mensaje_entrante(dto)


def _extraer_mensajes(payload: dict) -> List[MensajeEntranteDTO]:
    """Nunca lanza -- un payload vacío (ping de Meta) o con forma
    inesperada simplemente no produce mensajes que procesar."""
    mensajes = []
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                valor = change.get("value", {})
                for msg in valor.get("messages", []):
                    mensajes.append(_parsear_mensaje(msg))
    except Exception:
        logger.exception("Payload de webhook de WhatsApp con forma inesperada -- se ignora")
        return []
    return mensajes


def _parsear_mensaje(msg: dict) -> MensajeEntranteDTO:
    tipo_meta = msg.get("type", "text")
    if tipo_meta == "text":
        contenido = msg.get("text", {}).get("body", "")
        tipo = "texto"
    elif tipo_meta == "image":
        # Fase 3.1: sin transcripción/descripción real todavía -- se usa
        # el caption si viene, si no un placeholder. Revisar en Fase 3.2.
        contenido = msg.get("image", {}).get("caption") or "[imagen]"
        tipo = "imagen"
    elif tipo_meta == "audio":
        contenido = "[audio]"
        tipo = "audio"
    else:
        contenido = f"[mensaje tipo '{tipo_meta}' no soportado todavía]"
        tipo = "texto"

    return MensajeEntranteDTO(
        wamid=msg["id"],
        telefono=msg["from"],
        contenido=contenido,
        tipo=tipo,
        referral=msg.get("referral"),
    )
