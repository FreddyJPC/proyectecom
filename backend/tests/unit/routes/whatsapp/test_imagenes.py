"""
Victoria ve las fotos y PDF del cliente (fase F2 de docs/PLAN_IMAGENES_AUDIO.md): llegan a la IA como imágenes, un comprobante de pago
se registra SIN darse por pagado, y todo lo que falle se le explica a Victoria en vez de callarse.
"""
import base64
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.integrations.llm.contratos import AdjuntoLLM, LlamadaHerramienta, MensajeLLM, RespuestaLLM
from src.integrations.llm.providers.anthropic_provider import AnthropicProvider
from src.routes.whatsapp.conversation_service import VictoriaConversationService
from src.routes.whatsapp.tools import _leer_monto
from tests.unit.routes.whatsapp.test_conversation_service import (
    EjecutorHerramientasFalso,
    FakeConversacionRepository,
    FakeLeadRepository,
    FakeProductoBotRepository,
    LLMProviderFalso,
)
from tests.unit.routes.whatsapp.test_tools import FakeLeadRepository as FakeLeadsDeHerramientas, _herramientas

FOTO = b"\xff\xd8\xff\xe0fotodeprueba"


class MensajesConArchivos:
    def __init__(self, filas):
        self.filas = [{"id": i + 1, "creado_en": i + 1, "tipo": "texto", **f} for i, f in enumerate(filas)]
        self.analisis = {}

    def obtener_por_conversacion(self, conversacion_id):
        return self.filas

    def crear(self, conversacion_id, rol, contenido, tipo="texto", wamid=None, creado_en=None, **kw):
        self.filas.append({"id": len(self.filas) + 1, "creado_en": len(self.filas) + 1, "rol": rol, "contenido": contenido, "tipo": tipo})

    def guardar_analisis(self, mensaje_id, analisis):
        self.analisis[mensaje_id] = analisis


class CanalesFalsos:
    """Un registro de canales cuyo WhatsApp entrega la foto de prueba (o falla)."""

    def __init__(self, error=None, datos=FOTO):
        self.error, self.datos, self.pedidos = error, datos, []

    def para(self, canal):
        return self

    def descargar_media(self, media_id, max_bytes):
        self.pedidos.append((media_id, max_bytes))
        if self.error:
            raise self.error
        return self.datos, "image/jpeg"


def _imagen(media_id="M1", mime="image/jpeg", contenido="[imagen]", **extra):
    return {"rol": "cliente", "tipo": "imagen", "contenido": contenido, "media_id": media_id, "media_mime": mime, **extra}


def _servicio(llm, mensajes, canales):
    return VictoriaConversationService(
        llm_client=llm,
        lead_repo=FakeLeadRepository(),
        conversacion_repo=FakeConversacionRepository({1: {"id": 1, "contacto_id": 1, "telefono": "593987654321", "canal": "whatsapp", "id_anuncio": None}}),
        mensaje_repo=mensajes,
        producto_repo=FakeProductoBotRepository(),
        ejecutor_herramientas=EjecutorHerramientasFalso(),
        max_turnos_herramientas=5,
        max_mensajes_historial=40,
        canales=canales,
    )


def _fin(texto="ok"):
    return RespuestaLLM(texto=texto, llamadas_herramientas=[], razon_de_parada="fin")


class TestProveedorTraduceImagenes:
    def test_los_archivos_van_antes_del_texto_como_bloques_de_imagen_y_documento(self):
        traducido = AnthropicProvider._traducir_mensajes([
            MensajeLLM(rol="user", texto="[imagen adjunta]", adjuntos=[
                AdjuntoLLM(tipo="imagen", mime="image/png", datos_base64="AAA"),
                AdjuntoLLM(tipo="documento", mime="application/pdf", datos_base64="BBB"),
            ])
        ])
        contenido = traducido[0]["content"]
        assert [b["type"] for b in contenido] == ["image", "document", "text"]
        assert contenido[0]["source"] == {"type": "base64", "media_type": "image/png", "data": "AAA"}
        assert contenido[1]["source"]["media_type"] == "application/pdf"

    def test_un_mensaje_sin_archivos_sigue_siendo_texto_simple(self):
        assert AnthropicProvider._traducir_mensajes([MensajeLLM(rol="user", texto="hola")]) == [{"role": "user", "content": "hola"}]


