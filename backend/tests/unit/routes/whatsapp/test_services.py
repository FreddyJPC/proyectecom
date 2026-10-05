from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from src.integrations.whatsapp import WhatsAppAuthError
from src.routes.whatsapp.dto import MensajeEntranteDTO
from src.routes.whatsapp.services import WebhookService


class FakeConversacionRepository:
    def __init__(self, existentes=None):
        self.tabla = dict(existentes or {})
        self._siguiente_id = max((c["id"] for c in self.tabla.values()), default=0) + 1
        self.timestamps_actualizados = []

    def obtener_por_telefono(self, telefono):
        return self.tabla.get(telefono)

    def crear(self, telefono, origen="directo", fep_expira_en=None, id_anuncio=None, ctwa_clid=None):
        conversacion = {
            "id": self._siguiente_id,
            "telefono": telefono,
            "origen": origen,
            "fep_expira_en": fep_expira_en,
            "id_anuncio": id_anuncio,
            "ctwa_clid": ctwa_clid,
            "estado": "activa",
        }
        self.tabla[telefono] = conversacion
        self._siguiente_id += 1
        return conversacion

    def actualizar_estado(self, conversacion_id, estado):
        for c in self.tabla.values():
            if c["id"] == conversacion_id:
                c["estado"] = estado

    def marcar_escalada(self, conversacion_id):
        for c in self.tabla.values():
            if c["id"] == conversacion_id:
                c["estado"] = "escalada"
                c["vista_en"] = None

    def actualizar_timestamp(self, conversacion_id):
        self.timestamps_actualizados.append(conversacion_id)


class FakeMensajeRepository:
    def __init__(self):
        self.mensajes = []
        self._siguiente_id = 1

    def existe_por_wamid(self, wamid):
        return any(m["wamid"] == wamid for m in self.mensajes if m["wamid"] is not None)

    def crear(self, conversacion_id, rol, contenido, tipo="texto", wamid=None):
        mensaje = {
            "id": self._siguiente_id,
            "conversacion_id": conversacion_id,
            "rol": rol,
            "contenido": contenido,
            "tipo": tipo,
            "wamid": wamid,
        }
        self.mensajes.append(mensaje)
        self._siguiente_id += 1
        return mensaje

    def obtener_por_conversacion(self, conversacion_id):
        return [m for m in self.mensajes if m["conversacion_id"] == conversacion_id]


class FakeLeadRepository:
    def __init__(self, despachados_por_telefono=None, leads_por_conversacion=None):
        self._despachados = set(despachados_por_telefono or [])
        self._leads_por_conversacion = leads_por_conversacion or {}

    def existe_despachado_por_telefono(self, telefono):
        return telefono in self._despachados

    def obtener_por_conversacion(self, conversacion_id):
        return self._leads_por_conversacion.get(conversacion_id)


def _dto(wamid="wamid.1", telefono="593987654321", contenido="Hola", referral=None, tipo="texto"):
    return MensajeEntranteDTO(wamid=wamid, telefono=telefono, contenido=contenido, tipo=tipo, referral=referral)


def _service(conv_repo=None, msg_repo=None, lead_repo=None, telegram=None, client=None, bot_worker=None):
    return WebhookService(
        whatsapp_client=client or MagicMock(),
        conversacion_repo=conv_repo or FakeConversacionRepository(),
        mensaje_repo=msg_repo or FakeMensajeRepository(),
        lead_repo=lead_repo or FakeLeadRepository(),
        telegram_notifier=telegram or MagicMock(),
        bot_worker=bot_worker or MagicMock(),
    )


class TestIdempotencia:
    def test_wamid_nuevo_se_guarda_y_encola(self):
        msg_repo = FakeMensajeRepository()
        bot_worker = MagicMock()
        _service(msg_repo=msg_repo, bot_worker=bot_worker).procesar_mensaje_entrante(_dto())

        assert len(msg_repo.mensajes) == 1
        assert msg_repo.mensajes[0]["rol"] == "cliente"
        bot_worker.encolar.assert_called_once()

    def test_wamid_repetido_no_se_reprocesa(self):
        msg_repo = FakeMensajeRepository()
        msg_repo.crear(conversacion_id=1, rol="cliente", contenido="hola", wamid="wamid.1")
        bot_worker = MagicMock()

        _service(msg_repo=msg_repo, bot_worker=bot_worker).procesar_mensaje_entrante(_dto(wamid="wamid.1"))

        assert len(msg_repo.mensajes) == 1  # no se agregó un segundo
        bot_worker.encolar.assert_not_called()


