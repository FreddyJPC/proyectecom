from unittest.mock import MagicMock

import pytest

from src.integrations.whatsapp import WhatsAppAuthError
from src.routes.anuncios.referral import normalizar_referral
from src.routes.whatsapp.dto import MensajeEntranteDTO
from src.routes.whatsapp.services import WebhookService


@pytest.fixture
def postventa_a_una_persona(monkeypatch):
    """El comportamiento de ANTES de los leads: con el parámetro apagado, un cliente con pedido previo pasa a una persona."""
    from src.config.parametros import parametros

    real = parametros.valor
    monkeypatch.setattr(
        parametros, "valor", lambda clave: False if clave == "bot.atender_clientes_recurrentes" else real(clave)
    )


class FakeConversacionRepository:
    def __init__(self, existentes=None):
        self.tabla = dict(existentes or {})
        self._siguiente_id = max((c["id"] for c in self.tabla.values()), default=0) + 1
        self.timestamps_actualizados = []

    # En estos falsos la conversación se guarda por su identificador en el canal (el teléfono, en WhatsApp) y el
    # contacto se identifica por ese mismo valor: basta para comprobar las reglas del webhook sin base de datos.
    def obtener_por_canal(self, canal, id_externo):
        existente = self.tabla.get(id_externo)
        if existente is None:
            return None
        return {"contacto_id": id_externo, "canal": canal, "id_externo": id_externo, **existente}

    def crear(self, id_externo, canal="whatsapp", origen="directo", id_anuncio=None, ctwa_clid=None,
              nombre_perfil=None, telefono=None):
        conversacion = {
            "id": self._siguiente_id,
            "contacto_id": id_externo,
            "canal": canal,
            "id_externo": id_externo,
            "telefono": telefono or id_externo,
            "nombre_perfil": nombre_perfil,
            "origen": origen,
            "id_anuncio": id_anuncio,
            "ctwa_clid": ctwa_clid,
            "estado": "activa",
        }
        self.tabla[id_externo] = conversacion
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

    def existe_pedido_previo(self, contacto_id):
        return contacto_id in self._despachados

    def obtener_por_conversacion(self, conversacion_id):
        return self._leads_por_conversacion.get(conversacion_id)


class FakeAnuncioServicio:
    """Sustituye al servicio de anuncios (que usa la base): registra lo que se le pide."""

    def __init__(self, anuncio_nuevo=False, falla=False):
        self.llegadas = []
        self._anuncio_nuevo = anuncio_nuevo
        self._falla = falla

    def registrar_llegada(self, conversacion_id, mensaje_id, wamid, referral):
        if self._falla:
            raise RuntimeError("la base no responde")
        self.llegadas.append({"conversacion_id": conversacion_id, "mensaje_id": mensaje_id, "wamid": wamid, "referral": referral})
        return {"registrada": True, "anuncio_nuevo": self._anuncio_nuevo, "datos": normalizar_referral(referral)}

    def describir_origen(self, conversacion_id):
        return "Escribió directo (sin anuncio)"


def _dto(wamid="wamid.1", id_externo="593987654321", contenido="Hola", referral=None, tipo="texto", canal="whatsapp",
         nombre_perfil=None):
    return MensajeEntranteDTO(
        wamid=wamid, id_externo=id_externo, contenido=contenido, tipo=tipo, canal=canal,
        nombre_perfil=nombre_perfil, referral=referral,
    )


