"""
Lo que Meta manda cuando un cliente escribe tocando un anuncio de Click-to-WhatsApp: el objeto `referral`
(dentro del mensaje). Referencia de campos (documentación oficial de Meta):

    source_url, source_id, source_type ("ad" | "post"), headline, body, media_type ("image" | "video"),
    image_url (solo anuncios con imagen), video_url y thumbnail_url (solo con video), ctwa_clid
    (se omite en anuncios del Estado de WhatsApp), welcome_message {text}

Esta función es PURA: recibe el diccionario de Meta y devuelve los campos ya limpios para guardarlos. Nunca lanza:
el webhook no puede fallar por un campo raro de un anuncio.
"""
from typing import Any, Dict, Optional

# Meta puede mandar textos largos (el cuerpo de un anuncio); se corta para no guardar algo desmesurado.
_LARGO_TEXTO = 4000
_LARGO_URL = 2000
_LARGO_ID = 200


def _texto(valor: Any, largo: int = _LARGO_TEXTO) -> Optional[str]:
    if valor is None or isinstance(valor, (dict, list)):
        return None
    limpio = str(valor).strip()
    return limpio[:largo] if limpio else None


def _url(valor: Any) -> Optional[str]:
    """Solo enlaces http(s): estos datos se muestran como enlace o imagen en la app, y no se debe poder colar otro tipo."""
    texto = _texto(valor, _LARGO_URL)
    if texto and texto.lower().startswith(("https://", "http://")):
        return texto
    return None


def normalizar_referral(referral: Optional[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    """Campos del `referral` de Meta, listos para la tabla `conversacion_anuncios` (todos opcionales)."""
    datos = referral if isinstance(referral, dict) else {}
    bienvenida = datos.get("welcome_message")
    return {
        "id_anuncio": _texto(datos.get("source_id"), _LARGO_ID),
        "tipo_origen": _texto(datos.get("source_type"), 40),
        "url_anuncio": _url(datos.get("source_url")),
        "titulo": _texto(datos.get("headline")),
        "texto": _texto(datos.get("body")),
        "tipo_media": _texto(datos.get("media_type"), 40),
        "imagen_url": _url(datos.get("image_url")),
        "video_url": _url(datos.get("video_url")),
        "miniatura_url": _url(datos.get("thumbnail_url")),
        "ctwa_clid": _texto(datos.get("ctwa_clid"), _LARGO_ID),
        "mensaje_bienvenida": _texto(bienvenida.get("text")) if isinstance(bienvenida, dict) else None,
    }
