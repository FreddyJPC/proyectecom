"""
Quién atiende cada mensaje: el webhook decide el asistente (por anuncio o por número) y el worker contesta con el asistente de
la conversación y DESDE el número por el que escribió el cliente.
"""
from unittest.mock import MagicMock

from src.config.parametros import parametros
from src.integrations.canales import CanalWhatsApp, RegistroCanales
from src.routes.inmuebles.ruteo import RuteoDeAsistente
from src.routes.whatsapp.dto import MensajeEntranteDTO, TareaRespuestaDTO
from src.routes.whatsapp.services import WebhookService
from src.routes.whatsapp.worker import BotWorker
from tests.unit.routes.whatsapp.test_services import (
    FakeAnuncioServicio,
    FakeConversacionRepository,
    FakeLeadRepository,
    FakeMensajeRepository,
)

NUMERO_CASA = "880000000001"
ANUNCIO_CASA = "1200000000990001"


class RuteoFalso(RuteoDeAsistente):
    def __init__(self, numeros=None, anuncios=None):
        self._num = numeros or {}
        self._anu = anuncios or {}

    def para_numero(self, numero_negocio):
        return self._num.get(numero_negocio, "ventas")

    def inmueble_de_anuncio(self, id_anuncio):
        return self._anu.get(id_anuncio)


def _servicio(ruteo, conv_repo=None, bot_worker=None, telegram=None):
    return WebhookService(
        whatsapp_client=MagicMock(),
        conversacion_repo=conv_repo or FakeConversacionRepository(),
        mensaje_repo=FakeMensajeRepository(),
        lead_repo=FakeLeadRepository(),
        telegram_notifier=telegram or MagicMock(),
        bot_worker=bot_worker or MagicMock(),
        anuncio_servicio=FakeAnuncioServicio(),
        ruteo=ruteo,
    )


def _dto(numero=None, referral=None, wamid="wamid.casa-1"):
    return MensajeEntranteDTO(
        wamid=wamid, id_externo="593990001101", contenido="Hola, info de la casa", tipo="texto", numero_negocio=numero,
        referral=referral,
    )


class TestWebhook:
    def test_el_numero_de_la_casa_crea_una_conversacion_de_inmuebles(self):
        conv_repo, worker = FakeConversacionRepository(), MagicMock()
        _servicio(RuteoFalso(numeros={NUMERO_CASA: "inmuebles"}), conv_repo, worker)._procesar(_dto(numero=NUMERO_CASA))
        conversacion = conv_repo.tabla["593990001101"]
        assert conversacion["asistente"] == "inmuebles" and conversacion["numero_negocio"] == NUMERO_CASA
        assert worker.encolar.call_args.kwargs["modo"] == "ia"

    def test_el_anuncio_de_la_casa_manda_al_asistente_aunque_sea_el_numero_de_victoria(self):
        conv_repo = FakeConversacionRepository()
        referral = {"source_id": ANUNCIO_CASA, "source_type": "ad"}
        _servicio(RuteoFalso(anuncios={ANUNCIO_CASA: 7}), conv_repo)._procesar(_dto(referral=referral))
        conversacion = conv_repo.tabla["593990001101"]
        assert conversacion["asistente"] == "inmuebles" and conversacion["inmueble_id"] == 7
        assert conversacion["numero_negocio"] is None  # el número principal

    def test_un_cliente_de_la_tienda_que_vuelve_por_el_anuncio_de_la_casa_cambia_de_asistente(self):
        conv_repo = FakeConversacionRepository({"593990001101": {"id": 5, "estado": "activa", "asistente": "ventas"}})
        referral = {"source_id": ANUNCIO_CASA, "source_type": "ad"}
        _servicio(RuteoFalso(anuncios={ANUNCIO_CASA: 7}), conv_repo)._procesar(_dto(referral=referral))
        assert conv_repo.tabla["593990001101"]["asistente"] == "inmuebles"
        assert conv_repo.tabla["593990001101"]["inmueble_id"] == 7

    def test_sin_anuncio_ni_numero_de_inmuebles_es_victoria(self):
        conv_repo = FakeConversacionRepository()
        _servicio(RuteoFalso(), conv_repo)._procesar(_dto())
        assert conv_repo.tabla["593990001101"]["asistente"] == "ventas"

    def test_con_el_asistente_apagado_pasa_al_dueno_sin_respuesta(self, monkeypatch):
        original = parametros.valor
        monkeypatch.setattr(parametros, "valor", lambda clave: False if clave == "inmuebles.activo" else original(clave))
        conv_repo, worker, telegram = FakeConversacionRepository(), MagicMock(), MagicMock()
        _servicio(RuteoFalso(numeros={NUMERO_CASA: "inmuebles"}), conv_repo, worker, telegram)._procesar(_dto(numero=NUMERO_CASA))
        assert conv_repo.tabla["593990001101"]["estado"] == "escalada"
        worker.encolar.assert_not_called()
        telegram.notificar_escalado.assert_called_once()

    def test_una_conversacion_de_inmuebles_en_manos_del_dueno_no_se_responde(self):
        conv_repo = FakeConversacionRepository({"593990001101": {"id": 5, "estado": "escalada", "asistente": "inmuebles"}})
        worker = MagicMock()
        _servicio(RuteoFalso(), conv_repo, worker)._procesar(_dto())
        worker.encolar.assert_not_called()