def _service(conv_repo=None, msg_repo=None, lead_repo=None, telegram=None, client=None, bot_worker=None, anuncios=None):
    return WebhookService(
        whatsapp_client=client or MagicMock(),
        conversacion_repo=conv_repo or FakeConversacionRepository(),
        mensaje_repo=msg_repo or FakeMensajeRepository(),
        lead_repo=lead_repo or FakeLeadRepository(),
        telegram_notifier=telegram or MagicMock(),
        bot_worker=bot_worker or MagicMock(),
        anuncio_servicio=anuncios or FakeAnuncioServicio(),
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
    def test_referral_presente_marca_origen_anuncio(self):
        conv_repo = FakeConversacionRepository()

        _service(conv_repo=conv_repo).procesar_mensaje_entrante(
            _dto(referral={"source_id": "23847382910", "ctwa_clid": "abc123"})
        )

        conversacion = conv_repo.tabla["593987654321"]
        assert conversacion["origen"] == "anuncio"
        assert conversacion["id_anuncio"] == "23847382910"
        assert conversacion["ctwa_clid"] == "abc123"

    def test_la_conversacion_nace_con_su_canal_y_el_nombre_de_perfil(self):
        conv_repo = FakeConversacionRepository()
        bot_worker = MagicMock()
        _service(conv_repo=conv_repo, bot_worker=bot_worker).procesar_mensaje_entrante(
            _dto(id_externo="17841400000000000", canal="instagram", nombre_perfil="José P.")
        )
        conversacion = conv_repo.tabla["17841400000000000"]
        assert conversacion["canal"] == "instagram" and conversacion["nombre_perfil"] == "José P."
        kwargs = bot_worker.encolar.call_args.kwargs
        assert kwargs["canal"] == "instagram" and kwargs["id_externo"] == "17841400000000000"

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
            canal="whatsapp",
            id_externo="593987654321",
            modo="ia",
            mensaje_id=msg_repo.mensajes[0]["id"],
            texto_mensaje_cliente="Hola",
        )


