"""Todos los tipos de mensaje de WhatsApp (fase F1 de docs/PLAN_IMAGENES_AUDIO.md)."""
import pytest

from src.routes.whatsapp.controllers import _extraer_mensajes, _parsear_mensaje


def _msg(tipo, cuerpo=None, **extra):
    base = {"id": "wamid.X", "from": "593987654321", "type": tipo}
    if cuerpo is not None:
        base[tipo] = cuerpo
    base.update(extra)
    return base


class TestParsear:
    def test_texto(self):
        dto = _parsear_mensaje(_msg("text", {"body": "hola"}))
        assert (dto.tipo, dto.contenido, dto.media_id) == ("texto", "hola", None)

    def test_imagen_guarda_el_archivo_y_el_pie_de_foto(self):
        dto = _parsear_mensaje(_msg("image", {"id": "M1", "mime_type": "image/jpeg", "caption": "mi comprobante"}))
        assert (dto.tipo, dto.contenido, dto.media_id, dto.media_mime) == ("imagen", "mi comprobante", "M1", "image/jpeg")

    def test_imagen_sin_pie_de_foto(self):
        assert _parsear_mensaje(_msg("image", {"id": "M1", "mime_type": "image/png"})).contenido == "[imagen]"

    def test_audio_guarda_el_archivo(self):
        dto = _parsear_mensaje(_msg("audio", {"id": "A1", "mime_type": "audio/ogg; codecs=opus", "voice": True}))
        assert (dto.tipo, dto.media_id, dto.media_mime) == ("audio", "A1", "audio/ogg; codecs=opus")

    def test_documento_con_nombre(self):
        dto = _parsear_mensaje(_msg("document", {"id": "D1", "mime_type": "application/pdf", "filename": "comprobante.pdf"}))
        assert dto.tipo == "documento" and dto.media_nombre == "comprobante.pdf" and "comprobante.pdf" in dto.contenido

    def test_ubicacion_deja_un_enlace_al_mapa(self):
        dto = _parsear_mensaje(_msg("location", {"latitude": -0.18, "longitude": -78.47, "name": "Mi casa", "address": "Av. Amazonas"}))
        assert dto.tipo == "ubicacion"
        assert "Mi casa, Av. Amazonas" in dto.contenido and "https://maps.google.com/?q=-0.18,-78.47" in dto.contenido

    def test_ubicacion_sin_coordenadas_no_rompe(self):
        assert "sin coordenadas" in _parsear_mensaje(_msg("location", {})).contenido

    def test_sticker_y_contacto_y_video(self):
        assert _parsear_mensaje(_msg("sticker", {"id": "S"})).tipo == "sticker"
        assert _parsear_mensaje(_msg("contacts", [{}])).tipo == "contacto"
        video = _parsear_mensaje(_msg("video", {"id": "V1", "mime_type": "video/mp4"}))
        assert (video.tipo, video.media_id) == ("video", "V1")

    def test_reaccion_con_emoji(self):
        dto = _parsear_mensaje(_msg("reaction", {"message_id": "w", "emoji": "👍"}))
        assert dto.tipo == "reaccion" and "👍" in dto.contenido

    def test_reaccion_quitada_no_se_procesa(self):
        assert _parsear_mensaje(_msg("reaction", {"message_id": "w", "emoji": ""})) is None

    @pytest.mark.parametrize("interactivo", [{"button_reply": {"id": "1", "title": "Sí"}}, {"list_reply": {"id": "1", "title": "Sí"}}])
    def test_respuesta_de_boton_es_texto(self, interactivo):
        dto = _parsear_mensaje(_msg("interactive", interactivo))
        assert (dto.tipo, dto.contenido) == ("texto", "Sí")

    def test_boton_de_plantilla(self):
        dto = _parsear_mensaje(_msg("button", {"text": "Sí, me interesa", "payload": "p"}))
        assert (dto.tipo, dto.contenido) == ("texto", "Sí, me interesa")

    def test_un_tipo_desconocido_sigue_siendo_texto_con_aviso(self):
        dto = _parsear_mensaje(_msg("order", {}))
        assert dto.tipo == "texto" and "no soportado" in dto.contenido


class TestExtraer:
    def test_las_reacciones_quitadas_se_descartan_y_el_resto_sigue(self):
        payload = {"entry": [{"changes": [{"value": {"messages": [
            _msg("reaction", {"message_id": "w", "emoji": ""}), _msg("text", {"body": "hola"}, id="wamid.Y"),
        ]}}]}]}
        assert [m.contenido for m in _extraer_mensajes(payload)] == ["hola"]
