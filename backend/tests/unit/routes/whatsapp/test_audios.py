"""Audios (fase F3 de docs/PLAN_IMAGENES_AUDIO.md): se pasan a texto con un servicio de transcripción; sin él, Victoria pide que escriban."""
import pytest
import responses

from src.integrations.transcripcion.contratos import TranscripcionError
from src.integrations.transcripcion.proveedor_openai import OpenAITranscriptionProvider
from tests.unit.routes.whatsapp.test_imagenes import CanalesFalsos, MensajesConArchivos, _fin, _servicio
from tests.unit.routes.whatsapp.test_conversation_service import LLMProviderFalso


def _audio(media_id="A1", mime="audio/ogg; codecs=opus", **extra):
    return {"rol": "cliente", "tipo": "audio", "contenido": "[audio]", "media_id": media_id, "media_mime": mime, **extra}


class TranscriptorFalso:
    def __init__(self, texto="quiero dos audífonos negros", error=None):
        self.texto, self.error, self.llamadas = texto, error, []

    def transcribir(self, audio, mime, idioma="es"):
        self.llamadas.append((audio, mime))
        if self.error:
            raise self.error
        return self.texto


@pytest.fixture
def audios_encendidos(monkeypatch):
    from src.config.parametros import parametros

    real = parametros.valor
    monkeypatch.setattr(parametros, "valor", lambda c: True if c == "bot.entender_audios" else real(c))


def _correr(mensajes, transcriptor, canales=None):
    llm = LLMProviderFalso([_fin()])
    servicio = _servicio(llm, mensajes, canales or CanalesFalsos())
    servicio._transcriptor_fijo = transcriptor
    servicio.procesar_turno(1, "")
    return llm.llamadas[0]["mensajes"][-1].texto


class TestConElServicioEncendido:
    def test_el_audio_llega_a_victoria_como_texto_y_queda_guardado(self, audios_encendidos):
        mensajes, transcriptor = MensajesConArchivos([_audio()]), TranscriptorFalso()
        texto = _correr(mensajes, transcriptor)
        assert texto == "[audio transcrito] quiero dos audífonos negros"
        assert mensajes.analisis[1] == "quiero dos audífonos negros"
        assert transcriptor.llamadas[0][1] == "audio/ogg; codecs=opus"

    def test_un_audio_ya_transcrito_no_se_vuelve_a_pagar(self, audios_encendidos):
        transcriptor = TranscriptorFalso()
        texto = _correr(MensajesConArchivos([_audio(analisis="ya lo había dicho")]), transcriptor)
        assert texto == "[audio transcrito] ya lo había dicho" and transcriptor.llamadas == []

    def test_texto_y_audio_juntos(self, audios_encendidos):
        texto = _correr(MensajesConArchivos([{"rol": "cliente", "contenido": "hola"}, _audio()]), TranscriptorFalso("me llamo Ana"))
        assert texto == "hola\n[audio transcrito] me llamo Ana"

    def test_si_la_transcripcion_falla_se_le_dice_a_victoria(self, audios_encendidos):
        texto = _correr(MensajesConArchivos([_audio()]), TranscriptorFalso(error=TranscripcionError("caído")))
        assert "no se pudo escuchar" in texto

    def test_si_la_descarga_falla_tambien(self, audios_encendidos):
        texto = _correr(MensajesConArchivos([_audio()]), TranscriptorFalso(), CanalesFalsos(error=RuntimeError("Meta caído")))
        assert "no se pudo escuchar" in texto

    @pytest.mark.parametrize("dicho", ["", "  ", "a"])
    def test_un_audio_sin_voz_clara_no_se_toma_por_texto(self, audios_encendidos, dicho):
        texto = _correr(MensajesConArchivos([_audio()]), TranscriptorFalso(dicho))
        assert "sin voz clara" in texto

    @pytest.mark.parametrize("dicho", ["", "no se pudo"])
    def test_el_audio_que_no_se_entiende_le_pide_a_victoria_decirlo_y_pedir_otro(self, audios_encendidos, dicho):
        """Lo pidió Freddy: ante un audio ilegible, Victoria dice que no lo entendió y pide enviarlo de nuevo o escribirlo."""
        falla = TranscriptorFalso(error=TranscripcionError("x")) if dicho else TranscriptorFalso(dicho)
        texto = _correr(MensajesConArchivos([_audio()]), falla)
        assert "no lograste entender el audio" in texto
        assert "donde se escuche mejor" in texto
        assert "no adivines" in texto

    def test_sin_servicio_configurado_se_pide_que_escriba(self, audios_encendidos, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        llm = LLMProviderFalso([_fin()])
        _servicio(llm, MensajesConArchivos([_audio()]), CanalesFalsos()).procesar_turno(1, "")
        assert "no pudiste escuchar" in llm.llamadas[0]["mensajes"][-1].texto

    def test_el_tope_de_tamano_viene_del_parametro(self, audios_encendidos):
        canales = CanalesFalsos()
        _correr(MensajesConArchivos([_audio()]), TranscriptorFalso(), canales)
        assert canales.pedidos[0][1] == 3 * 1024 * 1024


class TestApagado:
    def test_por_defecto_viene_apagado_y_no_se_baja_ni_se_paga_nada(self):
        from src.config.parametros import parametros

        assert parametros.valor("bot.entender_audios") is False
        canales, transcriptor = CanalesFalsos(), TranscriptorFalso()
        texto = _correr(MensajesConArchivos([_audio()]), transcriptor, canales)
        assert "no pudiste escuchar" in texto and canales.pedidos == [] and transcriptor.llamadas == []

    def test_el_modelo_por_defecto_es_el_economico(self):
        from src.config.parametros import parametros

        assert parametros.valor("bot.modelo_transcripcion") == "gpt-4o-mini-transcribe"


class TestProveedorOpenAI:
    URL = "https://api.openai.com/v1/audio/transcriptions"

    @responses.activate
    def test_manda_el_audio_con_la_clave_el_modelo_y_el_idioma(self):
        responses.add(responses.POST, self.URL, json={"text": "  hola, quiero comprar  "}, status=200)
        texto = OpenAITranscriptionProvider("sk-prueba", "gpt-4o-mini-transcribe").transcribir(b"OggS...", "audio/ogg; codecs=opus")
        peticion = responses.calls[0].request
        assert texto == "hola, quiero comprar"
        assert peticion.headers["Authorization"] == "Bearer sk-prueba"
        cuerpo = peticion.body if isinstance(peticion.body, bytes) else peticion.body.read()
        assert b'name="model"' in cuerpo and b"gpt-4o-mini-transcribe" in cuerpo and b'filename="audio.ogg"' in cuerpo and b"es" in cuerpo

    @responses.activate
    def test_un_formato_no_soportado_ni_siquiera_se_envia(self):
        with pytest.raises(TranscripcionError, match="no soportado"):
            OpenAITranscriptionProvider("k", "m").transcribir(b"x", "audio/amr")
        assert len(responses.calls) == 0

    @responses.activate
    @pytest.mark.parametrize("estado, frase", [(401, "rechazó la clave"), (500, "HTTP 500")])
    def test_errores_del_servicio(self, estado, frase):
        responses.add(responses.POST, self.URL, json={}, status=estado)
        with pytest.raises(TranscripcionError, match=frase):
            OpenAITranscriptionProvider("k", "m").transcribir(b"x", "audio/ogg")

    def test_sin_clave_no_hay_transcriptor(self, monkeypatch):
        from src.integrations.transcripcion import get_transcriptor

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert get_transcriptor() is None
        monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
        assert get_transcriptor() is not None