class TestLlegadaPorAnuncio:
    """Cada mensaje que llega desde un anuncio se guarda COMPLETO, también si el cliente ya existía."""

    REFERRAL = {
        "source_id": "23847382910",
        "source_type": "ad",
        "headline": "Audífonos Pro",
        "body": "Cancelación de ruido",
        "source_url": "https://fb.me/abc",
        "ctwa_clid": "clic-1",
    }

    def test_cliente_nuevo_por_anuncio_guarda_la_llegada_con_el_mensaje(self):
        anuncios = FakeAnuncioServicio()
        msg_repo = FakeMensajeRepository()

        _service(msg_repo=msg_repo, anuncios=anuncios).procesar_mensaje_entrante(_dto(wamid="wamid.9", referral=self.REFERRAL))

        assert len(anuncios.llegadas) == 1
        llegada = anuncios.llegadas[0]
        assert llegada["wamid"] == "wamid.9"
        assert llegada["mensaje_id"] == msg_repo.mensajes[0]["id"]
        assert llegada["referral"] == self.REFERRAL

    def test_cliente_que_ya_existia_y_vuelve_por_otro_anuncio_tambien_se_registra(self):
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 99, "telefono": "593987654321", "origen": "directo", "estado": "activa"}}
        )
        anuncios = FakeAnuncioServicio()

        _service(conv_repo=conv_repo, anuncios=anuncios).procesar_mensaje_entrante(_dto(referral=self.REFERRAL))

        assert [l["conversacion_id"] for l in anuncios.llegadas] == [99]

    def test_sin_referral_no_se_registra_ninguna_llegada(self):
        anuncios = FakeAnuncioServicio()
        _service(anuncios=anuncios).procesar_mensaje_entrante(_dto())
        assert anuncios.llegadas == []

    def test_la_llegada_se_registra_antes_de_encolar_la_respuesta(self):
        """Para que Victoria ya vea el anuncio vigente al contestar."""
        orden = []
        anuncios = FakeAnuncioServicio()
        original = anuncios.registrar_llegada
        anuncios.registrar_llegada = lambda *a, **k: (orden.append("llegada"), original(*a, **k))[1]
        bot_worker = MagicMock()
        bot_worker.encolar.side_effect = lambda **k: orden.append("encolar")

        _service(anuncios=anuncios, bot_worker=bot_worker).procesar_mensaje_entrante(_dto(referral=self.REFERRAL))

        assert orden == ["llegada", "encolar"]

    def test_si_falla_guardar_el_anuncio_el_cliente_igual_recibe_respuesta(self):
        bot_worker = MagicMock()

        _service(anuncios=FakeAnuncioServicio(falla=True), bot_worker=bot_worker).procesar_mensaje_entrante(
            _dto(referral=self.REFERRAL)
        )

        bot_worker.encolar.assert_called_once()

    def test_anuncio_nuevo_sin_vincular_avisa_por_telegram(self):
        telegram = MagicMock()

        _service(telegram=telegram, anuncios=FakeAnuncioServicio(anuncio_nuevo=True)).procesar_mensaje_entrante(
            _dto(referral=self.REFERRAL)
        )

        telegram.notificar_aviso.assert_called_once()
        titulo, detalle = telegram.notificar_aviso.call_args.args
        assert "anuncio nuevo" in titulo
        assert "23847382910" in detalle and "Audífonos Pro" in detalle

    def test_anuncio_ya_conocido_no_vuelve_a_avisar(self):
        telegram = MagicMock()
        _service(telegram=telegram, anuncios=FakeAnuncioServicio(anuncio_nuevo=False)).procesar_mensaje_entrante(
            _dto(referral=self.REFERRAL)
        )
        telegram.notificar_aviso.assert_not_called()

    def test_el_aviso_de_escalado_incluye_de_donde_viene_el_cliente(self, postventa_a_una_persona):
        telegram = MagicMock()
        lead_repo = FakeLeadRepository(despachados_por_telefono=["593987654321"])
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 5, "telefono": "593987654321", "origen": "anuncio", "estado": "activa"}}
        )

        _service(conv_repo=conv_repo, lead_repo=lead_repo, telegram=telegram).procesar_mensaje_entrante(_dto())

        assert telegram.notificar_escalado.call_args.kwargs["origen"] == "Escribió directo (sin anuncio)"


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

    def test_telefono_con_lead_despachado_escala_sin_invocar_al_llm(self, postventa_a_una_persona):
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

    def test_imagen_con_lead_esperando_pago_escala_sin_invocar_al_llm(self, monkeypatch):
        # Con «Que Victoria vea las fotos» APAGADO se mantiene la regla de siempre.
        from src.config.parametros import parametros

        real = parametros.valor
        monkeypatch.setattr(parametros, "valor", lambda clave: False if clave == "bot.entender_imagenes" else real(clave))
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

    def test_los_textos_fijos_son_parametros_que_se_cambian_desde_la_app(self, monkeypatch):
        from src.config.parametros import parametros

        real = parametros.valor
        editados = {
            "bot.texto_postventa": "Texto de postventa editado", "bot.texto_comprobante_recibido": "Comprobante editado",
            "bot.atender_clientes_recurrentes": False, "bot.entender_imagenes": False,
        }
        monkeypatch.setattr(parametros, "valor", lambda clave: editados[clave] if clave in editados else real(clave))

        postventa = MagicMock()
        _service(
            conv_repo=FakeConversacionRepository(existentes={"593987654321": {"id": 1, "telefono": "593987654321", "origen": "directo", "estado": "activa"}}),
            lead_repo=FakeLeadRepository(despachados_por_telefono={"593987654321"}), bot_worker=postventa,
        ).procesar_mensaje_entrante(_dto())
        assert postventa.encolar.call_args.kwargs["texto_fijo"] == "Texto de postventa editado"

        comprobante = MagicMock()
        _service(
            conv_repo=FakeConversacionRepository(existentes={"593987654321": {"id": 1, "telefono": "593987654321", "origen": "directo", "estado": "activa"}}),
            lead_repo=FakeLeadRepository(leads_por_conversacion={1: {"estado": "esperando_pago"}}), bot_worker=comprobante,
        ).procesar_mensaje_entrante(_dto(wamid="wamid.2", tipo="imagen", contenido="[imagen]"))
        assert comprobante.encolar.call_args.kwargs["texto_fijo"] == "Comprobante editado"

    def test_por_defecto_victoria_atiende_al_cliente_que_ya_compro(self):
        """Pedido de Freddy: Victoria es la vendedora, atiende y da seguimiento al cliente recurrente; solo pasa a una persona lo
        que no sabe o lo que es de un pedido anterior (eso lo decide ella con escalar_a_humano, no una regla fija)."""
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 1, "telefono": "593987654321", "origen": "directo", "estado": "activa"}}
        )
        lead_repo = FakeLeadRepository(despachados_por_telefono={"593987654321"})
        telegram = MagicMock()
        bot_worker = MagicMock()

        _service(
            conv_repo=conv_repo, lead_repo=lead_repo, telegram=telegram, bot_worker=bot_worker
        ).procesar_mensaje_entrante(_dto(contenido="Hola, quiero comprar otra cosa"))

        assert conv_repo.tabla["593987654321"]["estado"] == "activa"
        telegram.notificar_escalado.assert_not_called()
        kwargs = bot_worker.encolar.call_args.kwargs
        assert kwargs["modo"] == "ia" and kwargs["texto_mensaje_cliente"] == "Hola, quiero comprar otra cosa"

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
        conv_repo.obtener_por_canal.side_effect = RuntimeError("boom")

        _service(conv_repo=conv_repo).procesar_mensaje_entrante(_dto())  # no debe lanzar