class TestLaIaVeLaFoto:
    def test_la_foto_se_baja_y_llega_a_la_ia_como_adjunto(self):
        mensajes = MensajesConArchivos([_imagen()])
        canales, llm = CanalesFalsos(), LLMProviderFalso([_fin()])

        _servicio(llm, mensajes, canales).procesar_turno(1, "")

        enviado = llm.llamadas[0]["mensajes"][-1]
        assert len(enviado.adjuntos) == 1 and enviado.adjuntos[0].mime == "image/jpeg"
        assert base64.b64decode(enviado.adjuntos[0].datos_base64) == FOTO
        assert enviado.texto == "[imagen adjunta]" and canales.pedidos[0][0] == "M1"

    def test_el_pie_de_foto_acompana_a_la_imagen(self):
        mensajes = MensajesConArchivos([_imagen(contenido="este es mi comprobante")])
        llm = LLMProviderFalso([_fin()])
        _servicio(llm, mensajes, CanalesFalsos()).procesar_turno(1, "")
        assert llm.llamadas[0]["mensajes"][-1].texto == "[imagen adjunta] este es mi comprobante"

    def test_texto_y_foto_en_la_misma_racha_van_juntos(self):
        mensajes = MensajesConArchivos([
            {"rol": "cliente", "contenido": "ya pagué"}, _imagen(), {"rol": "cliente", "contenido": "ahí va"},
        ])
        llm = LLMProviderFalso([_fin()])
        _servicio(llm, mensajes, CanalesFalsos()).procesar_turno(1, "")
        enviado = llm.llamadas[0]["mensajes"][-1]
        assert enviado.texto == "ya pagué\n[imagen adjunta]\nahí va" and len(enviado.adjuntos) == 1

    def test_un_pdf_tambien_se_entrega(self):
        mensajes = MensajesConArchivos([{"rol": "cliente", "tipo": "documento", "contenido": "[documento: pago.pdf]", "media_id": "D1", "media_mime": "application/pdf", "media_nombre": "pago.pdf"}])
        llm = LLMProviderFalso([_fin()])
        _servicio(llm, mensajes, CanalesFalsos()).procesar_turno(1, "")
        enviado = llm.llamadas[0]["mensajes"][-1]
        assert enviado.adjuntos[0].tipo == "documento" and "pago.pdf" in enviado.texto

    def test_solo_se_miran_las_fotos_mas_recientes_hasta_el_tope(self):
        mensajes = MensajesConArchivos([_imagen(media_id=f"M{i}") for i in range(1, 6)])  # el tope por defecto es 3
        canales, llm = CanalesFalsos(), LLMProviderFalso([_fin()])
        _servicio(llm, mensajes, canales).procesar_turno(1, "")
        assert [p[0] for p in canales.pedidos] == ["M3", "M4", "M5"]
        assert "pasó el tope" in llm.llamadas[0]["mensajes"][-1].texto

    def test_con_la_funcion_apagada_no_se_baja_nada_y_victoria_lo_sabe(self, monkeypatch):
        from src.config.parametros import parametros

        real = parametros.valor
        monkeypatch.setattr(parametros, "valor", lambda c: False if c == "bot.entender_imagenes" else real(c))
        canales, llm = CanalesFalsos(), LLMProviderFalso([_fin()])
        _servicio(llm, MensajesConArchivos([_imagen()]), canales).procesar_turno(1, "")
        assert canales.pedidos == [] and llm.llamadas[0]["mensajes"][-1].adjuntos == []
        assert "apagada" in llm.llamadas[0]["mensajes"][-1].texto

    def test_si_la_descarga_falla_no_se_calla_y_se_le_explica_a_victoria(self):
        llm = LLMProviderFalso([_fin()])
        _servicio(llm, MensajesConArchivos([_imagen()]), CanalesFalsos(error=RuntimeError("Meta caído"))).procesar_turno(1, "")
        enviado = llm.llamadas[0]["mensajes"][-1]
        assert enviado.adjuntos == [] and "no se pudo abrir" in enviado.texto

    @pytest.mark.parametrize("mime", ["image/heic", "application/zip", ""])
    def test_un_formato_que_la_ia_no_acepta_no_se_baja(self, mime):
        canales, llm = CanalesFalsos(), LLMProviderFalso([_fin()])
        _servicio(llm, MensajesConArchivos([_imagen(mime=mime)]), canales).procesar_turno(1, "")
        assert canales.pedidos == [] and "no puedes abrir" in llm.llamadas[0]["mensajes"][-1].texto


class TestElHistorialNoReenviaLasFotos:
    def test_una_foto_vieja_con_analisis_va_como_texto(self):
        mensajes = MensajesConArchivos([
            _imagen(analisis="Comprobante de pago: $24.99, Banco Pichincha"),
            {"rol": "bot", "contenido": "Lo recibimos, un asesor lo revisa."},
            {"rol": "cliente", "contenido": "¿ya está?"},
        ])
        llm = LLMProviderFalso([_fin()])
        canales = CanalesFalsos()
        _servicio(llm, mensajes, canales).procesar_turno(1, "")
        historial = llm.llamadas[0]["mensajes"]
        assert historial[0].texto.startswith("[imagen del cliente: Comprobante de pago: $24.99")
        assert all(m.adjuntos == [] for m in historial) and canales.pedidos == []

    def test_sin_analisis_queda_el_texto_de_siempre(self):
        mensajes = MensajesConArchivos([_imagen(), {"rol": "bot", "contenido": "ok"}, {"rol": "cliente", "contenido": "hola"}])
        llm = LLMProviderFalso([_fin()])
        _servicio(llm, mensajes, CanalesFalsos()).procesar_turno(1, "")
        assert llm.llamadas[0]["mensajes"][0].texto == "[imagen]"


