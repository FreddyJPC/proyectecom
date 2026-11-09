"""
Seguimiento automático con la base real y un canal de WhatsApp y un Telegram FALSOS: a quién se le escribe, a quién jamás, el
tope, el horario, lo que pasa cuando el envío falla y que nunca se repite.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.config.database import get_connection
from src.config.parametros import parametros
from src.integrations.canales import RegistroCanales
from src.integrations.whatsapp.exceptions import WhatsAppBusinessError, WhatsAppRequestError
from src.jobs.seguimiento.repository import SeguimientoRepository
from src.jobs.seguimiento.service import SeguimientoService
from src.routes.anuncios.referral import normalizar_referral
from src.routes.anuncios.repository import AnuncioRepository
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository
from tests.helpers_db import borrar_conversaciones_de_prueba

TELEFONOS = [f"59390000{n:04d}" for n in range(6001, 6009)]
T1, T2, T3 = TELEFONOS[:3]
DUENO = "test@ejemplo.com"
TEXTO_EMPUJON = "Hola 👋 ¿Sigue interesado(a)? Cuénteme y lo terminamos en un momento 😊"
TEXTO_PLANTILLA = "Hola 👋 Soy Victoria, de AzoShop. ¿Sigue interesado(a)? Si necesita ayuda, escríbame y con gusto le atiendo."


class CanalFalso:
    """Un canal de WhatsApp que anota lo que se le pide enviar (y puede fallar a pedido)."""

    def __init__(self):
        self.textos, self.plantillas = [], []
        self.falla = None

    def enviar_texto(self, id_externo, mensaje):
        if self.falla:
            raise self.falla
        self.textos.append((id_externo, mensaje))
        return {"messages": [{"id": f"wamid.texto-{len(self.textos)}"}]}

    def enviar_plantilla(self, id_externo, nombre_plantilla, variables=None, idioma="es"):
        if self.falla:
            raise self.falla
        self.plantillas.append((id_externo, nombre_plantilla))
        return {"messages": [{"id": f"wamid.plantilla-{len(self.plantillas)}"}]}


def _limpiar():
    # Primero Instagram (la prueba de canales sin plantillas crea una), después WhatsApp: el contacto se borra con la última.
    borrar_conversaciones_de_prueba(*[f"ig-{t}" for t in TELEFONOS], canal="instagram")
    borrar_conversaciones_de_prueba(*TELEFONOS)


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


@pytest.fixture
def canal():
    return CanalFalso()


@pytest.fixture
def telegram():
    return MagicMock()


@pytest.fixture
def servicio(canal, telegram):
    return SeguimientoService(canales=RegistroCanales({"whatsapp": canal}), telegram=telegram)


@contextmanager
def ajustes(**valores):
    """Guarda parámetros para la prueba y los restaura al terminar (las claves van con `__` en vez de `.`)."""
    claves = {k.replace("__", ".", 1): v for k, v in valores.items()}
    try:
        for clave, valor in claves.items():
            parametros.guardar(clave, valor, DUENO)
        yield
    finally:
        for clave in claves:
            parametros.restaurar(clave, DUENO)


def _sql(consulta, *params):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(consulta, params)
        return cur.fetchall() if cur.description else None


def _mensaje(conv_id, rol, horas_atras):
    _sql(
        "insert into mensajes (conversacion_id, rol, contenido, tipo, creado_en) "
        "values (%s, %s, 'texto de prueba', 'texto', now() - make_interval(secs => %s))",
        conv_id, rol, horas_atras * 3600,
    )


def _escenario(telefono, mensajes, *, temperatura="tibio", producto=True, estado="activa", anuncio=False, canal="whatsapp"):
    """Un cliente con su conversación, su lead y mensajes `(rol, horas atrás)`. Devuelve (conversación, lead)."""
    conv = ConversacionRepository.crear(id_externo=telefono if canal == "whatsapp" else f"ig-{telefono}", canal=canal, telefono=telefono)
    lead = LeadRepository.obtener_o_crear(conv["id"], conv["contacto_id"], telefono)
    if producto:
        _sql("update leads set producto_sku = 'AUD-1', producto_nombre = 'Audífonos' where id = %s", lead["id"])
    if temperatura != "tibio":
        _sql("update leads set temperatura = %s where id = %s", temperatura, lead["id"])
    if estado != "activa":
        _sql("update conversaciones set estado = %s where id = %s", estado, conv["id"])
    for rol, horas in mensajes:
        _mensaje(conv["id"], rol, horas)
    if anuncio:
        referral = {"source_id": "AD-SEG-1", "source_type": "ad", "ctwa_clid": "clic-seg", "headline": "Anuncio"}
        AnuncioRepository.registrar_llegada(conv["id"], None, f"wamid.seg-{telefono}", normalizar_referral(referral), referral)
        # La llegada ocurrió con el primer mensaje del cliente.
        _sql("update conversacion_anuncios set creado_en = (select min(creado_en) from mensajes where conversacion_id = %s) where conversacion_id = %s", conv["id"], conv["id"])
    return conv, lead


# Un cliente que escribió hace 5 h y a quien Victoria contestó enseguida: le toca el empujón (espera de 4 h).
EMPUJON_5H = [("cliente", 5), ("bot", 4.9)]
# Escribió hace 30 h por un anuncio y Victoria contestó enseguida: pasó la ventana de 24 h pero la gratuita sigue abierta.
PLANTILLA_30H = [("cliente", 30), ("bot", 29.9)]


def _seguimientos(telefono):
    return _sql(
        "select s.tipo, s.estado, s.contenido, s.plantilla, s.wamid, s.error from seguimientos s "
        "join contactos ct on ct.id = s.contacto_id where ct.telefono = %s order by s.id", telefono,
    )


def _ejecutar(servicio):
    return servicio.ejecutar(datetime.now(timezone.utc))


# Los interruptores vienen apagados: así llega a producción. Cada prueba prende solo lo que necesita y abre el horario completo
# (la hora real de la prueba no debe decidir el resultado).
HORARIO_ABIERTO = dict(seguimiento__hora_desde=0, seguimiento__hora_hasta=24)


class TestApagadoPorDefecto:
    def test_sin_tocar_nada_no_escribe_a_nadie(self, servicio, canal):
        _escenario(T1, EMPUJON_5H)
        resumen = _ejecutar(servicio)
        assert resumen["motivo_de_pausa"] == "apagado"
        assert canal.textos == [] and canal.plantillas == []
        assert _seguimientos(T1) == []

    def test_los_dos_interruptores_vienen_apagados_en_el_catalogo(self):
        assert parametros.valor("seguimiento.empujon_activo") is False
        assert parametros.valor("seguimiento.plantilla_activa") is False


class TestElEmpujon:
    def test_le_escribe_al_cliente_interesado_que_dejo_de_contestar(self, servicio, canal, telegram):
        conv, _ = _escenario(T1, EMPUJON_5H)
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            resumen = _ejecutar(servicio)
        assert canal.textos == [(T1, TEXTO_EMPUJON)]
        assert len(resumen["enviados"]) == 1
        (fila,) = _seguimientos(T1)
        assert fila[:3] == ("empujon", "enviado", TEXTO_EMPUJON) and fila[4] == "wamid.texto-1"

    def test_el_mensaje_queda_en_la_conversacion_como_de_victoria(self, servicio):
        conv, _ = _escenario(T1, EMPUJON_5H)
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            _ejecutar(servicio)
        ultimo = _sql("select rol, contenido, wamid from mensajes where conversacion_id = %s order by creado_en desc, id desc limit 1", conv["id"])[0]
        assert ultimo == ("bot", TEXTO_EMPUJON, "wamid.texto-1")

    def test_avisa_al_dueno_por_telegram(self, servicio, telegram):
        _escenario(T1, EMPUJON_5H)
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            _ejecutar(servicio)
        telegram.notificar_aviso.assert_called_once()
        titulo, detalle = telegram.notificar_aviso.call_args.args
        assert "1 cliente" in titulo and T1 in detalle and "empujón" in detalle

    def test_el_texto_es_un_parametro(self, servicio, canal):
        _escenario(T1, EMPUJON_5H)
        with ajustes(seguimiento__empujon_activo=True, seguimiento__texto_empujon="¿Le ayudo a terminar su pedido?", **HORARIO_ABIERTO):
            _ejecutar(servicio)
        assert canal.textos == [(T1, "¿Le ayudo a terminar su pedido?")]

    def test_jamas_se_repite_aunque_el_cliente_siga_callado(self, servicio, canal):
        _escenario(T1, EMPUJON_5H)
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            _ejecutar(servicio)
            # Pasa el tiempo y vuelve a quedar callado tras otra respuesta de Victoria: no hay un segundo empujón.
            segunda = _ejecutar(servicio)
        assert len(canal.textos) == 1 and segunda["enviados"] == []

    def test_con_la_plantilla_apagada_no_envia_plantillas(self, servicio, canal):
        _escenario(T1, PLANTILLA_30H, anuncio=True)
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            _ejecutar(servicio)
        assert canal.textos == [] and canal.plantillas == []


class TestAQuienNuncaSeLeEscribe:
    def _nada(self, servicio, canal):
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            resumen = _ejecutar(servicio)
        assert canal.textos == [] and resumen["enviados"] == []

    def test_no_contactar(self, servicio, canal):
        _escenario(T1, EMPUJON_5H)
        _sql("update contactos set no_contactar = true where telefono = %s", T1)
        self._nada(servicio, canal)

    @pytest.mark.parametrize("temperatura", ["frio", "perdido", "ganado"])
    def test_leads_frios_perdidos_o_ganados(self, servicio, canal, temperatura):
        _escenario(T1, EMPUJON_5H, temperatura=temperatura)
        self._nada(servicio, canal)

    @pytest.mark.parametrize("estado", ["escalada", "en_gestion", "cerrada", "fria"])
    def test_conversaciones_que_no_atiende_victoria(self, servicio, canal, estado):
        _escenario(T1, EMPUJON_5H, estado=estado)
        self._nada(servicio, canal)

    def test_quien_solo_dijo_hola_y_no_sabemos_que_quiere(self, servicio, canal):
        _escenario(T1, EMPUJON_5H, producto=False)
        self._nada(servicio, canal)

    def test_si_la_ultima_palabra_es_del_cliente(self, servicio, canal):
        _escenario(T1, [("bot", 6), ("cliente", 5)])
        self._nada(servicio, canal)

    def test_si_la_ultima_palabra_fue_de_una_persona(self, servicio, canal):
        _escenario(T1, [("cliente", 6), ("humano", 5)])
        self._nada(servicio, canal)

    def test_quien_no_ha_escrito_nunca(self, servicio, canal):
        _escenario(T1, [("bot", 5)])
        self._nada(servicio, canal)

    def test_un_lead_con_el_pedido_ya_despachado(self, servicio, canal):
        _, lead = _escenario(T1, EMPUJON_5H)
        _sql("update leads set estado = 'despachado' where id = %s", lead["id"])
        self._nada(servicio, canal)

    def test_canales_sin_envio_de_plantillas(self, servicio, canal):
        # Una conversación de Instagram no se toca: ese canal no está conectado (y no tiene plantillas).
        _escenario(T1, EMPUJON_5H, canal="instagram")
        self._nada(servicio, canal)


class TestElMomento:
    def test_todavia_es_pronto(self, servicio, canal):
        _escenario(T1, [("cliente", 2), ("bot", 1.9)])
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            assert _ejecutar(servicio)["enviados"] == []

    def test_la_espera_se_ajusta_desde_parametros(self, servicio, canal):
        _escenario(T1, [("cliente", 2), ("bot", 1.9)])
        with ajustes(seguimiento__empujon_activo=True, seguimiento__horas_empujon=1, **HORARIO_ABIERTO):
            assert len(_ejecutar(servicio)["enviados"]) == 1

    def test_ya_casi_se_cierra_la_ventana_de_24_horas(self, servicio, canal):
        _escenario(T1, [("cliente", 23.5), ("bot", 23.4)])
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            assert _ejecutar(servicio)["enviados"] == []

    def test_fuera_del_horario_no_envia_nada(self, servicio, canal):
        _escenario(T1, EMPUJON_5H)
        con_noche = datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)  # 22:00 en Ecuador
        with ajustes(seguimiento__empujon_activo=True):  # horario por defecto: 9 a 20
            resumen = servicio.ejecutar(con_noche)
        assert resumen["motivo_de_pausa"] == "fuera_de_horario" and canal.textos == []

    def test_un_horario_al_reves_no_envia_nada(self, servicio, canal):
        _escenario(T1, EMPUJON_5H)
        with ajustes(seguimiento__empujon_activo=True, seguimiento__hora_desde=20, seguimiento__hora_hasta=9):
            assert _ejecutar(servicio)["motivo_de_pausa"] == "fuera_de_horario"


class TestElTopeDiario:
    def test_no_pasa_del_tope_y_prefiere_a_los_calientes(self, servicio, canal):
        _escenario(T1, EMPUJON_5H, temperatura="tibio")
        _escenario(T2, EMPUJON_5H, temperatura="caliente")
        _escenario(T3, EMPUJON_5H, temperatura="tibio")
        with ajustes(seguimiento__empujon_activo=True, seguimiento__tope_diario=1, **HORARIO_ABIERTO):
            resumen = _ejecutar(servicio)
        assert [t for t, _ in canal.textos] == [T2] and len(resumen["enviados"]) == 1

    def test_con_el_cupo_gastado_no_envia_mas_hoy(self, servicio, canal):
        _escenario(T1, EMPUJON_5H)
        _escenario(T2, EMPUJON_5H)
        with ajustes(seguimiento__empujon_activo=True, seguimiento__tope_diario=1, **HORARIO_ABIERTO):
            _ejecutar(servicio)
            segunda = _ejecutar(servicio)
        assert len(canal.textos) == 1 and segunda["motivo_de_pausa"] == "tope_diario"


class TestLaPlantilla:
    def test_a_un_cliente_de_anuncio_con_la_ventana_gratuita_abierta(self, servicio, canal):
        conv, _ = _escenario(T1, PLANTILLA_30H, anuncio=True)
        with ajustes(seguimiento__plantilla_activa=True, **HORARIO_ABIERTO):
            resumen = _ejecutar(servicio)
        assert canal.plantillas == [(T1, "retomar_conversacion")] and canal.textos == []
        (fila,) = _seguimientos(T1)
        assert fila[:2] == ("plantilla", "enviado") and fila[3] == "retomar_conversacion"
        # En la conversación queda lo que dice la plantilla, no el nombre.
        ultimo = _sql("select rol, contenido from mensajes where conversacion_id = %s order by creado_en desc, id desc limit 1", conv["id"])[0]
        assert ultimo == ("bot", TEXTO_PLANTILLA)
        assert resumen["enviados"][0]["tipo"] == "plantilla"

    def test_no_a_quien_no_llego_por_anuncio(self, servicio, canal):
        _escenario(T1, PLANTILLA_30H, anuncio=False)
        with ajustes(seguimiento__plantilla_activa=True, **HORARIO_ABIERTO):
            assert _ejecutar(servicio)["enviados"] == []
        assert canal.plantillas == []

    def test_no_si_la_ventana_gratuita_ya_se_cerro(self, servicio, canal):
        # Escribió hace 40 h y recién se le contestó hace 10 h: la respuesta cayó fuera de las 24 h y no abrió la ventana gratuita.
        _escenario(T1, [("cliente", 40), ("bot", 10)], anuncio=True)
        with ajustes(seguimiento__plantilla_activa=True, **HORARIO_ABIERTO):
            assert _ejecutar(servicio)["enviados"] == []

    def test_no_dentro_de_las_24_horas_alli_basta_el_empujon(self, servicio, canal):
        _escenario(T1, EMPUJON_5H, anuncio=True)
        with ajustes(seguimiento__plantilla_activa=True, **HORARIO_ABIERTO):
            assert _ejecutar(servicio)["enviados"] == []

    def test_se_puede_enviar_el_empujon_y_despues_la_plantilla_al_mismo_cliente_una_vez_cada_uno(self, servicio, canal):
        conv, _ = _escenario(T1, EMPUJON_5H, anuncio=True)
        with ajustes(seguimiento__empujon_activo=True, seguimiento__plantilla_activa=True, **HORARIO_ABIERTO):
            _ejecutar(servicio)  # 5 h: empujón
            assert len(canal.textos) == 1 and canal.plantillas == []
            # Pasan 26 horas más sin respuesta: toca la plantilla (y el empujón ya no se repite).
            _sql("update mensajes set creado_en = creado_en - interval '26 hours' where conversacion_id = %s", conv["id"])
            _sql("update conversacion_anuncios set creado_en = creado_en - interval '26 hours' where conversacion_id = %s", conv["id"])
            _ejecutar(servicio)
            _ejecutar(servicio)
        assert len(canal.textos) == 1 and len(canal.plantillas) == 1
        assert [f[0] for f in _seguimientos(T1)] == ["empujon", "plantilla"]

    def test_el_nombre_de_la_plantilla_es_un_parametro_y_se_valida(self, servicio, canal):
        _escenario(T1, PLANTILLA_30H, anuncio=True)
        with ajustes(seguimiento__plantilla_activa=True, seguimiento__plantilla_nombre="Nombre Invalido", **HORARIO_ABIERTO):
            assert _ejecutar(servicio)["enviados"] == []
        assert canal.plantillas == [] and _seguimientos(T1) == []


class TestCuandoElEnvioFalla:
    def test_queda_anotado_sin_mensaje_en_la_conversacion_y_se_puede_reintentar_despues(self, servicio, canal):
        conv, _ = _escenario(T1, EMPUJON_5H)
        canal.falla = WhatsAppBusinessError("Fuera de la ventana", code=131047, raw={})
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            resumen = _ejecutar(servicio)
        assert resumen["fallidos"] == 1 and resumen["enviados"] == []
        (fila,) = _seguimientos(T1)
        assert fila[1] == "fallido" and "Fuera de la ventana" in fila[5]
        # No se anotó nada en la conversación (el cliente no recibió nada).
        assert _sql("select count(*) from mensajes where conversacion_id = %s and contenido = %s", conv["id"], TEXTO_EMPUJON)[0][0] == 0
        # Un fallo no gasta el único empujón: pasadas unas horas se puede reintentar.
        _sql("update seguimientos set creado_en = now() - interval '7 hours'")
        canal.falla = None
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            _ejecutar(servicio)
        assert [f[1] for f in _seguimientos(T1)] == ["fallido", "enviado"]

    def test_no_se_insiste_enseguida_con_el_mismo_cliente(self, servicio, canal):
        _escenario(T1, EMPUJON_5H)
        canal.falla = WhatsAppRequestError("Sin conexión")
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            _ejecutar(servicio)
            canal.falla = None
            segunda = _ejecutar(servicio)
        assert segunda["enviados"] == [] and canal.textos == []

    def test_un_cliente_que_falla_no_impide_escribirle_a_los_demas(self, servicio, canal):
        _escenario(T1, EMPUJON_5H)
        _escenario(T2, EMPUJON_5H)
        llamadas = []

        def enviar(id_externo, mensaje):
            llamadas.append(id_externo)
            if len(llamadas) == 1:
                raise WhatsAppBusinessError("Número inválido", code=131026, raw={})
            return {"messages": [{"id": "wamid.ok"}]}

        canal.enviar_texto = enviar
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            resumen = _ejecutar(servicio)
        assert resumen["fallidos"] == 1 and len(resumen["enviados"]) == 1

    def test_una_plantilla_que_falla_avisa_por_telegram_y_frena_el_resto(self, servicio, canal, telegram):
        _escenario(T1, PLANTILLA_30H, anuncio=True)
        _escenario(T2, PLANTILLA_30H, anuncio=True)
        canal.falla = WhatsAppBusinessError("Template name does not exist", code=132001, raw={})
        with ajustes(seguimiento__plantilla_activa=True, **HORARIO_ABIERTO):
            resumen = _ejecutar(servicio)
            canal.falla = None
            siguiente = _ejecutar(servicio)
        # Una sola plantilla fallida en la corrida (no se insiste con el segundo cliente) y la siguiente corrida espera.
        assert resumen["fallidos"] == 1 and siguiente["enviados"] == [] and canal.plantillas == []
        telegram.notificar_aviso.assert_called_once()
        assert "plantilla" in telegram.notificar_aviso.call_args.args[0].lower()

    def test_nunca_lanza_aunque_la_base_falle(self, servicio, monkeypatch):
        with ajustes(seguimiento__empujon_activo=True, **HORARIO_ABIERTO):
            monkeypatch.setattr(servicio._repo, "candidatos", MagicMock(side_effect=RuntimeError("base caída")))
            monkeypatch.setattr(servicio._repo, "contar_fallos", MagicMock(return_value=0))
            resumen = _ejecutar(servicio)
        assert resumen["enviados"] == []


class TestLaReserva:
    def test_el_mismo_cliente_no_se_reserva_dos_veces_para_el_mismo_tipo(self):
        _, lead = _escenario(T1, EMPUJON_5H)
        primera = SeguimientoRepository.reservar(lead["id"], "whatsapp", "empujon", "x")
        segunda = SeguimientoRepository.reservar(lead["id"], "whatsapp", "empujon", "x")
        assert primera is not None and segunda is None
        # Pero sí puede recibir una plantilla (otro tipo).
        assert SeguimientoRepository.reservar(lead["id"], "whatsapp", "plantilla", "y", "retomar_conversacion") is not None

    def test_no_se_reserva_si_pidio_que_no_lo_contacten_despues_de_la_consulta(self):
        _, lead = _escenario(T1, EMPUJON_5H)
        _sql("update contactos set no_contactar = true where telefono = %s", T1)
        assert SeguimientoRepository.reservar(lead["id"], "whatsapp", "empujon", "x") is None

    def test_no_se_reserva_si_el_cliente_escribio_despues_de_la_consulta(self):
        conv, lead = _escenario(T1, EMPUJON_5H)
        _mensaje(conv["id"], "cliente", 0)  # contestó justo ahora: la última palabra ya es suya
        assert SeguimientoRepository.reservar(lead["id"], "whatsapp", "empujon", "x") is None

    def test_no_se_reserva_si_la_conversacion_paso_a_manos_del_dueno_despues_de_la_consulta(self):
        conv, lead = _escenario(T1, EMPUJON_5H)
        _sql("update conversaciones set estado = 'escalada' where id = %s", conv["id"])
        assert SeguimientoRepository.reservar(lead["id"], "whatsapp", "empujon", "x") is None

    def test_no_se_reserva_si_el_lead_ya_no_esta_abierto(self):
        _, lead = _escenario(T1, EMPUJON_5H, temperatura="perdido")
        assert SeguimientoRepository.reservar(lead["id"], "whatsapp", "empujon", "x") is None

    def test_una_reserva_a_medias_cuenta_en_el_tope_y_bloquea_un_segundo_envio(self):
        _, lead = _escenario(T1, EMPUJON_5H)
        SeguimientoRepository.reservar(lead["id"], "whatsapp", "empujon", "x")  # el proceso se cayó antes de enviar
        assert SeguimientoRepository.contar_del_dia(datetime(2000, 1, 1, tzinfo=timezone.utc)) >= 1
        assert SeguimientoRepository.reservar(lead["id"], "whatsapp", "empujon", "x") is None

    def test_los_seguimientos_protegen_el_historial_no_se_borra_un_lead_con_seguimientos(self):
        import psycopg2.errors

        _, lead = _escenario(T1, EMPUJON_5H)
        SeguimientoRepository.reservar(lead["id"], "whatsapp", "empujon", "x")
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            _sql("delete from leads where id = %s", lead["id"])