class TestConversacionEnGestion:
    """ADR-012: «en gestión» = el dueño está a cargo de un producto propio, igual que una escalada."""

    def test_una_conversacion_en_gestion_no_recibe_respuesta_automatica(self):
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 1, "telefono": "593987654321", "origen": "directo", "estado": "en_gestion"}}
        )
        bot_worker = MagicMock()

        _service(conv_repo=conv_repo, bot_worker=bot_worker).procesar_mensaje_entrante(_dto())

        bot_worker.encolar.assert_not_called()

    def test_quien_tiene_un_pedido_previo_por_gestionar_recibe_la_respuesta_fija_de_postventa(self, postventa_a_una_persona):
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 1, "telefono": "593987654321", "origen": "directo", "estado": "activa"}}
        )
        # El repositorio real devuelve True tanto para `despachado` como para `por_gestionar`.
        lead_repo = FakeLeadRepository(despachados_por_telefono={"593987654321"})
        bot_worker = MagicMock()

        _service(conv_repo=conv_repo, lead_repo=lead_repo, bot_worker=bot_worker).procesar_mensaje_entrante(_dto())

        assert bot_worker.encolar.call_args.kwargs["modo"] == "fijo"


class TestImagenesConLaFuncionEncendida:
    """Con «Que Victoria vea las fotos» encendido (lo normal), una foto de un cliente que debe pagar la ve Victoria."""

    def _correr(self, tipo):
        conv_repo = FakeConversacionRepository(
            existentes={"593987654321": {"id": 1, "telefono": "593987654321", "origen": "directo", "estado": "activa"}}
        )
        bot_worker = MagicMock()
        _service(
            conv_repo=conv_repo, lead_repo=FakeLeadRepository(leads_por_conversacion={1: {"estado": "esperando_pago"}}),
            bot_worker=bot_worker,
        ).procesar_mensaje_entrante(_dto(tipo=tipo, contenido="[imagen]"))
        return conv_repo, bot_worker

    def test_la_foto_pasa_a_victoria_en_vez_de_escalarse_directo(self):
        conv_repo, bot_worker = self._correr("imagen")
        assert bot_worker.encolar.call_args.kwargs["modo"] == "ia"
        assert conv_repo.tabla["593987654321"]["estado"] == "activa"  # el que escala, si es un comprobante, es la herramienta

    def test_un_pdf_igual(self):
        _, bot_worker = self._correr("documento")
        assert bot_worker.encolar.call_args.kwargs["modo"] == "ia"

    def test_una_reaccion_no_se_contesta(self):
        _, bot_worker = self._correr("reaccion")
        bot_worker.encolar.assert_not_called()
