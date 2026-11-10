"""
Webhook de WhatsApp Cloud API (Meta). Mismo principio de diseño que el
webhook de Rocketfy (src/routes/webhooks/controllers.py): responder
siempre 200 lo más rápido posible, nunca propagar excepciones, idempotencia
por un identificador propio del proveedor (acá wamid, allá
order_id+status_id+event_date).

Autenticación: cada POST debe traer la firma `X-Hub-Signature-256` de Meta
(HMAC-SHA256 del cuerpo con el App Secret); si no coincide, 401 y no se
procesa nada. Es el único caso en que este webhook responde distinto de
200, y es a propósito: Meta no puede estar enviando una firma mala.

Diferencia con Rocketfy: acá la respuesta 200 se manda ANTES de cualquier
procesamiento -- Meta cancela y reintenta si no llega en ~5 segundos, y
generar+enviar la respuesta del bot puede tardar más que eso (ver
worker.py). El parseo del payload y la llamada a WebhookService ocurren en
un thread aparte, disparado después de responder.
"""
import hashlib
import hmac
import logging
import threading
from typing import List, Optional

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


def _firma_valida(cuerpo: bytes, cabecera: str, app_secret: str) -> bool:
    """Meta firma cada POST con HMAC-SHA256 del cuerpo crudo usando el App
    Secret, y manda el resultado en `X-Hub-Signature-256: sha256=<hex>`.
    Se compara en tiempo constante. El cuerpo debe ser el crudo, byte a
    byte, sin pasar por json."""
    if not cabecera.startswith("sha256="):
        return False
    esperada = hmac.new(app_secret.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(cabecera.removeprefix("sha256="), esperada)


@whatsapp_bp.post("/whatsapp")
def recibir_evento():
    settings = load_settings()
    if not settings.whatsapp_skip_signature:
        if not settings.whatsapp_app_secret:
            # Falla cerrado: sin App Secret no hay forma de saber si el
            # POST viene de Meta, así que no se procesa nada.
            logger.error("WHATSAPP_APP_SECRET no está configurado -- se rechaza el POST al webhook de WhatsApp")
            return jsonify(error="webhook sin configurar"), 401
        cabecera = request.headers.get("X-Hub-Signature-256", "")
        if not _firma_valida(request.get_data(), cabecera, settings.whatsapp_app_secret):
            logger.warning("POST al webhook de WhatsApp con firma inválida o ausente -- se rechaza")
            return jsonify(error="firma inválida"), 401

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
                # `contacts` trae el nombre de perfil de quien escribe (`wa_id` es su teléfono). Es opcional.
                nombres = {
                    c.get("wa_id"): (c.get("profile") or {}).get("name")
                    for c in valor.get("contacts", [])
                    if isinstance(c, dict)
                }
                for msg in valor.get("messages", []):
                    dto = _parsear_mensaje(msg, nombres.get(msg.get("from")))
                    if dto is not None:
                        mensajes.append(dto)
    except Exception:
        logger.exception("Payload de webhook de WhatsApp con forma inesperada -- se ignora")
        return []
    return mensajes


def _enlace_al_mapa(latitud, longitud) -> str:
    return f"https://maps.google.com/?q={latitud},{longitud}"


def _parsear_mensaje(msg: dict, nombre_perfil: Optional[str] = None) -> Optional[MensajeEntranteDTO]:
    """Convierte un mensaje de Meta en nuestro formato. Devuelve None para lo que no hay que procesar (p. ej. una reacción que el
    cliente quitó). Los archivos (foto, audio, documento) quedan con su `media_id` para bajarlos después; ver el plan en
    docs/PLAN_IMAGENES_AUDIO.md."""
    tipo_meta = msg.get("type", "text")
    media_id = media_mime = media_nombre = None

    if tipo_meta == "text":
        contenido = msg.get("text", {}).get("body", "")
        tipo = "texto"
    elif tipo_meta == "image":
        imagen = msg.get("image", {})
        contenido = imagen.get("caption") or "[imagen]"
        tipo, media_id, media_mime = "imagen", imagen.get("id"), imagen.get("mime_type")
    elif tipo_meta == "audio":
        audio = msg.get("audio", {})
        contenido = "[audio]"
        tipo, media_id, media_mime = "audio", audio.get("id"), audio.get("mime_type")
    elif tipo_meta == "document":
        documento = msg.get("document", {})
        media_nombre = documento.get("filename")
        contenido = documento.get("caption") or f"[documento{': ' + media_nombre if media_nombre else ''}]"
        tipo, media_id, media_mime = "documento", documento.get("id"), documento.get("mime_type")
    elif tipo_meta == "video":
        video = msg.get("video", {})
        contenido = video.get("caption") or "[video]"
        tipo, media_id, media_mime = "video", video.get("id"), video.get("mime_type")
    elif tipo_meta == "sticker":
        contenido = "[sticker]"
        tipo = "sticker"
    elif tipo_meta == "location":
        ubicacion = msg.get("location", {})
        if ubicacion.get("latitude") is None or ubicacion.get("longitude") is None:
            contenido = "[ubicación compartida sin coordenadas]"
        else:
            nombre = ", ".join(p for p in (ubicacion.get("name"), ubicacion.get("address")) if p)
            contenido = f"[Ubicación compartida{': ' + nombre if nombre else ''} — {_enlace_al_mapa(ubicacion['latitude'], ubicacion['longitude'])}]"
        tipo = "ubicacion"
    elif tipo_meta == "reaction":
        emoji = (msg.get("reaction") or {}).get("emoji")
        if not emoji:  # el cliente quitó su reacción: no hay nada que procesar
            return None
        contenido = f"[reaccionó con {emoji} a un mensaje]"
        tipo = "reaccion"
    elif tipo_meta == "contacts":
        contenido = "[contacto compartido]"
        tipo = "contacto"
    elif tipo_meta == "interactive":
        # Respuesta a un botón o a una lista: lo que el cliente tocó es su respuesta, como si la hubiera escrito.
        interactivo = msg.get("interactive", {})
        elegido = interactivo.get("button_reply") or interactivo.get("list_reply") or {}
        contenido = elegido.get("title") or "[respuesta de botón]"
        tipo = "texto"
    elif tipo_meta == "button":
        contenido = (msg.get("button") or {}).get("text") or "[respuesta de botón]"
        tipo = "texto"
    else:
        contenido = f"[mensaje tipo '{tipo_meta}' no soportado todavía]"
        tipo = "texto"

    return MensajeEntranteDTO(
        wamid=msg["id"],
        id_externo=msg["from"],
        contenido=contenido,
        tipo=tipo,
        canal="whatsapp",
        nombre_perfil=nombre_perfil or None,
        media_id=media_id,
        media_mime=media_mime,
        media_nombre=media_nombre,
        referral=msg.get("referral"),
    )
