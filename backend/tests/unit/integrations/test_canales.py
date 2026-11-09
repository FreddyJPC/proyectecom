"""Registro de canales de mensajería (ADR-014): WhatsApp conectado; Instagram y Messenger existen pero aún no."""
from unittest.mock import MagicMock

import pytest

from src.integrations.canales import (
    CANALES,
    CanalNoDisponibleError,
    CanalWhatsApp,
    RegistroCanales,
    etiqueta_de_cliente,
    nombre_de_canal,
)


def test_los_tres_canales_son_validos_en_el_sistema():
    assert CANALES == ("whatsapp", "instagram", "messenger")


def test_whatsapp_envia_usando_el_identificador_del_cliente_como_telefono():
    cliente = MagicMock()
    canal = CanalWhatsApp(cliente)

    canal.enviar_texto("593987654321", "Hola")
    canal.enviar_imagen("593987654321", "https://x/y.jpg", "Un reloj")

    cliente.enviar_texto.assert_called_once_with(telefono="593987654321", mensaje="Hola")
    cliente.enviar_imagen.assert_called_once_with(telefono="593987654321", url="https://x/y.jpg", descripcion="Un reloj")


def test_el_registro_encamina_por_canal_y_asume_whatsapp_si_no_se_dice():
    whatsapp = CanalWhatsApp(MagicMock())
    registro = RegistroCanales({"whatsapp": whatsapp})
    assert registro.para("whatsapp") is whatsapp
    assert registro.para(None) is whatsapp
    assert registro.conectados() == ("whatsapp",)


@pytest.mark.parametrize("canal", ["instagram", "messenger"])
def test_un_canal_valido_pero_no_conectado_falla_con_un_mensaje_claro(canal):
    registro = RegistroCanales({"whatsapp": CanalWhatsApp(MagicMock())})
    with pytest.raises(CanalNoDisponibleError) as error:
        registro.para(canal)
    assert nombre_de_canal(canal) in str(error.value) and "todavía no está conectado" in str(error.value)


def test_la_etiqueta_del_cliente_dice_canal_y_telefono_o_identificador():
    assert etiqueta_de_cliente("whatsapp", "593987654321") == "WhatsApp · 593987654321"
    assert etiqueta_de_cliente("instagram", "17841400000000000") == "Instagram · 17841400000000000"
    # Si ya se conoce el teléfono de un cliente de otro canal, es lo más útil para el dueño.
    assert etiqueta_de_cliente("messenger", "9876", telefono="593987654321") == "Messenger · 593987654321"
    assert etiqueta_de_cliente(None, None) == "WhatsApp · —"


def test_whatsapp_envia_plantillas_con_el_identificador_como_telefono():
    cliente = MagicMock()
    CanalWhatsApp(cliente).enviar_plantilla("593987654321", "retomar_conversacion")
    cliente.enviar_plantilla.assert_called_once_with(
        telefono="593987654321", nombre_plantilla="retomar_conversacion", variables=None, idioma="es"
    )


def test_el_registro_dice_que_canales_saben_enviar_plantillas():
    class SoloTexto:
        def enviar_texto(self, id_externo, mensaje):
            return {}

    registro = RegistroCanales({"whatsapp": CanalWhatsApp(MagicMock()), "instagram": SoloTexto()})
    # Un canal sin plantillas queda fuera del seguimiento automático (no se le puede escribir pasadas las 24 h).
    assert registro.con_plantillas() == ("whatsapp",)
    assert registro.conectados() == ("whatsapp", "instagram")
