"""
Recordatorios al dueño (pendiente #76): un chat que Victoria le pasó y sigue sin abrir genera avisos por Telegram a los 15 min, luego
cada 30, hasta 3 y solo entre las 8 y las 21 h de Ecuador. Abrir el chat (o que deje de estar en sus manos) los detiene.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.config.parametros import parametros
from src.jobs.recordatorios.reglas import tiempo_legible, toca_recordatorio
from src.jobs.recordatorios.repository import RecordatoriosRepository
from src.jobs.recordatorios.service import RecordatoriosService
from src.routes.conversaciones.services import ConversacionesService
from src.routes.whatsapp.repository import ConversacionRepository
from tests.helpers_db import borrar_conversaciones_de_prueba

# Ecuador es UTC-5: las 15:00 UTC son las 10:00 de Ecuador (dentro del horario 8-21).
MEDIODIA = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)
MADRUGADA = datetime(2026, 11, 10, 7, 0, tzinfo=timezone.utc)  # 02:00 en Ecuador
NOCHE = datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc)  # 22:00 en Ecuador


def _toca(pendiente_hace_min, enviados=0, ultimo_hace_min=None, ahora=MEDIODIA, primero=15, entre=30, maximo=3, desde=8, hasta=21):
    ultimo = ahora - timedelta(minutes=ultimo_hace_min) if ultimo_hace_min is not None else None
    return toca_recordatorio(ahora - timedelta(minutes=pendiente_hace_min), enviados, ultimo, ahora, primero, entre, maximo, desde, hasta)


class TestLasReglas:
    def test_el_primero_sale_a_los_15_minutos_no_antes(self):
        assert not _toca(14) and _toca(15) and _toca(60)

    def test_los_siguientes_salen_cada_30_minutos_contados_desde_el_ultimo(self):
        assert not _toca(80, enviados=1, ultimo_hace_min=29)
        assert _toca(80, enviados=1, ultimo_hace_min=30)
        assert _toca(200, enviados=2, ultimo_hace_min=45)

    def test_nunca_pasa_del_maximo(self):
        assert not _toca(500, enviados=3, ultimo_hace_min=500)
        assert _toca(500, enviados=2, ultimo_hace_min=500, maximo=3)

    def test_de_madrugada_o_de_noche_no_se_manda_nada(self):
        assert not _toca(120, ahora=MADRUGADA) and not _toca(120, ahora=NOCHE)

    def test_lo_que_toco_de_madrugada_sale_apenas_empieza_el_horario(self):
        pendiente = MADRUGADA - timedelta(minutes=30)  # quedó pendiente de madrugada
        apenas_empieza = datetime(2026, 11, 10, 13, 0, tzinfo=timezone.utc)  # 08:00 en Ecuador
        assert not toca_recordatorio(pendiente, 0, None, MADRUGADA, 15, 30, 3, 8, 21)
        assert toca_recordatorio(pendiente, 0, None, apenas_empieza, 15, 30, 3, 8, 21)

    def test_un_horario_al_reves_no_manda_nada(self):
        assert not _toca(120, desde=21, hasta=8)

    def test_tiempo_legible(self):
        assert [tiempo_legible(m) for m in (0, 20, 59, 60, 65, 180, 1500, 3000)] == ["0 min", "20 min", "59 min", "1 h", "1 h 5 min", "3 h", "1 día", "2 días"]


def _chat(id=1, estado="escalada", pendiente_hace_min=20, enviados=0, ultimo_hace_min=None, ultimo_mensaje="Quiero hablar con una persona"):
    return {
        "id": id, "canal": "whatsapp", "id_externo": "593987654321", "estado": estado,
        "pendiente_desde": MEDIODIA - timedelta(minutes=pendiente_hace_min), "recordatorios_enviados": enviados,
        "ultimo_recordatorio_en": MEDIODIA - timedelta(minutes=ultimo_hace_min) if ultimo_hace_min is not None else None,
        "telefono": "593987654321", "nombre": "Ana", "ultimo_mensaje": ultimo_mensaje,
    }


class RepoFalso:
    def __init__(self, chats):
        self.chats, self.registrados = chats, []

    def pendientes(self):
        return self.chats

    def registrar_envio(self, conversacion_id):
        self.registrados.append(conversacion_id)


def _servicio(chats, ahora=MEDIODIA):
    telegram = MagicMock()
    return RecordatoriosService(repo=RepoFalso(chats), telegram=telegram, ahora=lambda: ahora), telegram


class TestElServicio:
    def test_avisa_con_los_datos_del_chat_y_lo_deja_registrado(self):
        servicio, telegram = _servicio([_chat(id=7)])
        assert servicio.ejecutar() == 1
        args = telegram.notificar_recordatorio.call_args.kwargs
        assert args["conversacion_id"] == 7 and args["numero"] == 1 and args["maximo"] == 3
        assert args["espera"] == "20 min" and "Ana" not in args["cliente"] and "593987654321" in args["cliente"]
        assert args["ultimo_mensaje"] == "Quiero hablar con una persona" and args["enlace"].endswith("/conversaciones/7")
        assert "persona" in args["motivo"]
        assert servicio._repo.registrados == [7]

    def test_un_pedido_en_gestion_dice_que_hay_una_gestion_pendiente(self):
        servicio, telegram = _servicio([_chat(estado="en_gestion")])
        servicio.ejecutar()
        assert "gestión" in telegram.notificar_recordatorio.call_args.kwargs["motivo"]

    def test_todavia_no_toca_no_manda_nada(self):
        servicio, telegram = _servicio([_chat(pendiente_hace_min=5)])
        assert servicio.ejecutar() == 0 and telegram.notificar_recordatorio.call_count == 0 and servicio._repo.registrados == []

    def test_a_cada_chat_le_toca_lo_suyo(self):
        servicio, telegram = _servicio([_chat(id=1, pendiente_hace_min=20), _chat(id=2, pendiente_hace_min=90, enviados=1, ultimo_hace_min=10), _chat(id=3, pendiente_hace_min=300, enviados=3, ultimo_hace_min=100)])
        assert servicio.ejecutar() == 1 and servicio._repo.registrados == [1]

    def test_un_mensaje_largo_se_recorta_y_en_una_sola_linea(self):
        servicio, telegram = _servicio([_chat(ultimo_mensaje="hola\n" * 100)])
        servicio.ejecutar()
        enviado = telegram.notificar_recordatorio.call_args.kwargs["ultimo_mensaje"]
        assert "\n" not in enviado and len(enviado) <= 140

    def test_si_un_chat_falla_los_demas_igual_reciben_su_aviso(self):
        servicio, telegram = _servicio([_chat(id=1), _chat(id=2)])
        telegram.notificar_recordatorio.side_effect = [RuntimeError("boom"), None]
        assert servicio.ejecutar() == 1 and servicio._repo.registrados == [2]

    def test_apagado_desde_parametros_no_manda_nada(self):
        try:
            parametros.guardar("recordatorios.activo", False, "test@ejemplo.com")
            servicio, telegram = _servicio([_chat()])
            assert servicio.ejecutar() == 0 and telegram.notificar_recordatorio.call_count == 0
        finally:
            parametros.restaurar("recordatorios.activo", "test@ejemplo.com")

    def test_los_valores_salen_de_los_parametros(self):
        try:
            parametros.guardar("recordatorios.minutos_primero", 60, "test@ejemplo.com")
            servicio, _ = _servicio([_chat(pendiente_hace_min=30)])
            assert servicio.ejecutar() == 0
        finally:
            parametros.restaurar("recordatorios.minutos_primero", "test@ejemplo.com")


TELEFONO = "593900007774"


@pytest.fixture
def conversacion():
    borrar_conversaciones_de_prueba(TELEFONO)
    c = ConversacionRepository.crear(id_externo=TELEFONO, origen="directo")
    yield c["id"]
    borrar_conversaciones_de_prueba(TELEFONO)


def _pendientes(id_):
    return [c for c in RecordatoriosRepository.pendientes() if c["id"] == id_]


class TestContraLaBaseReal:
    def test_una_conversacion_activa_no_esta_pendiente(self, conversacion):
        assert _pendientes(conversacion) == []

    def test_al_escalar_queda_pendiente_con_el_ultimo_mensaje_del_cliente(self, conversacion):
        from src.routes.whatsapp.repository import MensajeRepository

        MensajeRepository.crear(conversacion_id=conversacion, rol="cliente", contenido="primero", tipo="texto", wamid=None)
        MensajeRepository.crear(conversacion_id=conversacion, rol="cliente", contenido="quiero una persona", tipo="texto", wamid=None)
        ConversacionRepository.marcar_escalada(conversacion)
        (chat,) = _pendientes(conversacion)
        assert chat["estado"] == "escalada" and chat["pendiente_desde"] is not None and chat["recordatorios_enviados"] == 0
        assert chat["ultimo_mensaje"] == "quiero una persona"

    def test_en_gestion_tambien_cuenta(self, conversacion):
        ConversacionRepository.marcar_en_gestion(conversacion)
        assert [c["estado"] for c in _pendientes(conversacion)] == ["en_gestion"]

    def test_registrar_el_envio_cuenta_y_marca_la_hora(self, conversacion):
        ConversacionRepository.marcar_escalada(conversacion)
        RecordatoriosRepository.registrar_envio(conversacion)
        RecordatoriosRepository.registrar_envio(conversacion)
        (chat,) = _pendientes(conversacion)
        assert chat["recordatorios_enviados"] == 2 and chat["ultimo_recordatorio_en"] is not None

    def test_abrir_el_chat_lo_deja_de_marcar_pendiente(self, conversacion):
        ConversacionRepository.marcar_escalada(conversacion)
        assert len(_pendientes(conversacion)) == 1
        ConversacionesService(bot_worker=MagicMock()).obtener_detalle(conversacion)  # abrirlo en el panel
        assert _pendientes(conversacion) == []

    def test_devolverlo_a_victoria_o_tomarlo_lo_deja_de_marcar_pendiente(self, conversacion):
        ConversacionRepository.marcar_escalada(conversacion)
        ConversacionRepository.actualizar_estado(conversacion, "activa")
        assert _pendientes(conversacion) == []
        ConversacionRepository.marcar_escalada(conversacion)
        ConversacionRepository.marcar_manual(conversacion)
        assert _pendientes(conversacion) == []

    def test_escalar_de_nuevo_reinicia_los_recordatorios(self, conversacion):
        ConversacionRepository.marcar_escalada(conversacion)
        RecordatoriosRepository.registrar_envio(conversacion)
        ConversacionRepository.actualizar_estado(conversacion, "activa")
        ConversacionRepository.marcar_escalada(conversacion)
        (chat,) = _pendientes(conversacion)
        assert chat["recordatorios_enviados"] == 0 and chat["ultimo_recordatorio_en"] is None