class TestDeteccionDeOrigen:
    def test_referral_presente_marca_origen_fep_con_ventana_72h(self):
        conv_repo = FakeConversacionRepository()
        antes = datetime.now(timezone.utc)

        _service(conv_repo=conv_repo).procesar_mensaje_entrante(
            _dto(referral={"source_id": "23847382910", "ctwa_clid": "abc123"})
        )

        conversacion = conv_repo.tabla["593987654321"]
        assert conversacion["origen"] == "fep"
        assert conversacion["id_anuncio"] == "23847382910"
        assert conversacion["ctwa_clid"] == "abc123"
        assert conversacion["fep_expira_en"] > antes + timedelta(hours=71)

    def test_sin_referral_marca_origen_directo(self):
        conv_repo = FakeConversacionRepository()
        _service(conv_repo=conv_repo).procesar_mensaje_entrante(_dto())
        assert conv_repo.tabla["593987654321"]["origen"] == "directo"

    def test_cliente_existente_reutiliza_conversacion(self):
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 99, "telefono": "593987654321", "origen": "directo", "estado": "activa"}}
        )
        msg_repo = FakeMensajeRepository()
        bot_worker = MagicMock()

        _service(conv_repo=conv_repo, msg_repo=msg_repo, bot_worker=bot_worker).procesar_mensaje_entrante(_dto())

        assert 99 in conv_repo.timestamps_actualizados
        assert msg_repo.mensajes[0]["conversacion_id"] == 99
        bot_worker.encolar.assert_called_once_with(
            conversacion_id=99,
            telefono="593987654321",
            modo="ia",
            mensaje_id=msg_repo.mensajes[0]["id"],
            texto_mensaje_cliente="Hola",
        )


class TestReglasDeterministasDeEscalado:
    """Fase 3.2, Tarea 6: estas 4 reglas se evalúan ANTES de invocar al
    LLM siquiera -- ver services.py::_encolar_respuesta."""

    def test_conversacion_ya_escalada_no_encola_nada(self):
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 1, "telefono": "593987654321", "origen": "directo", "estado": "escalada"}}
        )
        bot_worker = MagicMock()

        _service(conv_repo=conv_repo, bot_worker=bot_worker).procesar_mensaje_entrante(_dto())

        bot_worker.encolar.assert_not_called()

    def test_telefono_con_lead_despachado_escala_sin_invocar_al_llm(self):
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 1, "telefono": "593987654321", "origen": "directo", "estado": "activa"}}
        )
        lead_repo = FakeLeadRepository(despachados_por_telefono={"593987654321"})
        telegram = MagicMock()
        bot_worker = MagicMock()

        _service(
            conv_repo=conv_repo, lead_repo=lead_repo, telegram=telegram, bot_worker=bot_worker
        ).procesar_mensaje_entrante(_dto())

        assert conv_repo.tabla["593987654321"]["estado"] == "escalada"
        telegram.notificar_escalado.assert_called_once()
        bot_worker.encolar.assert_called_once()
        kwargs = bot_worker.encolar.call_args.kwargs
        assert kwargs["modo"] == "fijo"
        assert "conecto" in kwargs["texto_fijo"].lower()

    def test_imagen_con_lead_esperando_pago_escala_sin_invocar_al_llm(self):
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 1, "telefono": "593987654321", "origen": "directo", "estado": "activa"}}
        )
        lead_repo = FakeLeadRepository(leads_por_conversacion={1: {"estado": "esperando_pago"}})
        telegram = MagicMock()
        bot_worker = MagicMock()

        _service(
            conv_repo=conv_repo, lead_repo=lead_repo, telegram=telegram, bot_worker=bot_worker
        ).procesar_mensaje_entrante(_dto(tipo="imagen", contenido="[imagen]"))

        assert conv_repo.tabla["593987654321"]["estado"] == "escalada"
        telegram.notificar_escalado.assert_called_once()
        bot_worker.encolar.assert_called_once()
        kwargs = bot_worker.encolar.call_args.kwargs
        assert kwargs["modo"] == "fijo"
        assert "comprobante" in kwargs["texto_fijo"].lower()

    def test_imagen_sin_lead_esperando_pago_no_escala_pasa_a_victoria(self):
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 1, "telefono": "593987654321", "origen": "directo", "estado": "activa"}}
        )
        lead_repo = FakeLeadRepository(leads_por_conversacion={1: {"estado": "recopilando_datos"}})
        bot_worker = MagicMock()

        _service(conv_repo=conv_repo, lead_repo=lead_repo, bot_worker=bot_worker).procesar_mensaje_entrante(
            _dto(tipo="imagen", contenido="[imagen]")
        )

        assert conv_repo.tabla["593987654321"]["estado"] == "activa"
        bot_worker.encolar.assert_called_once()
        assert bot_worker.encolar.call_args.kwargs["modo"] == "ia"

    def test_caso_normal_encola_modo_ia_con_texto_del_cliente(self):
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 1, "telefono": "593987654321", "origen": "directo", "estado": "activa"}}
        )
        bot_worker = MagicMock()

        _service(conv_repo=conv_repo, bot_worker=bot_worker).procesar_mensaje_entrante(_dto(contenido="Quiero comprar"))

        kwargs = bot_worker.encolar.call_args.kwargs
        assert kwargs["modo"] == "ia"
        assert kwargs["texto_mensaje_cliente"] == "Quiero comprar"


class TestToleranciaAFallos:
    def test_fallo_marcando_como_leido_no_impide_encolar(self):
        client = MagicMock()
        client.marcar_como_leido.side_effect = WhatsAppAuthError("token vencido")
        bot_worker = MagicMock()

        _service(client=client, bot_worker=bot_worker).procesar_mensaje_entrante(_dto())  # no debe lanzar

        bot_worker.encolar.assert_called_once()

    def test_excepcion_interna_nunca_se_propaga(self):
        conv_repo = MagicMock()
        conv_repo.obtener_por_telefono.side_effect = RuntimeError("boom")

        _service(conv_repo=conv_repo).procesar_mensaje_entrante(_dto())  # no debe lanzar
