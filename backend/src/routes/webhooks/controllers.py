import hmac

from flask import jsonify, request

from src.config.settings import load_settings

from . import webhooks_bp
from .services import WebhookService


@webhooks_bp.post("/rocketfy/<token>")
def recibir_evento_rocketfy(token: str):
    settings = load_settings()

    # Rocket no manda autenticación propia — el secreto va en la URL.
    # 403, nunca 404/405 (esos códigos bloquean el alta del webhook).
    if not hmac.compare_digest(token, settings.rocketfy_webhook_token):
        return jsonify(error="forbidden"), 403

    payload = request.get_json(silent=True) or {}

    # Ping de validación al dar de alta la URL: llega sin cuerpo.
    if not payload.get("order_id"):
        return jsonify(ok=True, ping=True), 200

    # Persistir y procesar; procesar_evento() nunca lanza (ver services.py).
    WebhookService().procesar_evento(payload)

    return jsonify(ok=True), 200
