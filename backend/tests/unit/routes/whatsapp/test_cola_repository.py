"""Cola de mensajes y orden de mensajes contra la base real (la desechable de pruebas)."""
from datetime import datetime, timedelta, timezone

import pytest

from src.routes.whatsapp.repository import ColaMensajeRepository, ConversacionRepository, MensajeRepository
from tests.helpers_db import borrar_conversaciones_de_prueba

TELEFONO = "593900007771"


@pytest.fixture
def conversacion():
    borrar_conversaciones_de_prueba(TELEFONO)
    c = ConversacionRepository.crear(id_externo=TELEFONO, origen="directo")
    yield c["id"]
    borrar_conversaciones_de_prueba(TELEFONO)


def _propias(conversacion_id):
    return [f for f in ColaMensajeRepository.obtener_pendientes() if f["conversacion_id"] == conversacion_id]


class TestRecuperarAlReiniciar:
    def test_una_tarea_pendiente_se_recupera_con_sus_intentos(self, conversacion):
        fila = ColaMensajeRepository.crear(conversacion, "ia")
        recuperadas = _propias(conversacion)
        assert [f["id"] for f in recuperadas] == [fila["id"]]
        assert recuperadas[0]["intentos"] == 0 and recuperadas[0]["id_externo"] == TELEFONO

    def test_una_tarea_procesando_se_recupera_aunque_sea_reciente(self, conversacion):
        # Antes solo se recuperaba pasados 5 minutos: una tarea cortada por un reinicio se perdía.
        fila = ColaMensajeRepository.crear(conversacion, "ia")
        ColaMensajeRepository.marcar_procesando(fila["id"])
        assert [f["id"] for f in _propias(conversacion)] == [fila["id"]]

    def test_las_completadas_y_las_fallidas_no_se_recuperan(self, conversacion):
        hecha = ColaMensajeRepository.crear(conversacion, "ia")
        ColaMensajeRepository.marcar_completado(hecha["id"])
        rota = ColaMensajeRepository.crear(conversacion, "ia")
        ColaMensajeRepository.marcar_error(rota["id"], "boom")
        assert _propias(conversacion) == []


class TestReintento:
    def test_vuelve_a_pendiente_y_cuenta_el_intento(self, conversacion):
        fila = ColaMensajeRepository.crear(conversacion, "ia")
        ColaMensajeRepository.marcar_procesando(fila["id"])

        assert ColaMensajeRepository.marcar_para_reintento(fila["id"], "IA saturada") == 1
        assert ColaMensajeRepository.marcar_para_reintento(fila["id"], "IA saturada") == 2
        recuperada = _propias(conversacion)[0]
        assert recuperada["intentos"] == 2


class TestOrdenDeMensajes:
    def test_una_respuesta_con_hora_anterior_queda_antes_del_mensaje_que_llego_despues(self, conversacion):
        hola = MensajeRepository.crear(conversacion, "cliente", "Hola")
        MensajeRepository.crear(conversacion, "cliente", "¿Tienen audífonos?")
        # La respuesta se redactó leyendo solo «Hola»: se guarda con SU hora, no con la de ahora.
        MensajeRepository.crear(conversacion, "bot", "¡Hola!", creado_en=hola["creado_en"])

        orden = [(f["rol"], f["contenido"]) for f in MensajeRepository.obtener_por_conversacion(conversacion)]
        assert orden == [("cliente", "Hola"), ("bot", "¡Hola!"), ("cliente", "¿Tienen audífonos?")]

    def test_sin_hora_explicita_vale_la_de_la_base(self, conversacion):
        antes = datetime.now(timezone.utc) - timedelta(seconds=5)
        fila = MensajeRepository.crear(conversacion, "bot", "Hola")
        assert fila["creado_en"] >= antes