class TestLeerMonto:
    @pytest.mark.parametrize("texto, esperado", [
        ("24.99", "24.99"), ("$24.99", "24.99"), ("24,99", "24.99"), ("USD 1.250,50", "1250.50"), ("1,250.50", "1250.50"),
        ("25", "25.00"), (24.99, "24.99"), (Decimal("30"), "30.00"),
    ])
    def test_formatos_comunes(self, texto, esperado):
        assert _leer_monto(texto) == Decimal(esperado)

    @pytest.mark.parametrize("texto", [None, "", "no se lee", "—"])
    def test_lo_que_no_es_un_monto(self, texto):
        assert _leer_monto(texto) is None


class TestRegistrarImagenRecibida:
    def _escena(self, lead):
        mensajes = MensajesConArchivos([{"rol": "cliente", "contenido": "ahí va", **{k: v for k, v in _imagen().items() if k != "contenido"}}])
        telegram = MagicMock()
        leads = FakeLeadsDeHerramientas(leads={1: lead})
        h = _herramientas(lead_repo=leads, telegram=telegram)
        h._mensajes = mensajes
        return h, mensajes, telegram, h._conversaciones

    def _registrar(self, h, **entrada):
        return h.ejecutar("registrar_imagen_recibida", 1, 1, entrada, "t").contenido

    def test_un_comprobante_que_coincide_se_registra_y_pasa_a_una_persona(self):
        h, mensajes, telegram, conversaciones = self._escena({"estado": "esperando_pago", "metodo_pago": "transferencia", "total": Decimal("24.99")})
        respuesta = self._registrar(h, tipo="comprobante_pago", resumen="Transferencia del Banco Pichincha", monto="$24.99", fecha="2026-11-09", banco="Pichincha", referencia="123456")

        assert "NO confirmes ni des por pagado" in respuesta
        assert "monto: $24.99" in mensajes.analisis[1] and "referencia: 123456" in mensajes.analisis[1]
        assert conversaciones.estados[1] == "escalada"
        motivo = telegram.notificar_escalado.call_args.args[2]
        assert "COINCIDE" in motivo and "VERIFICAR el pago" in motivo

    def test_un_monto_distinto_se_marca_en_el_aviso(self):
        h, _, telegram, _ = self._escena({"estado": "esperando_pago", "total": Decimal("24.99")})
        self._registrar(h, tipo="comprobante_pago", resumen="Transferencia", monto="20.00")
        assert "NO COINCIDE" in telegram.notificar_escalado.call_args.args[2]

    def test_un_comprobante_sin_monto_legible_tambien_va_a_una_persona(self):
        h, _, telegram, conversaciones = self._escena({"estado": "esperando_pago", "total": Decimal("24.99")})
        self._registrar(h, tipo="comprobante_pago", resumen="Foto borrosa de una transferencia")
        assert "no se pudo leer" in telegram.notificar_escalado.call_args.args[2] and conversaciones.estados[1] == "escalada"

    def test_un_comprobante_de_quien_no_debia_pagar_se_avisa_igual(self):
        h, _, telegram, _ = self._escena({"estado": "recopilando_datos", "total": Decimal("24.99")})
        self._registrar(h, tipo="comprobante_pago", resumen="Transferencia", monto="24.99")
        assert "no tenía un pago por transferencia pendiente" in telegram.notificar_escalado.call_args.args[2]

    @pytest.mark.parametrize("tipo, frase", [("producto", "muestra un producto"), ("ilegible", "ilegible"), ("otro", "Imagen registrada"), ("direccion_o_ubicacion", "Imagen registrada")])
    def test_los_otros_tipos_no_escalan(self, tipo, frase):
        h, mensajes, telegram, conversaciones = self._escena({"estado": "recopilando_datos"})
        assert frase in self._registrar(h, tipo=tipo, resumen="una foto")
        assert mensajes.analisis[1] == "una foto" and 1 not in conversaciones.estados
        telegram.notificar_escalado.assert_not_called()

    def test_sin_ninguna_foto_reciente_no_inventa_nada(self):
        h, _, telegram, _ = self._escena({"estado": "esperando_pago"})
        h._mensajes = MensajesConArchivos([{"rol": "cliente", "contenido": "hola"}])
        assert "No hay ninguna foto" in self._registrar(h, tipo="comprobante_pago", resumen="x", monto="1")
        telegram.notificar_escalado.assert_not_called()