class TestWorker:
    def _worker(self, conversacion, canal_principal, canal_casa, victoria, inmuebles):
        registro = RegistroCanales({"whatsapp": canal_principal}, fabrica_whatsapp=lambda numero: canal_casa)
        conversaciones = MagicMock()
        conversaciones.obtener_por_id.return_value = conversacion
        return BotWorker(
            canales=registro, mensaje_repository=MagicMock(), cola_repository=MagicMock(), conversation_service=victoria,
            conversacion_repository=conversaciones, servicio_inmuebles=inmuebles, segundos_espera=0,
        )

    def _tarea(self):
        return TareaRespuestaDTO(cola_mensajes_id=1, conversacion_id=5, canal="whatsapp", id_externo="593990001101", modo="ia")

    def test_responde_el_asistente_de_inmuebles_desde_el_numero_de_la_casa(self):
        principal, casa, victoria, inmuebles = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        inmuebles.procesar_turno.return_value = "Hola, con gusto le doy información."
        worker = self._worker({"id": 5, "asistente": "inmuebles", "numero_negocio": NUMERO_CASA}, principal, casa, victoria, inmuebles)
        worker._procesar(self._tarea())
        victoria.procesar_turno.assert_not_called()
        casa.enviar_texto.assert_called_once_with("593990001101", "Hola, con gusto le doy información.")
        principal.enviar_texto.assert_not_called()

    def test_victoria_sigue_igual(self):
        principal, casa, victoria, inmuebles = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        victoria.procesar_turno.return_value = "Hola, soy Victoria."
        worker = self._worker({"id": 5, "asistente": "ventas", "numero_negocio": None}, principal, casa, victoria, inmuebles)
        worker._procesar(self._tarea())
        inmuebles.procesar_turno.assert_not_called()
        principal.enviar_texto.assert_called_once_with("593990001101", "Hola, soy Victoria.")

    def test_si_no_se_puede_leer_la_conversacion_responde_victoria_por_el_principal(self):
        principal, casa, victoria, inmuebles = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        victoria.procesar_turno.return_value = "Hola"
        worker = self._worker(None, principal, casa, victoria, inmuebles)
        worker._conversaciones_fijo.obtener_por_id.side_effect = RuntimeError("base caída")
        worker._procesar(self._tarea())
        principal.enviar_texto.assert_called_once()


def test_el_registro_reutiliza_el_canal_de_cada_numero():
    creados = []

    def fabrica(numero):
        creados.append(numero)
        return MagicMock()

    registro = RegistroCanales({"whatsapp": MagicMock()}, fabrica_whatsapp=fabrica)
    assert registro.para("whatsapp", NUMERO_CASA) is registro.para_conversacion({"canal": "whatsapp", "numero_negocio": NUMERO_CASA})
    assert creados == [NUMERO_CASA]
    principal = registro.para("whatsapp")
    assert registro.para_conversacion({"canal": "whatsapp", "numero_negocio": None}) is principal


def test_el_canal_de_whatsapp_manda_la_ubicacion():
    cliente = MagicMock()
    CanalWhatsApp(cliente).enviar_ubicacion("5939", -2.1, -79.9, "Casa", "Av. 1")
    cliente.enviar_ubicacion.assert_called_once_with(telefono="5939", latitud=-2.1, longitud=-79.9, nombre="Casa", direccion="Av. 1")


def test_el_cliente_arma_el_mensaje_de_ubicacion(monkeypatch):
    from src.integrations.whatsapp.client import WhatsAppClient

    cliente = WhatsAppClient("123", "token")
    enviado = {}
    monkeypatch.setattr(cliente, "_post", lambda payload: enviado.update(payload) or {"messages": [{"id": "wamid.x"}]})
    cliente.enviar_ubicacion("5939", -2.170998, -79.922359, "Casa en Guayaquil", "Av. Principal")
    assert enviado == {
        "messaging_product": "whatsapp", "to": "5939", "type": "location",
        "location": {"latitude": -2.170998, "longitude": -79.922359, "name": "Casa en Guayaquil", "address": "Av. Principal"},
    }


def test_el_numero_principal_se_guarda_como_nulo():
    from src.integrations.whatsapp import normalizar_numero_negocio

    assert normalizar_numero_negocio("1") is None  # WHATSAPP_PHONE_NUMBER_ID de las pruebas
    assert normalizar_numero_negocio(None) is None
    assert normalizar_numero_negocio(NUMERO_CASA) == NUMERO_CASA


def test_el_webhook_toma_el_numero_del_negocio():
    from src.routes.whatsapp.controllers import _extraer_mensajes

    payload = {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": NUMERO_CASA},
        "messages": [{"from": "593990001101", "id": "wamid.1", "type": "text", "text": {"body": "Hola"}}],
    }}]}]}
    assert _extraer_mensajes(payload)[0].numero_negocio == NUMERO_CASA
