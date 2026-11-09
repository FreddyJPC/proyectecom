"""Lo que Meta manda en `referral` (Click-to-WhatsApp) y cómo se limpia para guardarlo."""
from src.routes.anuncios.referral import normalizar_referral

# Forma documentada por Meta (todos los campos del objeto `referral`).
REFERRAL_COMPLETO = {
    "source_url": "https://fb.me/abc",
    "source_id": "23847382910",
    "source_type": "ad",
    "body": "Cancelación de ruido y 30 h de batería",
    "headline": "Audífonos Pro",
    "media_type": "video",
    "video_url": "https://video.fb/x.mp4",
    "thumbnail_url": "https://cdn.fb/mini.jpg",
    "ctwa_clid": "AR-click-1",
    "welcome_message": {"text": "¡Hola! ¿En qué te ayudamos?"},
}


def test_guarda_todos_los_campos_documentados_por_meta():
    datos = normalizar_referral(REFERRAL_COMPLETO)

    assert datos == {
        "id_anuncio": "23847382910",
        "tipo_origen": "ad",
        "url_anuncio": "https://fb.me/abc",
        "titulo": "Audífonos Pro",
        "texto": "Cancelación de ruido y 30 h de batería",
        "tipo_media": "video",
        "imagen_url": None,
        "video_url": "https://video.fb/x.mp4",
        "miniatura_url": "https://cdn.fb/mini.jpg",
        "ctwa_clid": "AR-click-1",
        "mensaje_bienvenida": "¡Hola! ¿En qué te ayudamos?",
    }


def test_un_anuncio_de_imagen_guarda_la_imagen():
    datos = normalizar_referral({"source_id": "1", "media_type": "image", "image_url": "https://cdn.fb/i.jpg"})
    assert datos["imagen_url"] == "https://cdn.fb/i.jpg"
    assert datos["video_url"] is None


def test_un_anuncio_del_estado_de_whatsapp_no_trae_ctwa_clid_y_no_rompe():
    datos = normalizar_referral({"source_id": "9", "source_type": "ad", "headline": "Oferta"})
    assert datos["ctwa_clid"] is None
    assert datos["id_anuncio"] == "9"


def test_el_id_numerico_se_guarda_como_texto():
    assert normalizar_referral({"source_id": 23847382910})["id_anuncio"] == "23847382910"


def test_solo_se_aceptan_enlaces_http_o_https():
    """Esos datos se muestran como enlace o imagen en la app: no se debe poder colar otro tipo de enlace."""
    datos = normalizar_referral(
        {"source_url": "javascript:alert(1)", "image_url": "data:image/png;base64,AAA", "thumbnail_url": "ftp://x/y", "video_url": "HTTPS://ok.com/v"}
    )
    assert datos["url_anuncio"] is None
    assert datos["imagen_url"] is None
    assert datos["miniatura_url"] is None
    assert datos["video_url"] == "HTTPS://ok.com/v"


def test_los_textos_vacios_o_con_espacios_quedan_en_none():
    datos = normalizar_referral({"headline": "   ", "body": "", "source_id": " 55 "})
    assert datos["titulo"] is None and datos["texto"] is None
    assert datos["id_anuncio"] == "55"


def test_los_textos_larguisimos_se_cortan():
    assert len(normalizar_referral({"body": "x" * 50_000})["texto"]) == 4000


def test_nunca_lanza_con_formas_inesperadas():
    assert normalizar_referral(None)["id_anuncio"] is None
    assert normalizar_referral("no es un diccionario")["id_anuncio"] is None  # type: ignore[arg-type]
    datos = normalizar_referral({"source_id": {"anidado": 1}, "welcome_message": "texto suelto", "headline": ["lista"]})
    assert datos["id_anuncio"] is None and datos["mensaje_bienvenida"] is None and datos["titulo"] is None
